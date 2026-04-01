from __future__ import annotations

import json
import os
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Must run before import pywikibot if this module is ever loaded first.
os.environ.setdefault(
    "PYWIKIBOT_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
)

import pywikibot

from pq_wiki.config import (
    FORCE_OVERWRITE,
    GENERATE_FEW_PAGES_LIMIT,
    LAST_VERSION_PATH,
    WIKI_OVERRIDES_PATH,
    WIKI_BOT_USER,
    ensure_dirs,
)
from pq_wiki.import_diff import (
    compute_incremental_sets,
    compute_render_fingerprint,
    load_cached_datadump,
    read_last_import_state,
    sha256_file,
    write_cached_datadump,
    write_last_import_state,
)
from pq_wiki.difficulty_icons import build_difficulty_skull_wikitext
from pq_wiki.drop_sources import build_item_id_to_drop_sources
from pq_wiki.import_log import get_import_logger
from pq_wiki.loot_tier_icons import build_drop_tier_icon_parts_map, build_drop_tier_wikitext_map
from pq_wiki.skin_rarity_icons import build_skin_rarity_wikitext_map
from pq_wiki.honor_icons import build_honor_icon_wikitext_map
from pq_wiki.render_pages import (
    STATUS_EFFECTS_INDEX_TITLE,
    achievement_page_path,
    account_stat_page_path,
    badge_page_path,
    build_account_stat_wikitext,
    build_achievement_wikitext,
    build_badge_wikitext,
    biome_page_path,
    build_biome_wikitext,
    build_entity_wikitext,
    build_item_wikitext,
    build_location_wikitext,
    build_quest_wikitext,
    build_skin_wikitext,
    build_status_effect_name_to_path_map,
    build_status_effects_index_wikitext,
    entity_page_path,
    item_page_path,
    location_page_path,
    quest_page_path,
    save_bot_page,
    skin_page_path,
)
from pq_wiki.renderers.save import (
    peek_skip_build_reason,
    push_edit_summary_override,
    reset_edit_summary_override,
)
from pq_wiki.stat_icons import build_stat_icon_wikitext_map
from pq_wiki.status_effect_icons import build_status_effect_icon_wikitext_map
from pq_wiki.valor_icon import build_valor_icon_wikitext
from pq_wiki.wiki_assets import ensure_loot_chest_toc_css, ensure_pixel_art_css

SUPPORTED_IMPORT_KINDS: frozenset[str] = frozenset(
    {
        "items",
        "locations",
        "biomes",
        "entities",
        "skins",
        "account_stats",
        "badges",
        "achievements",
        "quests",
        "status_effects",
    }
)


@dataclass(frozen=True)
class KindImportSelection:
    """
    Parsed ?kinds= query (or equivalent).

    - ``items:Chest`` — items with that exact TypeHierarchy string; ``items:634`` — item Id 634 only.
    - ``locations:634`` or ``locations:Dungeon Name`` — only that location Id or exact Name (spaces OK).
    - ``biomes:2`` or ``biomes:Beach`` — only that biome Id or exact Name (spaces OK).
    - ``entities:497`` or ``entities:Loot Chest`` — only that entity Id or exact Name.
    - ``skins:Name`` or ``skins:123`` — only the skin with that Name or Id.
    """

    kinds: frozenset[str]
    items_hierarchy: str | None = None
    locations_spec: str | None = None
    biomes_spec: str | None = None
    entities_spec: str | None = None
    skins_spec: str | None = None


def parse_kind_import_selection(raw: str) -> KindImportSelection | None:
    """
    Comma-separated tokens: ``items:Chest``, ``locations:Coral Cove``, ``biomes:Beach``, ``entities:497``, …
    Unknown kind prefixes are ignored. Empty / whitespace → None (full import).
    """
    if not raw or not str(raw).strip():
        return None
    kinds_set: set[str] = set()
    items_h: str | None = None
    locations_s: str | None = None
    biomes_s: str | None = None
    entities_s: str | None = None
    skins_s: str | None = None
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            base, _, sub = part.partition(":")
            base_l = base.strip().lower()
            sub = sub.strip()
            if not base_l or not sub:
                continue
            if base_l not in SUPPORTED_IMPORT_KINDS:
                continue
            kinds_set.add(base_l)
            if base_l == "items":
                items_h = sub
            elif base_l == "locations":
                locations_s = sub
            elif base_l == "biomes":
                biomes_s = sub
            elif base_l == "entities":
                entities_s = sub
            elif base_l == "skins":
                skins_s = sub
        else:
            kinds_set.add(part.lower())
    if not kinds_set:
        return None
    return KindImportSelection(
        frozenset(kinds_set),
        items_h,
        locations_s,
        biomes_s,
        entities_s,
        skins_s,
    )


def _item_has_type_hierarchy_value(item: dict[str, Any], needle: str) -> bool:
    for h in item.get("TypeHierarchy") or []:
        if str(h) == needle:
            return True
    return False


def _item_matches_spec(item: dict[str, Any], spec: str) -> bool:
    """``items:`` subfilter: numeric spec → Id; otherwise exact TypeHierarchy string match."""
    spec = (spec or "").strip()
    if not spec:
        return True
    if spec.isdigit():
        try:
            return int(item.get("Id")) == int(spec)
        except (TypeError, ValueError):
            return False
    return _item_has_type_hierarchy_value(item, spec)


def _skin_matches_spec(skin: dict[str, Any], spec: str) -> bool:
    spec = (spec or "").strip()
    if not spec:
        return True
    if spec.isdigit():
        try:
            return int(skin.get("Id")) == int(spec)
        except (TypeError, ValueError):
            return False
    return str(skin.get("Name") or "") == spec


def _entity_matches_spec(go: dict[str, Any], spec: str) -> bool:
    spec = (spec or "").strip()
    if not spec:
        return True
    if spec.isdigit():
        try:
            return int(go.get("Id")) == int(spec)
        except (TypeError, ValueError):
            return False
    return str(go.get("Name") or "") == spec


