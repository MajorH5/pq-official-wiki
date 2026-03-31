"""
Incremental wiki import: diff new datadump vs cached copy, and detect renderer/template changes.

Full re-import when:
- No cached dump
- PQ_IMPORT_FULL=1 or --force (handled in runner)
- Render fingerprint changed (layout .wikitext + core renderers)
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from pq_wiki.config import (
    BOT_ROOT,
    LAST_DATADUMP_CACHE_PATH,
    LAST_IMPORT_STATE_PATH,
    WIKI_LAYOUT_TEMPLATES_DIR,
)
from pq_wiki.drop_sources import ItemDropSource, build_item_id_to_drop_sources
from pq_wiki.render_pages import entity_page_path


def _with_unreleased_namespace(title: str, unreleased: bool) -> str:
    if not unreleased:
        return title
    if title.startswith("Unreleased:"):
        return title
    return f"Unreleased:{title}"

# Files whose edits change generated wikitext (templates + main renderers).
_RENDER_CODE_PATHS: tuple[Path, ...] = (
    BOT_ROOT / "pq_wiki" / "renderers" / "item_renderer.py",
    BOT_ROOT / "pq_wiki" / "renderers" / "entity_renderer.py",
    BOT_ROOT / "pq_wiki" / "renderers" / "location_renderer.py",
    BOT_ROOT / "pq_wiki" / "renderers" / "biome_renderer.py",
    BOT_ROOT / "pq_wiki" / "renderers" / "skin_renderer.py",
    BOT_ROOT / "pq_wiki" / "renderers" / "badge_renderer.py",
    BOT_ROOT / "pq_wiki" / "renderers" / "achievement_renderer.py",
    BOT_ROOT / "pq_wiki" / "renderers" / "shared.py",
    BOT_ROOT / "pq_wiki" / "wikitext_util.py",
    BOT_ROOT / "pq_wiki" / "reward_wikitext.py",
    BOT_ROOT / "pq_wiki" / "datadump_helpers.py",
    BOT_ROOT / "pq_wiki" / "honor_icons.py",
    BOT_ROOT / "pq_wiki" / "achievement_icons.py",
    BOT_ROOT / "pq_wiki" / "seo.py",
    BOT_ROOT / "pq_wiki" / "drop_sources.py",
    BOT_ROOT / "pq_wiki" / "skin_drops.py",
    BOT_ROOT / "pq_wiki" / "skin_rarity_icons.py",
    BOT_ROOT / "pq_wiki" / "stat_icons.py",
    BOT_ROOT / "pq_wiki" / "status_effect_icons.py",
    BOT_ROOT / "pq_wiki" / "renderers" / "status_effect_renderer.py",
    BOT_ROOT / "pq_wiki" / "valor_icon.py",
)

_TEMPLATE_NAMES: tuple[str, ...] = (
    "PQ_Item.wikitext",
    "PQ_Entity.wikitext",
    "PQ_Location.wikitext",
    "PQ_Biome.wikitext",
    "PQ_Skin.wikitext",
    "PQ_Badge.wikitext",
    "PQ_Achievement.wikitext",
)


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return _hash_bytes(path.read_bytes())


def compute_render_fingerprint() -> str:
    """SHA-256 of concatenated layout templates + renderer sources (stable order)."""
    h = hashlib.sha256()
    paths: list[Path] = []
    for p in _RENDER_CODE_PATHS:
        paths.append(p)
    for name in _TEMPLATE_NAMES:
        paths.append(WIKI_LAYOUT_TEMPLATES_DIR / name)
    for p in sorted(paths, key=lambda x: str(x)):
        if p.is_file():
            h.update(str(p).encode("utf-8"))
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return h.hexdigest()


def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _object_hash(obj: dict[str, Any]) -> str:
    return _hash_bytes(stable_json(obj).encode("utf-8"))


def _index_by_id(rows: list[dict[str, Any]], key: str = "Id") -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        try:
            iid = int(row.get(key, -1))
        except (TypeError, ValueError):
            continue
        out[iid] = row
    return out


def _serialize_drop_sources(m: dict[int, list[ItemDropSource]]) -> dict[int, str]:
    out: dict[int, str] = {}
    for iid, rows in m.items():
        keys = []
        for r in rows:
            keys.append(
                (
                    r.entity_id,
                    r.entity_name,
                    r.entity_path or "",
                    r.via,
                    r.group_label or "",
                )
            )
        out[iid] = stable_json(sorted(keys))
    return out


def build_entity_name_to_locations(locations: list[dict[str, Any]]) -> dict[str, tuple[str, ...]]:
    """Entity name -> sorted tuple of location names (for diffing Found in)."""
    entity_name_to_locations: dict[str, list[str]] = {}
    for loc in locations:
        lname = str(loc.get("Name") or "")
        if not lname:
            continue
        for go_name in loc.get("FoundGameObjects") or []:
            if not go_name:
                continue
            k = str(go_name)
            entity_name_to_locations.setdefault(k, [])
            if lname not in entity_name_to_locations[k]:
                entity_name_to_locations[k].append(lname)
    return {k: tuple(sorted(v)) for k, v in entity_name_to_locations.items()}


def diff_item_ids(
    old_data: dict[str, Any],
    new_items: list[dict[str, Any]],
    new_game_objects: list[dict[str, Any]],
    unreleased_entities: set[int],
) -> set[int]:
    """Item ids whose item JSON or derived drop sources changed."""
    old_items = old_data.get("Items") or []
    new_idx = _index_by_id(new_items)
    old_idx = _index_by_id(list(old_items))
    changed: set[int] = set()

    for iid, row in new_idx.items():
        if iid not in old_idx:
            changed.add(iid)
            continue
        if _object_hash(row) != _object_hash(old_idx[iid]):
            changed.add(iid)

    # Drop sources: depend on all entities + loot tables
    def build_maps(
        items: list[dict[str, Any]],
        gos: list[dict[str, Any]],
        unreleased_ent: set[int],
    ) -> dict[int, str]:
        item_name_to_id: dict[str, int] = {}
        for it in items:
            n = it.get("Name")
            if n:
                item_name_to_id[str(n)] = int(it["Id"])
        item_id_to_item = {int(it["Id"]): it for it in items}
        used_paths_public: set[str] = set()
        used_paths_unreleased: set[str] = set()
        entity_id_to_path: dict[int, str] = {}
        entities_sorted = sorted(
            (go for go in gos if go.get("IsEntity", True)),
            key=lambda x: x["Id"],
        )
        for go in entities_sorted:
            gid = int(go["Id"])
            is_unreleased = gid in unreleased_ent
            used = used_paths_unreleased if is_unreleased else used_paths_public
            base = entity_page_path(go, used)
            entity_id_to_path[gid] = _with_unreleased_namespace(base, is_unreleased)

        ds = build_item_id_to_drop_sources(gos, item_name_to_id, item_id_to_item, entity_id_to_path)
        return _serialize_drop_sources(ds)

    ser_old = build_maps(
        list(old_data.get("Items") or []),
        old_data.get("GameObjects") or [],
        unreleased_entities,
    )
    ser_new = build_maps(new_items, new_game_objects, unreleased_entities)

    all_ids = set(new_idx.keys()) | set(old_idx.keys())
    for iid in all_ids:
        if ser_old.get(iid) != ser_new.get(iid):
            changed.add(iid)

    return changed


def diff_badge_ids(
    old_data: dict[str, Any],
    new_badges: list[dict[str, Any]],
) -> set[int]:
    old_b = old_data.get("Badges") or []
    new_idx = _index_by_id(new_badges)
    old_idx = _index_by_id(list(old_b))
    changed: set[int] = set()
    for bid, row in new_idx.items():
        if bid not in old_idx:
            changed.add(bid)
            continue
        if _object_hash(row) != _object_hash(old_idx[bid]):
            changed.add(bid)
    return changed


def diff_achievement_ids(
    old_data: dict[str, Any],
    new_achievements: list[dict[str, Any]],
) -> set[int]:
    old_a = old_data.get("Achievements") or []
    new_idx = _index_by_id(new_achievements)
    old_idx = _index_by_id(list(old_a))
    changed: set[int] = set()
    for aid, row in new_idx.items():
        if aid not in old_idx:
            changed.add(aid)
            continue
        if _object_hash(row) != _object_hash(old_idx[aid]):
            changed.add(aid)
    return changed


def diff_status_effect_ids(
    old_data: dict[str, Any],
    new_rows: list[dict[str, Any]],
) -> set[int]:
    old_rows = old_data.get("StatusEffects") or []
    new_idx = _index_by_id(new_rows)
    old_idx = _index_by_id(list(old_rows) if isinstance(old_rows, list) else [])
    changed: set[int] = set()
    for sid, row in new_idx.items():
        if sid < 0:
            continue
        if sid not in old_idx:
            changed.add(sid)
            continue
        if _object_hash(row) != _object_hash(old_idx[sid]):
            changed.add(sid)
    return changed


def diff_skin_ids(
    old_data: dict[str, Any],
    new_skins: list[dict[str, Any]],
) -> set[int]:
    old_skins = old_data.get("CharacterSkins") or []
    new_idx = _index_by_id(new_skins)
    old_idx = _index_by_id(list(old_skins))
    changed: set[int] = set()
    for sid, row in new_idx.items():
        if sid not in old_idx:
            changed.add(sid)
            continue
        if _object_hash(row) != _object_hash(old_idx[sid]):
            changed.add(sid)
    return changed


def diff_location_ids(
    old_data: dict[str, Any],
    new_locations: list[dict[str, Any]],
) -> set[int]:
    old_locs = old_data.get("Locations") or []
    new_idx = _index_by_id(new_locations)
    old_idx = _index_by_id(list(old_locs))
    changed: set[int] = set()
    for lid, row in new_idx.items():
        if lid not in old_idx:
            changed.add(lid)
            continue
        if _object_hash(row) != _object_hash(old_idx[lid]):
            changed.add(lid)
    return changed


def diff_biome_ids(
    old_data: dict[str, Any],
    new_biomes: list[dict[str, Any]],
) -> set[int]:
    old_b = old_data.get("Biomes") or []
    if not isinstance(old_b, list):
        old_b = []
    new_idx = _index_by_id(new_biomes)
    old_idx = _index_by_id(list(old_b))
    changed: set[int] = set()
    for bid, row in new_idx.items():
        if bid not in old_idx:
            changed.add(bid)
            continue
        if _object_hash(row) != _object_hash(old_idx[bid]):
            changed.add(bid)
    return changed


def diff_entity_ids(
    old_data: dict[str, Any],
    new_game_objects: list[dict[str, Any]],
    new_locations: list[dict[str, Any]],
) -> set[int]:
    old_gos = [go for go in (old_data.get("GameObjects") or []) if go.get("IsEntity", True)]
    new_gos = [go for go in new_game_objects if go.get("IsEntity", True)]
    new_idx = _index_by_id(new_gos)
    old_idx = _index_by_id(list(old_gos))
    changed: set[int] = set()

    for gid, row in new_idx.items():
        if gid not in old_idx:
            changed.add(gid)
            continue
        if _object_hash(row) != _object_hash(old_idx[gid]):
            changed.add(gid)

    loc_old = build_entity_name_to_locations(old_data.get("Locations") or [])
    loc_new = build_entity_name_to_locations(new_locations)
    for name in set(loc_old) | set(loc_new):
        if loc_old.get(name) != loc_new.get(name):
            go = next((g for g in new_gos if str(g.get("Name") or "") == name), None)
            if go:
                changed.add(int(go["Id"]))
            go_old = next((g for g in old_gos if str(g.get("Name") or "") == name), None)
            if go_old:
                changed.add(int(go_old["Id"]))

    return changed


def read_last_import_state() -> dict[str, Any] | None:
    if not LAST_IMPORT_STATE_PATH.exists():
        return None
    try:
        return json.loads(LAST_IMPORT_STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_last_import_state(
    *,
    datadump_version: str,
    datadump_content_sha256: str,
    render_fingerprint: str,
) -> None:
    LAST_IMPORT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAST_IMPORT_STATE_PATH.write_text(
        json.dumps(
            {
                "datadump_version": datadump_version,
                "datadump_content_sha256": datadump_content_sha256,
                "render_fingerprint": render_fingerprint,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def load_cached_datadump() -> dict[str, Any] | None:
    if not LAST_DATADUMP_CACHE_PATH.is_file():
        return None
    try:
        with LAST_DATADUMP_CACHE_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def write_cached_datadump(source_path: Path) -> None:
    LAST_DATADUMP_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, LAST_DATADUMP_CACHE_PATH)


def compute_incremental_sets(
    *,
    old_data: dict[str, Any],
    new_items: list[dict[str, Any]],
    new_locations: list[dict[str, Any]],
    new_biomes: list[dict[str, Any]],
    new_game_objects: list[dict[str, Any]],
    new_character_skins: list[dict[str, Any]],
    new_badges: list[dict[str, Any]],
    new_achievements: list[dict[str, Any]],
    new_status_effects: list[dict[str, Any]],
    unreleased_entities: set[int],
) -> tuple[set[int], set[int], set[int], set[int], set[int], set[int], set[int], set[int]]:
    """Returns changed ids: items, locations, biomes, entities, skins, badges, achievements, status effects."""
    ci = diff_item_ids(
        old_data,
        new_items,
        new_game_objects,
        unreleased_entities,
    )
    cl = diff_location_ids(old_data, new_locations)
    cbi = diff_biome_ids(old_data, new_biomes)
    ce = diff_entity_ids(old_data, new_game_objects, new_locations)
    cs = diff_skin_ids(old_data, new_character_skins)
    cb = diff_badge_ids(old_data, new_badges)
    ca = diff_achievement_ids(old_data, new_achievements)
    cfx = diff_status_effect_ids(old_data, new_status_effects)
    return ci, cl, cbi, ce, cs, cb, ca, cfx
