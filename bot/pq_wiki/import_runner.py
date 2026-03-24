from __future__ import annotations

import json
import os
import sys
import time
import traceback
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
    GENERATE_FEW_PAGES,
    LAST_VERSION_PATH,
    WIKI_OVERRIDES_PATH,
    WIKI_BOT_USER,
    ensure_dirs,
)
from pq_wiki.difficulty_icons import build_difficulty_skull_wikitext
from pq_wiki.import_log import get_import_logger
from pq_wiki.loot_tier_icons import build_drop_tier_icon_parts_map, build_drop_tier_wikitext_map
from pq_wiki.render_pages import (
    build_entity_wikitext,
    build_item_wikitext,
    build_location_wikitext,
    entity_page_path,
    item_page_path,
    location_page_path,
    save_bot_page,
)
from pq_wiki.stat_icons import build_stat_icon_wikitext_map
from pq_wiki.status_effect_icons import build_status_effect_icon_wikitext_map
from pq_wiki.wiki_assets import ensure_pixel_art_css


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


def load_overrides() -> dict[str, dict[str, set[int]]]:
    defaults = {
        "skip": {"items": set(), "locations": set(), "entities": set()},
        "unreleased": {"items": set(), "locations": set(), "entities": set()},
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
        for kind in ("items", "locations", "entities"):
            defaults[section][kind] = _as_int_set(block.get(kind))
    return defaults


def _with_unreleased_namespace(title: str, unreleased: bool) -> str:
    if not unreleased:
        return title
    if title.startswith("Unreleased:"):
        return title
    return f"Unreleased:{title}"


def run_import(datadump_path: Path, force: bool = False) -> dict[str, Any]:
    log = get_import_logger()
    ensure_dirs()
    data = load_json(datadump_path)
    version = data.get("Version")
    if not version:
        raise ValueError("Datadump missing Version field")

    prev = read_last_version()
    effective_force = force or FORCE_OVERWRITE
    if not effective_force and prev == version:
        log.info("Skip import: same datadump version %s", version)
        return {
            "ok": True,
            "skipped": True,
            "reason": "same_version",
            "version": version,
        }
    if FORCE_OVERWRITE:
        log.info("FORCE_OVERWRITE=1: overriding same-version guard and page ownership checks")

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

    ensure_pixel_art_css(site)

    items = data.get("Items") or []
    locations = data.get("Locations") or []
    game_objects = data.get("GameObjects") or []
    overrides = load_overrides()
    skip_items = overrides["skip"]["items"]
    skip_locations = overrides["skip"]["locations"]
    skip_entities = overrides["skip"]["entities"]
    unreleased_items = overrides["unreleased"]["items"]
    unreleased_locations = overrides["unreleased"]["locations"]
    unreleased_entities = overrides["unreleased"]["entities"]

    items = [it for it in items if int(it.get("Id", -1)) not in skip_items]
    locations = [loc for loc in locations if int(loc.get("Id", -1)) not in skip_locations]
    game_objects = [
        go
        for go in game_objects
        if (not go.get("IsEntity", True)) or int(go.get("Id", -1)) not in skip_entities
    ]
    log.info(
        "Overrides loaded: skip(items=%d,locations=%d,entities=%d) unreleased(items=%d,locations=%d,entities=%d)",
        len(skip_items),
        len(skip_locations),
        len(skip_entities),
        len(unreleased_items),
        len(unreleased_locations),
        len(unreleased_entities),
    )

    stat_icons = build_stat_icon_wikitext_map(site, data, version)
    log.info("Stat icons ready: %d", len(stat_icons))
    status_effect_icons = build_status_effect_icon_wikitext_map(site, data, version)
    log.info("Status effect icons ready: %d", len(status_effect_icons))
    drop_tiers = {int((it.get("DropTierType") or 0)) for it in items}
    drop_tier_icons = build_drop_tier_wikitext_map(site, data, version, drop_tiers)
    drop_tier_icon_parts = build_drop_tier_icon_parts_map(site, data, version, drop_tiers)
    log.info("Drop tier icons ready: %d", len(drop_tier_icons))
    difficulty_skull_icon = build_difficulty_skull_wikitext(site, data, version, size_px=40)

    items_to_process = items[:3] if GENERATE_FEW_PAGES else items
    locations_to_process = locations[:3] if GENERATE_FEW_PAGES else locations
    all_entities = [go for go in game_objects if go.get("IsEntity", True)]
    entities_to_process = all_entities[:3] if GENERATE_FEW_PAGES else all_entities

    if GENERATE_FEW_PAGES:
        log.info("GENERATE_FEW_PAGES=1: limiting to 3 items, 3 locations, 3 entities")

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

    entity_name_to_locations: dict[str, list[str]] = {}
    for loc in locations:
        lname = str(loc.get("Name") or "")
        if not lname:
            continue
        lpath = location_id_to_path.get(loc.get("Id"))
        if not lpath:
            continue
        link = f"[[{lpath}|{lname}]]"
        for go_name in (loc.get("FoundGameObjects") or []):
            if not go_name:
                continue
            k = str(go_name)
            entity_name_to_locations.setdefault(k, [])
            if link not in entity_name_to_locations[k]:
                entity_name_to_locations[k].append(link)

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

    stats: dict[str, int] = {}
    errors: list[str] = []

    def _one(
        kind: str,
        title: str,
        build,
        save,
    ) -> None:
        t0 = time.perf_counter()
        try:
            w = build()
            t1 = time.perf_counter()
            r = save(site, title, w, version, WIKI_BOT_USER, kind)
            t2 = time.perf_counter()
            build_ms = (t1 - t0) * 1000
            save_ms = (t2 - t1) * 1000
            stats[r] = stats.get(r, 0) + 1
            log.info(
                "%s %s | result=%s | build=%.0fms save=%.0fms total=%.0fms",
                kind,
                title,
                r,
                build_ms,
                save_ms,
                (t2 - t0) * 1000,
            )
        except Exception:
            errors.append(f"{kind} {title}")
            log.error("FAILED %s %s\n%s", kind, title, traceback.format_exc())

    for it in items_to_process:
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
            )

        def save_item(s, ttl, txt, ver, user, k):
            return save_bot_page(s, ttl, txt, ver, user, k, force_overwrite=FORCE_OVERWRITE)

        _one("item", path, build_item, save_item)

    for loc in locations_to_process:
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
                difficulty_skull_icon=difficulty_skull_icon,
                unreleased=int(l["Id"]) in unreleased_locations,
            )

        def save_loc(s, ttl, txt, ver, user, k):
            return save_bot_page(s, ttl, txt, ver, user, k, force_overwrite=FORCE_OVERWRITE)

        _one("location", path, build_loc, save_loc)

    for go in entities_to_process:
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
                entity_name_to_locations=entity_name_to_locations,
                drop_tier_icon_parts=drop_tier_icon_parts,
                stat_icons=stat_icons,
                status_effect_icons=status_effect_icons,
                unreleased=int(g["Id"]) in unreleased_entities,
            )

        def save_ent(s, ttl, txt, ver, user, k):
            return save_bot_page(s, ttl, txt, ver, user, k, force_overwrite=FORCE_OVERWRITE)

        _one("entity", path, build_go, save_ent)

    write_last_version(version)
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
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: python -m pq_wiki import <pq-datadump.json> [--force]", file=sys.stderr)
        return 2
    path = Path(argv[1])
    force = "--force" in argv
    if not path.is_file():
        print(f"Not found: {path}", file=sys.stderr)
        return 1
    out = run_import(path, force=force)
    print(json.dumps(out, indent=2))
    return 0 if out.get("ok") else 1