def _location_matches_spec(loc: dict[str, Any], spec: str) -> bool:
    """``locations:`` subfilter: numeric spec → Id; otherwise exact location Name (spaces allowed)."""
    spec = (spec or "").strip()
    if not spec:
        return True
    if spec.isdigit():
        try:
            return int(loc.get("Id")) == int(spec)
        except (TypeError, ValueError):
            return False
    return str(loc.get("Name") or "") == spec


def _biome_matches_spec(biome: dict[str, Any], spec: str) -> bool:
    """``biomes:`` subfilter: numeric spec → Id; otherwise exact biome Name (spaces allowed)."""
    spec = (spec or "").strip()
    if not spec:
        return True
    if spec.isdigit():
        try:
            return int(biome.get("Id")) == int(spec)
        except (TypeError, ValueError):
            return False
    return str(biome.get("Name") or "") == spec


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def read_last_version() -> str | None:
    ensure_dirs()
    if not LAST_VERSION_PATH.exists():
        return None
    try:
        data = json.loads(LAST_VERSION_PATH.read_text(encoding="utf-8"))
        return data.get("version")
    except (json.JSONDecodeError, OSError):
        return None


def write_last_version(version: str) -> None:
    ensure_dirs()
    LAST_VERSION_PATH.write_text(
        json.dumps({"version": version}, indent=2),
        encoding="utf-8",
    )


def _as_int_set(vals: Any) -> set[int]:
    if not isinstance(vals, list):
        return set()
    out: set[int] = set()
    for v in vals:
        try:
            out.add(int(v))
        except (TypeError, ValueError):
            continue
    return out


def _as_str_set(vals: Any) -> set[str]:
    """Normalized lowercase strings for case-insensitive matching (e.g. chest kind enums)."""
    if not isinstance(vals, list):
        return set()
    out: set[str] = set()
    for v in vals:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            out.add(s.lower())
    return out


def _chest_info_entry_kind_key(ci: dict[str, Any]) -> str | None:
    """Datadump ChestInfo: prefer ChestKind, then Kind (string enum from game)."""
    for key in ("ChestKind", "Kind"):
        v = ci.get(key)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s.lower()
    return None


def apply_skip_chest_kinds_to_game_objects(
    game_objects: list[dict[str, Any]],
    skip_kinds: set[str],
) -> None:
    """Drop ChestInfo rows whose kind is in skip_kinds (entries without kind are kept)."""
    if not skip_kinds:
        return
    for go in game_objects:
        raw = go.get("ChestInfo")
        if not isinstance(raw, list) or not raw:
            continue
        kept: list[dict[str, Any]] = []
        for ci in raw:
            if not isinstance(ci, dict):
                continue
            k = _chest_info_entry_kind_key(ci)
            if k is not None and k in skip_kinds:
                continue
            kept.append(ci)
        go["ChestInfo"] = kept


def load_overrides() -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "skip": {
            "items": set(),
            "locations": set(),
            "entities": set(),
            "biomes": set(),
            "skins": set(),
            "badges": set(),
            "achievements": set(),
            "quests": set(),
            "chest_kinds": set(),
        },
        "unreleased": {
            "items": set(),
            "locations": set(),
            "entities": set(),
            "biomes": set(),
            "skins": set(),
            "badges": set(),
            "achievements": set(),
            "quests": set(),
        },
        "show_hidden_achievements": set(),
    }
    if not WIKI_OVERRIDES_PATH.exists():
        return defaults
    try:
        raw = json.loads(WIKI_OVERRIDES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return defaults
    for section in ("skip", "unreleased"):
        block = raw.get(section) if isinstance(raw, dict) else None
        if not isinstance(block, dict):
            continue
        for kind in ("items", "locations", "entities", "biomes", "skins", "badges", "achievements", "quests"):
            defaults[section][kind] = _as_int_set(block.get(kind))
    if isinstance(raw, dict):
        skip_block = raw.get("skip")
        if isinstance(skip_block, dict) and "chest_kinds" in skip_block:
            defaults["skip"]["chest_kinds"] = _as_str_set(skip_block.get("chest_kinds"))
    if isinstance(raw, dict) and "show_hidden_achievements" in raw:
        defaults["show_hidden_achievements"] = _as_int_set(raw.get("show_hidden_achievements"))
    return defaults


def _warn_missing_layout_templates(site: pywikibot.Site, log) -> None:
    """If layout templates are missing, item pages show raw {{PQ Item|...}} instead of rendering."""
    for short in (
        "PQ Item",
        "PQ Entity",
        "PQ Location",
        "PQ Biome",
        "PQ Skin",
        "PQ Badge",
        "PQ Achievement",
        "PQ Quest",
    ):
        title = f"Template:{short}"
        p = pywikibot.Page(site, title)
        try:
            exists = p.exists()
        except Exception as e:
            log.warning("Could not check %s: %s", title, e)
            continue
        if not exists:
            log.warning(
                "MISSING %s — article pages will show unexpanded {{%s|...}} until you create it "
                "(copy from mediawiki/wiki_templates/). See mediawiki/TEMPLATES.md",
                title,
                short,
            )


def _with_unreleased_namespace(title: str, unreleased: bool) -> str:
    if not unreleased:
        return title
    if title.startswith("Unreleased:"):
        return title
    return f"Unreleased:{title}"


def run_import(
    datadump_path: Path,
    force: bool = False,
    *,
    dry_run: bool = False,
    kind_selection: KindImportSelection | None = None,
) -> dict[str, Any]:
    log = get_import_logger()
    ensure_dirs()
    data = load_json(datadump_path)
    version = data.get("Version")
    if not version:
        raise ValueError("Datadump missing Version field")

    datadump_sha256 = sha256_file(datadump_path)
    render_fp = compute_render_fingerprint()
    prev = read_last_version()
    effective_force = force or FORCE_OVERWRITE
    selected_kinds: set[str] | None = None
    items_hierarchy_filter: str | None = None
    locations_spec_filter: str | None = None
    entities_spec_filter: str | None = None
    skins_spec_filter: str | None = None
    biomes_spec_filter: str | None = None
    if kind_selection is not None:
        bad = kind_selection.kinds - SUPPORTED_IMPORT_KINDS
        if bad:
            raise ValueError(
                f"Unsupported kind(s) in selection: {sorted(bad)}. "
                f"Supported: {sorted(SUPPORTED_IMPORT_KINDS)}"
            )
        if not kind_selection.kinds:
            raise ValueError("kind_selection.kinds is empty")
        selected_kinds = set(kind_selection.kinds)
        items_hierarchy_filter = kind_selection.items_hierarchy
        locations_spec_filter = kind_selection.locations_spec
        biomes_spec_filter = kind_selection.biomes_spec
        entities_spec_filter = kind_selection.entities_spec
        skins_spec_filter = kind_selection.skins_spec
    scoped_run = kind_selection is not None and (
        selected_kinds != set(SUPPORTED_IMPORT_KINDS)
        or items_hierarchy_filter is not None
        or locations_spec_filter is not None
        or biomes_spec_filter is not None
        or entities_spec_filter is not None
        or skins_spec_filter is not None
    )

    if effective_force:
        log.info(
            "Force overwrite enabled (--force, ingest ?force_overwrite=1, or FORCE_OVERWRITE=1): "
            "overriding same-version guard and page ownership checks",
        )
    if selected_kinds is not None:
        log.info(
            "Scoped import kinds: %s (items_hierarchy=%r locations_spec=%r biomes_spec=%r "
            "entities_spec=%r skins_spec=%r)",
            sorted(selected_kinds),
            items_hierarchy_filter,
            locations_spec_filter,
            biomes_spec_filter,
            entities_spec_filter,
            skins_spec_filter,
        )

    textures_map: dict[str, object] = (
        data["Textures"] if isinstance(data.get("Textures"), dict) else {}
    )

    log.info("Starting import datadump version=%s (previous=%s)", version, prev)
    from pq_wiki.config import ROBLOX_COOKIE
    log.info("ROBLOX_COOKIE set=%s (required for textures)", bool(ROBLOX_COOKIE))

    site = pywikibot.Site("en", "pqwiki")
    pywikibot.config.verbose_output = os.environ.get("PQ_BOT_VERBOSE", "").lower() in (
        "1",
        "true",
        "yes",
    )
    t_login = time.perf_counter()
    site.login()
    log.info("Wiki login OK (%.0f ms)", (time.perf_counter() - t_login) * 1000)
    try:
        log.info(
            "Wiki target (must match the site you open in the browser): %s",
            site,
        )
    except Exception:
        pass

    if not dry_run:
        ensure_pixel_art_css(site)
        ensure_loot_chest_toc_css(site)
    _warn_missing_layout_templates(site, log)

    items = data.get("Items") or []
    locations = data.get("Locations") or []
    biomes_raw = data.get("Biomes") or []
    biomes = [b for b in biomes_raw if isinstance(b, dict) and b.get("Id") is not None]
    game_objects = data.get("GameObjects") or []
    account_stats = data.get("AccountStats") or []
    overrides = load_overrides()
    skip_items = overrides["skip"]["items"]
    skip_locations = overrides["skip"]["locations"]
    skip_entities = overrides["skip"]["entities"]
    skip_biomes = overrides["skip"]["biomes"]
    skip_skins = overrides["skip"]["skins"]
    skip_badges = overrides["skip"]["badges"]
    skip_achievements = overrides["skip"]["achievements"]
    skip_quests = overrides["skip"]["quests"]
    skip_chest_kinds = overrides["skip"]["chest_kinds"]
    unreleased_items = overrides["unreleased"]["items"]
    unreleased_locations = overrides["unreleased"]["locations"]
    unreleased_entities = overrides["unreleased"]["entities"]
    unreleased_biomes = overrides["unreleased"]["biomes"]
    unreleased_skins = overrides["unreleased"]["skins"]
    unreleased_badges = overrides["unreleased"]["badges"]
    unreleased_achievements = overrides["unreleased"]["achievements"]
    unreleased_quests = overrides["unreleased"]["quests"]
    show_hidden_achievements = overrides.get("show_hidden_achievements") or set()

    items = [it for it in items if int(it.get("Id", -1)) not in skip_items]
    locations = [loc for loc in locations if int(loc.get("Id", -1)) not in skip_locations]
    biomes = [b for b in biomes if int(b.get("Id", -1)) not in skip_biomes]
    game_objects = [
        go
        for go in game_objects
        if (not go.get("IsEntity", True)) or int(go.get("Id", -1)) not in skip_entities
    ]
    apply_skip_chest_kinds_to_game_objects(game_objects, skip_chest_kinds)
    character_skins = data.get("CharacterSkins") or []
    character_skins = [s for s in character_skins if int(s.get("Id", -1)) not in skip_skins]

    badges_raw = data.get("Badges") or []
    if not isinstance(badges_raw, list):
        badges_raw = []
    badges = [b for b in badges_raw if isinstance(b, dict) and int(b.get("Id", -1)) not in skip_badges]

    achievements_raw = data.get("Achievements") or []
    if not isinstance(achievements_raw, list):
        achievements_raw = []
    achievements: list[dict[str, Any]] = []
    for a in achievements_raw:
        if not isinstance(a, dict):
            continue
        aid = int(a.get("Id", -1))
        if aid in skip_achievements:
            continue
        hid = bool(a.get("IsHidden") or a.get("isHidden"))
        if hid and aid not in show_hidden_achievements:
            continue
        achievements.append(a)

    quests_raw = data.get("Quests") or []
    if not isinstance(quests_raw, list):
        quests_raw = []
    quests: list[dict[str, Any]] = []
    for q in quests_raw:
        if not isinstance(q, dict):
            continue
        qid = int(q.get("Id", -1))
        if qid in skip_quests:
            continue
        quests.append(q)

    status_effects_raw = data.get("StatusEffects") or []
    if not isinstance(status_effects_raw, list):
        status_effects_raw = []
    status_effects_rows: list[dict[str, Any]] = [
        s for s in status_effects_raw if isinstance(s, dict) and int(s.get("Id", -1)) >= 0
    ]

    achievement_categories = data.get("AchievementCategories")
    achievement_series = data.get("AchievementSeries")
    achievement_groups = data.get("AchievementGroups")
    if not isinstance(achievement_categories, dict):
        achievement_categories = None
    if not isinstance(achievement_series, dict):
        achievement_series = None
    if not isinstance(achievement_groups, dict):
        achievement_groups = None

    quest_categories = data.get("QuestCategories")
    if not isinstance(quest_categories, dict):
        quest_categories = None

    log.info(
        "Overrides loaded: skip(items=%d,locations=%d,entities=%d,skins=%d,badges=%d,achievements=%d,quests=%d,"
        "chest_kinds=%d) "
        "unreleased(items=%d,locations=%d,entities=%d,skins=%d,badges=%d,achievements=%d,quests=%d) "
        "show_hidden_achievements=%d",
        len(skip_items),
        len(skip_locations),
        len(skip_entities),
        len(skip_skins),
        len(skip_badges),
        len(skip_achievements),
        len(skip_quests),
        len(skip_chest_kinds),
        len(unreleased_items),
        len(unreleased_locations),
        len(unreleased_entities),
        len(unreleased_skins),
        len(unreleased_badges),
        len(unreleased_achievements),
        len(unreleased_quests),
        len(show_hidden_achievements),
    )

    stat_icons = build_stat_icon_wikitext_map(site, data, version)
    log.info("Stat icons ready: %d", len(stat_icons))
    status_effect_icons = build_status_effect_icon_wikitext_map(site, data, version)
    log.info("Status effect icons ready: %d", len(status_effect_icons))
    valor_icon_wikitext = build_valor_icon_wikitext(site, data, version)
    log.info("Valor icon ready: %s", bool(valor_icon_wikitext))
    honor_icon_map = build_honor_icon_wikitext_map(site, data, version)
    log.info("Honor icons ready: %d", len(honor_icon_map))
    drop_tiers = {int((it.get("DropTierType") or 0)) for it in items}
    if character_skins:
        # Skin drops group as tier 6 (other legendaries); ensure icons exist even if no item uses 6.
        drop_tiers = drop_tiers | {6}
    drop_tier_icons = build_drop_tier_wikitext_map(site, data, version, drop_tiers)
    drop_tier_icon_parts = build_drop_tier_icon_parts_map(site, data, version, drop_tiers)
    log.info("Drop tier icons ready: %d", len(drop_tier_icons))
    skin_rarities = {int((s.get("Rarity") or 0)) for s in character_skins}
    skin_rarity_icon_wikitext = build_skin_rarity_wikitext_map(site, data, version, skin_rarities)
    log.info("Skin rarity icons ready: %d", len(skin_rarity_icon_wikitext))
    difficulty_skull_icon = build_difficulty_skull_wikitext(site, data, version, size_px=40)

    nlim = GENERATE_FEW_PAGES_LIMIT
    items_to_process = items[:nlim] if nlim else items
    locations_to_process = locations[:nlim] if nlim else locations
    all_entities = [go for go in game_objects if go.get("IsEntity", True)]
    entities_to_process = all_entities[:nlim] if nlim else all_entities
    biomes_to_process = biomes[:nlim] if nlim else biomes
    skins_to_process = character_skins[:nlim] if nlim else character_skins
    account_stats_to_process = account_stats[:nlim] if nlim else account_stats
    badges_to_process = badges[:nlim] if nlim else badges
    achievements_to_process = achievements[:nlim] if nlim else achievements
    quests_to_process = quests[:nlim] if nlim else quests

    if nlim:
        log.info(
            "GENERATE_FEW_PAGES cap %d per type: importing %d items, %d locations, %d biomes, "
            "%d entities, %d skins, %d account stats, %d quests (status effects: always one combined index, %d sections)",
            nlim,
            len(items_to_process),
            len(locations_to_process),
            len(biomes_to_process),
            len(entities_to_process),
            len(skins_to_process),
            len(account_stats_to_process),
            len(quests_to_process),
            len(status_effects_rows),
        )

    item_name_to_id: dict[str, int] = {}
    for it in items:
        n = it.get("Name")
        if n:
            item_name_to_id[n] = it["Id"]

    # Slugs are unique within each namespace; unreleased pages live under Unreleased:.
    used_paths_public: set[str] = set()
    used_paths_unreleased: set[str] = set()
    item_id_to_path: dict[int, str] = {}
    for it in sorted(items, key=lambda x: x["Id"]):
        iid = int(it["Id"])
        is_unreleased = iid in unreleased_items
        used = used_paths_unreleased if is_unreleased else used_paths_public
        base = item_page_path(it, used)
        item_id_to_path[iid] = _with_unreleased_namespace(base, is_unreleased)
    item_id_to_item: dict[int, dict[str, Any]] = {int(it["Id"]): it for it in items}

    go_name_to_id: dict[str, int] = {}
    location_id_to_path: dict[int, str] = {}
    for loc in sorted(locations, key=lambda x: x["Id"]):
        lid = int(loc["Id"])
        is_unreleased = lid in unreleased_locations
        used = used_paths_unreleased if is_unreleased else used_paths_public
        base = location_page_path(loc, used)
        location_id_to_path[lid] = _with_unreleased_namespace(base, is_unreleased)
    location_name_to_path: dict[str, str] = {}
    for loc in locations:
        lname = loc.get("Name")
        if lname and loc.get("Id") in location_id_to_path:
            location_name_to_path[str(lname)] = location_id_to_path[loc["Id"]]

    location_id_to_loc: dict[int, dict[str, Any]] = {}
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        lid = loc.get("Id")
        if lid is None:
            continue
        try:
            location_id_to_loc[int(lid)] = loc
        except (TypeError, ValueError):
            continue

    location_name_to_portal: dict[str, dict[str, Any]] = {}
    for loc in locations:
        lname = str(loc.get("Name") or "")
        if not lname:
            continue
        ps = loc.get("PortalSprite")
        if isinstance(ps, dict) and ps:
            location_name_to_portal[lname] = ps

    entity_name_to_locations: dict[str, list[str]] = {}
    for loc in locations:
        lname = str(loc.get("Name") or "")
        if not lname:
            continue
        lpath = location_id_to_path.get(loc.get("Id"))
        if not lpath:
            continue
        for go_name in (loc.get("FoundGameObjects") or []):
            if not go_name:
                continue
            k = str(go_name)
            entity_name_to_locations.setdefault(k, [])
            if lname not in entity_name_to_locations[k]:
                entity_name_to_locations[k].append(lname)

    entity_id_to_path: dict[int, str] = {}
    entities_sorted = sorted(
        (go for go in game_objects if go.get("IsEntity", True)),
        key=lambda x: x["Id"],
    )
    for go in game_objects:
        n = go.get("Name")
        if n:
            go_name_to_id[n] = go["Id"]
    entity_name_to_go: dict[str, dict[str, Any]] = {}
    for go in entities_sorted:
        n = go.get("Name")
        if n:
            entity_name_to_go[str(n)] = go
    for go in entities_sorted:
        gid = int(go["Id"])
        is_unreleased = gid in unreleased_entities
        used = used_paths_unreleased if is_unreleased else used_paths_public
        base = entity_page_path(go, used)
        entity_id_to_path[gid] = _with_unreleased_namespace(base, is_unreleased)

    biome_id_to_path: dict[int, str] = {}
    for bio in sorted(biomes, key=lambda x: int(x["Id"])):
        bid = int(bio["Id"])
        base = biome_page_path(bio, used_paths_public)
        biome_id_to_path[bid] = base

    biomes_by_id: dict[int, dict[str, Any]] = {}
    for b in biomes:
        if not isinstance(b, dict) or b.get("Id") is None:
            continue
        try:
            biomes_by_id[int(b["Id"])] = b
        except (TypeError, ValueError):
            continue

    biome_name_to_path: dict[str, str] = {}
    biome_name_to_biome: dict[str, dict[str, Any]] = {}
    for b in biomes:
        if not isinstance(b, dict):
            continue
        nm = b.get("Name")
        if nm is None:
            continue
        ns = str(nm)
        bid_raw = b.get("Id")
        if bid_raw is None:
            continue
        try:
            bid_i = int(bid_raw)
        except (TypeError, ValueError):
            continue
        bp = biome_id_to_path.get(bid_i)
        if bp and ns not in biome_name_to_path:
            biome_name_to_path[ns] = bp
        if ns not in biome_name_to_biome:
            biome_name_to_biome[ns] = b

    biome_name_to_event_entity_names: dict[str, list[str]] = {}
    for go in entities_sorted:
        ename = str(go.get("Name") or "").strip()
        if not ename:
            continue
        for raw_b in go.get("EventBiomes") or []:
            bn = str(raw_b).strip()
            if not bn:
                continue
            biome_name_to_event_entity_names.setdefault(bn, [])
            if ename not in biome_name_to_event_entity_names[bn]:
                biome_name_to_event_entity_names[bn].append(ename)

    item_drop_sources = build_item_id_to_drop_sources(
        game_objects,
        item_name_to_id,
        item_id_to_item,
        entity_id_to_path,
    )
    log.info("Item drop sources: %d items with at least one enemy source", len(item_drop_sources))
    entity_id_to_go: dict[int, dict[str, Any]] = {
        int(go["Id"]): go for go in game_objects if go.get("IsEntity", True)
    }

    skin_id_to_path: dict[int, str] = {}
    for sk in sorted(character_skins, key=lambda x: x["Id"]):
        sid = int(sk["Id"])
        is_unreleased = sid in unreleased_skins
        used = used_paths_unreleased if is_unreleased else used_paths_public
        base = skin_page_path(sk, used)
        skin_id_to_path[sid] = _with_unreleased_namespace(base, is_unreleased)
    skin_id_to_skin: dict[int, dict[str, Any]] = {int(s["Id"]): s for s in character_skins}

    account_stat_id_to_path: dict[int, str] = {}
    for st in sorted(account_stats, key=lambda x: x["Id"]):
        sid = int(st["Id"])
        base = account_stat_page_path(st, used_paths_public)
        account_stat_id_to_path[sid] = base

    badge_id_to_path: dict[int, str] = {}
    for b in sorted(badges, key=lambda x: int(x["Id"])):
        bid = int(b["Id"])
        is_unreleased = bid in unreleased_badges
        used = used_paths_unreleased if is_unreleased else used_paths_public
        base = badge_page_path(b, used)
        badge_id_to_path[bid] = _with_unreleased_namespace(base, is_unreleased)

    achievement_id_to_path: dict[int, str] = {}
    for ach in sorted(achievements, key=lambda x: int(x["Id"])):
        aid = int(ach["Id"])
        is_unreleased = aid in unreleased_achievements
        used = used_paths_unreleased if is_unreleased else used_paths_public
        base = achievement_page_path(ach, used)
        achievement_id_to_path[aid] = _with_unreleased_namespace(base, is_unreleased)

    quest_id_to_path: dict[int, str] = {}
    for qu in sorted(quests, key=lambda x: int(x["Id"])):
        qid = int(qu["Id"])
        is_unreleased = qid in unreleased_quests
        used = used_paths_unreleased if is_unreleased else used_paths_public
        base = quest_page_path(qu, used)
        quest_id_to_path[qid] = _with_unreleased_namespace(base, is_unreleased)

    status_effect_name_to_path = build_status_effect_name_to_path_map(status_effects_rows)

    badges_for_diff = [b for b in badges_raw if isinstance(b, dict) and int(b.get("Id", 0)) >= 0]
    achievements_for_diff = [
        a for a in achievements_raw if isinstance(a, dict) and int(a.get("Id", 0)) >= 0
    ]
    quests_for_diff = [
        q for q in quests_raw if isinstance(q, dict) and int(q.get("Id", 0)) >= 0
    ]

    old_cached = load_cached_datadump()
    last_state = read_last_import_state() or {}
    ci: set[int] = set()
    cl: set[int] = set()
    cbi: set[int] = set()
    ce: set[int] = set()
    cs: set[int] = set()
    cb: set[int] = set()
    ca: set[int] = set()
    cq: set[int] = set()
    cfx: set[int] = set()
    import_full = (
        old_cached is None
        or last_state.get("render_fingerprint") != render_fp
        or os.environ.get("PQ_IMPORT_FULL", "").strip().lower() in ("1", "true", "yes")
        or force
    )
    if import_full:
        log.info(
            "Full wiki rebuild (no/partial cache, render fingerprint changed, PQ_IMPORT_FULL, or --force)",
        )
    else:
        ci, cl, cbi, ce, cs, cb, ca, cq, cfx = compute_incremental_sets(
            old_data=old_cached,
            new_items=items,
            new_locations=locations,
            new_biomes=biomes,
            new_game_objects=game_objects,
            new_character_skins=character_skins,
            new_badges=badges_for_diff,
            new_achievements=achievements_for_diff,
            new_quests=quests_for_diff,
            new_status_effects=status_effects_rows,
            unreleased_entities=unreleased_entities,
        )
        log.info(
            "Incremental scope: %d items, %d locations, %d biomes, %d entities, %d skins, %d badges, "
            "%d achievements, %d quests, %d status effect rows changed (index page if any)",
            len(ci),
            len(cl),
            len(cbi),
            len(ce),
            len(cs),
            len(cb),
            len(ca),
            len(cq),
            len(cfx),
        )
        if not ci and not cl and not cbi and not ce and not cs and not cb and not ca and not cq and not cfx:
            log.info("Incremental diff: no page updates needed (wikitext would be unchanged)")

    stats: dict[str, int] = {}
    errors: list[str] = []

    def _work_list(
        rows: list[dict[str, Any]],
        id_set: set[int],
    ) -> list[dict[str, Any]]:
        if import_full:
            return rows
        return [r for r in rows if int(r["Id"]) in id_set]

    items_work = _work_list(items_to_process, ci)
    locations_work = _work_list(locations_to_process, cl)
    biomes_work = _work_list(biomes_to_process, cbi)
    entities_work = _work_list(entities_to_process, ce)
    skins_work = _work_list(skins_to_process, cs)
    # Keep account stats fully refreshed; list is small and currently outside incremental diff sets.
    account_stats_work = account_stats_to_process
    badges_work = _work_list(badges_to_process, cb)
    achievements_work = _work_list(achievements_to_process, ca)
    quests_work = _work_list(quests_to_process, cq)

    if selected_kinds is not None:
        if "items" not in selected_kinds:
            items_work = []
        if "locations" not in selected_kinds:
            locations_work = []
        if "biomes" not in selected_kinds:
            biomes_work = []
        if "entities" not in selected_kinds:
            entities_work = []
        if "skins" not in selected_kinds:
            skins_work = []
        if "account_stats" not in selected_kinds:
            account_stats_work = []
        if "badges" not in selected_kinds:
            badges_work = []
        if "achievements" not in selected_kinds:
            achievements_work = []
        if "quests" not in selected_kinds:
            quests_work = []

    if items_hierarchy_filter and (selected_kinds is None or "items" in selected_kinds):
        items_work = [
            it for it in items_to_process if _item_matches_spec(it, items_hierarchy_filter)
        ]
        log.info(
            "Item filter %r → %d items (ignores incremental item diff)",
            items_hierarchy_filter,
            len(items_work),
        )
    if locations_spec_filter and (selected_kinds is None or "locations" in selected_kinds):
        locations_work = [
            loc for loc in locations_to_process if _location_matches_spec(loc, locations_spec_filter)
        ]
        log.info(
            "Location filter %r → %d locations (ignores incremental location diff)",
            locations_spec_filter,
            len(locations_work),
        )
    if biomes_spec_filter and (selected_kinds is None or "biomes" in selected_kinds):
        biomes_work = [
            b for b in biomes_to_process if _biome_matches_spec(b, biomes_spec_filter)
        ]
        log.info(
            "Biome filter %r → %d biomes (ignores incremental biome diff)",
            biomes_spec_filter,
            len(biomes_work),
        )
    if skins_spec_filter and (selected_kinds is None or "skins" in selected_kinds):
        skins_work = [s for s in skins_to_process if _skin_matches_spec(s, skins_spec_filter)]
        log.info(
            "Skin filter %r → %d skins (ignores incremental skin diff)",
            skins_spec_filter,
            len(skins_work),
        )
    if entities_spec_filter and (selected_kinds is None or "entities" in selected_kinds):
        entities_work = [
            go for go in entities_to_process if _entity_matches_spec(go, entities_spec_filter)
        ]
        log.info(
            "Entity filter %r → %d entities (ignores incremental entity diff)",
            entities_spec_filter,
            len(entities_work),
        )

    def _one(
        kind: str,
        title: str,
        build,
        save,
        *,
        progress: str | None = None,
    ) -> None:
        t0 = time.perf_counter()
        prefix = f"[{progress}] " if progress else ""
        try:
            skip = peek_skip_build_reason(site, title, WIKI_BOT_USER, effective_force)
            if skip:
                t1 = time.perf_counter()
                stats[skip] = stats.get(skip, 0) + 1
                log.info(
                    "%s%s %s | result=%s | build=%.0fms save=%.0fms total=%.0fms",
                    prefix,
                    kind,
                    title,
                    skip,
                    (t1 - t0) * 1000,
                    0.0,
                    (t1 - t0) * 1000,
                )
                return
            w = build()
            t1 = time.perf_counter()
            r = save(site, title, w, version, WIKI_BOT_USER, kind)
            t2 = time.perf_counter()
            build_ms = (t1 - t0) * 1000
            save_ms = (t2 - t1) * 1000
            stats[r] = stats.get(r, 0) + 1
            log.info(
                "%s%s %s | result=%s | build=%.0fms save=%.0fms total=%.0fms",
                prefix,
                kind,
                title,
                r,
                build_ms,
                save_ms,
                (t2 - t0) * 1000,
            )
        except Exception:
            errors.append(f"{kind} {title}")
            log.error("FAILED %s%s %s\n%s", prefix, kind, title, traceback.format_exc())

    if (import_full or cfx) and (selected_kinds is None or "status_effects" in selected_kinds):
        def build_status_effects_index():
            return build_status_effects_index_wikitext(site, status_effects_rows, data, version)

        def save_status_index(s, ttl, txt, ver, user, k):
            return save_bot_page(s, ttl, txt, ver, user, k, force_overwrite=effective_force)

        _one(
            "status_effects_index",
            STATUS_EFFECTS_INDEX_TITLE,
            build_status_effects_index,
            save_status_index,
        )

    n_items = len(items_work)
    for idx, it in enumerate(items_work, start=1):
        path = item_id_to_path[it["Id"]]
        name = it.get("Name", it["Id"])

        def build_item(i=it):
            return build_item_wikitext(
                site,
                i,
                version,
                stat_icons=stat_icons,
                drop_tier_icons=drop_tier_icons,
                unreleased=int(i["Id"]) in unreleased_items,
                drop_sources=item_drop_sources.get(int(i["Id"]), []),
                entity_id_to_go=entity_id_to_go,
                item_name_to_id=item_name_to_id,
                item_id_to_path=item_id_to_path,
                item_id_to_item=item_id_to_item,
                location_name_to_path=location_name_to_path,
                location_name_to_portal=location_name_to_portal,
                go_name_to_id=go_name_to_id,
                entity_id_to_path=entity_id_to_path,
                status_effect_icons=status_effect_icons,
                status_effect_name_to_path=status_effect_name_to_path,
                valor_icon_wikitext=valor_icon_wikitext,
                game_textures=textures_map,
            )

        def save_item(s, ttl, txt, ver, user, k):
            return save_bot_page(s, ttl, txt, ver, user, k, force_overwrite=effective_force)

        _one(
            "item",
            path,
            build_item,
            save_item,
            progress=f"{idx}/{n_items}",
        )

    n_locs = len(locations_work)
    for idx, loc in enumerate(locations_work, start=1):
        path = location_id_to_path[loc["Id"]]
        name = loc.get("Name", loc["Id"])

        def build_loc(l=loc):
            return build_location_wikitext(
                site,
                l,
                version,
                item_name_to_id,
                item_id_to_path,
                go_name_to_id,
                entity_id_to_path,
                entity_name_to_go=entity_name_to_go,
                item_id_to_item=item_id_to_item,
                difficulty_skull_icon=difficulty_skull_icon,
                unreleased=int(l["Id"]) in unreleased_locations,
            )

        def save_loc(s, ttl, txt, ver, user, k):
            return save_bot_page(s, ttl, txt, ver, user, k, force_overwrite=effective_force)

        _one(
            "location",
            path,
            build_loc,
            save_loc,
            progress=f"{idx}/{n_locs}",
        )

    n_biomes = len(biomes_work)
    for idx, bio in enumerate(biomes_work, start=1):
        path = biome_id_to_path[int(bio["Id"])]

        def build_biome(b=bio):
            bnm = str(b.get("Name") or "")
            extras = list(biome_name_to_event_entity_names.get(bnm, []))
            return build_biome_wikitext(
                site,
                b,
                version,
                go_name_to_id,
                entity_id_to_path,
                entity_name_to_go=entity_name_to_go,
                location_name_to_path=location_name_to_path,
                difficulty_skull_icon=difficulty_skull_icon,
                extra_found_entity_names=extras,
            )

        def save_biome(s, ttl, txt, ver, user, k):
            return save_bot_page(s, ttl, txt, ver, user, k, force_overwrite=effective_force)

        _one(
            "biome",
            path,
            build_biome,
            save_biome,
            progress=f"{idx}/{n_biomes}",
        )

    n_entities = len(entities_work)
    for idx, go in enumerate(entities_work, start=1):
        path = entity_id_to_path[go["Id"]]
        name = go.get("Name", go["Id"])

        def build_go(g=go):
            return build_entity_wikitext(
                site,
                g,
                version,
                item_name_to_id,
                item_id_to_path,
                item_id_to_item,
                go_name_to_id,
                entity_id_to_path,
                location_name_to_path=location_name_to_path,
                location_name_to_portal=location_name_to_portal,
                entity_name_to_locations=entity_name_to_locations,
                biome_name_to_path=biome_name_to_path,
                biome_name_to_biome=biome_name_to_biome,
                drop_tier_icon_parts=drop_tier_icon_parts,
                stat_icons=stat_icons,
                status_effect_icons=status_effect_icons,
                status_effect_name_to_path=status_effect_name_to_path,
                unreleased=int(g["Id"]) in unreleased_entities,
                entity_id_to_go=entity_id_to_go,
                skin_id_to_skin=skin_id_to_skin,
                skin_id_to_path=skin_id_to_path,
                skin_rarity_icon_wikitext=skin_rarity_icon_wikitext,
                game_textures=textures_map,
            )

        def save_ent(s, ttl, txt, ver, user, k):
            return save_bot_page(s, ttl, txt, ver, user, k, force_overwrite=effective_force)

        _one(
            "entity",
            path,
            build_go,
            save_ent,
            progress=f"{idx}/{n_entities}",
        )

    n_skins = len(skins_work)
    for idx, sk in enumerate(skins_work, start=1):
        path = skin_id_to_path[int(sk["Id"])]
        name = sk.get("Name", sk["Id"])

        def build_skin(s=sk):
            return build_skin_wikitext(
                site,
                s,
                version,
                unreleased=int(s["Id"]) in unreleased_skins,
            )

        def save_skin(s, ttl, txt, ver, user, k):
            return save_bot_page(s, ttl, txt, ver, user, k, force_overwrite=effective_force)

        _one(
            "skin",
            path,
            build_skin,
            save_skin,
            progress=f"{idx}/{n_skins}",
        )

    n_account_stats = len(account_stats_work)
    for idx, st in enumerate(account_stats_work, start=1):
        path = account_stat_id_to_path[int(st["Id"])]

        def build_account_stat(s=st):
            return build_account_stat_wikitext(s, version)

        def save_account_stat(s, ttl, txt, ver, user, k):
            return save_bot_page(s, ttl, txt, ver, user, k, force_overwrite=effective_force)

        _one(
            "account_stat",
            path,
            build_account_stat,
            save_account_stat,
            progress=f"{idx}/{n_account_stats}",
        )

    n_badges = len(badges_work)
    for idx, bd in enumerate(badges_work, start=1):
        path = badge_id_to_path[int(bd["Id"])]

        def build_badge(b=bd):
            return build_badge_wikitext(
                site,
                b,
                version,
                unreleased=int(b["Id"]) in unreleased_badges,
            )

        def save_badge(s, ttl, txt, ver, user, k):
            return save_bot_page(s, ttl, txt, ver, user, k, force_overwrite=effective_force)

        _one(
            "badge",
            path,
            build_badge,
            save_badge,
            progress=f"{idx}/{n_badges}",
        )

    n_ach = len(achievements_work)
    for idx, ach in enumerate(achievements_work, start=1):
        path = achievement_id_to_path[int(ach["Id"])]
        wiki_hidden = bool(ach.get("IsHidden") or ach.get("isHidden"))

        def build_ach(a=ach, wh=wiki_hidden):
            return build_achievement_wikitext(
                site,
                a,
                data,
                version,
                item_id_to_path=item_id_to_path,
                item_id_to_item=item_id_to_item,
                item_name_to_id=item_name_to_id,
                items_list=items,
                stat_icons=stat_icons,
                valor_icon_wikitext=valor_icon_wikitext,
                honor_icon_map=honor_icon_map,
                location_id_to_path=location_id_to_path,
                location_name_to_path=location_name_to_path,
                location_id_to_loc=location_id_to_loc,
                achievement_categories=achievement_categories,
                achievement_series=achievement_series,
                achievement_groups=achievement_groups,
                wiki_hidden=wh,
                unreleased=int(a["Id"]) in unreleased_achievements,
            )

        def save_ach(s, ttl, txt, ver, user, k):
            return save_bot_page(s, ttl, txt, ver, user, k, force_overwrite=effective_force)

        _one(
            "achievement",
            path,
            build_ach,
            save_ach,
            progress=f"{idx}/{n_ach}",
        )

    n_qu = len(quests_work)
    for idx, qu in enumerate(quests_work, start=1):
        path = quest_id_to_path[int(qu["Id"])]

        def build_qu(q=qu):
            return build_quest_wikitext(
                site,
                q,
                data,
                version,
                quest_categories=quest_categories,
                item_id_to_path=item_id_to_path,
                item_id_to_item=item_id_to_item,
                item_name_to_id=item_name_to_id,
                items_list=items,
                stat_icons=stat_icons,
                valor_icon_wikitext=valor_icon_wikitext,
                honor_icon_map=honor_icon_map,
                location_id_to_path=location_id_to_path,
                location_name_to_path=location_name_to_path,
                location_id_to_loc=location_id_to_loc,
                entity_id_to_path=entity_id_to_path,
                entity_id_to_go=entity_id_to_go,
                biome_id_to_path=biome_id_to_path,
                biomes_by_id=biomes_by_id,
            )

        def save_qu(s, ttl, txt, ver, user, k):
            return save_bot_page(s, ttl, txt, ver, user, k, force_overwrite=effective_force)

        _one(
            "quest",
            path,
            build_qu,
            save_qu,
            progress=f"{idx}/{n_qu}",
        )

    if not errors and not dry_run and not scoped_run:
        write_cached_datadump(datadump_path)
        write_last_import_state(
            datadump_version=version,
            datadump_content_sha256=datadump_sha256,
            render_fingerprint=render_fp,
        )
        write_last_version(version)
    else:
        if errors:
            log.warning("Not updating cached datadump / import state because of errors")
        elif dry_run:
            log.info("Dry-run mode: not updating cached datadump / import state")
        elif scoped_run:
            log.info("Scoped import mode: not updating cached datadump / import state")
    log.info(
        "If saved edits do not appear: hard-refresh the tab, or open the article with "
        "?action=purge — MediaWiki and the browser both cache rendered HTML. "
        "Set PQ_IMPORT_LOG_LEVEL=DEBUG or PQ_IMPORT_VERBOSE_SAVE=1 for per-save revision details."
    )
    log.info(
        "Import finished version=%s stats=%s errors=%d",
        version,
        stats,
        len(errors),
    )
    if errors:
        log.warning("Pages with errors (first 20): %s", errors[:20])

    return {
        "ok": len(errors) == 0,
        "skipped": False,
        "version": version,
        "previous_version": prev,
        "stats": stats,
        "errors": errors,
        "import_full": import_full,
        "incremental_items": len(ci) if not import_full else None,
        "incremental_locations": len(cl) if not import_full else None,
        "incremental_biomes": len(cbi) if not import_full else None,
        "incremental_entities": len(ce) if not import_full else None,
        "incremental_quests": len(cq) if not import_full else None,
    }


def parse_import_cli_argv(argv: list[str]) -> tuple[list[str], str | None]:
    """
    Strip ``--edit-summary <text>`` from argv. Returns (remaining argv, summary or None).
    """
    out: list[str] = []
    edit_summary: str | None = None
    i = 0
    while i < len(argv):
        if argv[i] == "--edit-summary":
            if i + 1 >= len(argv):
                raise ValueError("--edit-summary requires a value")
            edit_summary = argv[i + 1]
            i += 2
            continue
        out.append(argv[i])
        i += 1
    return out, edit_summary


def main(argv: list[str]) -> int:
    try:
        argv, edit_summary = parse_import_cli_argv(list(argv))
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    if len(argv) < 2:
        print(
            "Usage: python -m pq_wiki import <pq-datadump.json> "
            "[--force] [--edit-summary \"...\"]",
            file=sys.stderr,
        )
        return 2
    path = Path(argv[1])
    force = "--force" in argv
    if not path.is_file():
        print(f"Not found: {path}", file=sys.stderr)
        return 1
    tok = push_edit_summary_override(edit_summary) if edit_summary is not None else None
    try:
        out = run_import(path, force=force)
    finally:
        if tok is not None:
            reset_edit_summary_override(tok)
    print(json.dumps(out, indent=2))
    return 0 if out.get("ok") else 1
