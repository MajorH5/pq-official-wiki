from __future__ import annotations

import pywikibot

from pq_wiki.renderers.entity_renderer import _layout_drops_multicolumn
from pq_wiki.renderers.shared import find_dungeon_key, link_entity
from pq_wiki.texture_service import upload_portal_preview, upload_sprite_if_possible, upload_sprite_thumb_block
from pq_wiki.wikitext_util import fmt_num, template_invocation, wikitable

# Wikimedia Commons placeholder (InstantCommons / local mirror); replace when datadump ships assets.
_COMMONS_PLACEHOLDER_FILE = "No image available-4x.png"


def build_location_wikitext(
    site: pywikibot.Site,
    loc: dict,
    version: str,
    item_name_to_id: dict[str, int],
    item_id_to_path: dict[int, str],
    go_name_to_id: dict[str, int],
    entity_id_to_path: dict[int, str],
    entity_name_to_go: dict[str, dict] | None = None,
    item_id_to_item: dict[int, dict] | None = None,
    difficulty_skull_icon: str = "",
    unreleased: bool = False,
) -> str:
    lid = loc["Id"]
    name = loc.get("Name", f"Location {lid}")
    portal = loc.get("PortalSprite")
    pimg = upload_portal_preview(site, portal, version) if portal else ""
    key_inline = _key_inline_wikitext(
        site,
        name,
        version,
        item_name_to_id,
        item_id_to_path,
        item_id_to_item,
    )
    portal_image_block = _portal_and_key_row(pimg, key_inline)

    difficulty = _difficulty_display(loc.get("Difficulty"), difficulty_skull_icon)

    d = _location_difficulty_int(loc.get("Difficulty"))
    portal_rows: list[tuple[str, str]] = [
        ("Teleportation", "Yes" if loc.get("TeleportationEnabled") else "No"),
    ]
    if d > 0:
        portal_rows.append(
            (
                "Perma death",
                ('<span style="color:red">Yes</span>' if loc.get("IsPermaDeath") else "No"),
            )
        )
    portal_rows.append(("Max players", fmt_num(loc.get("MaxPlayerCount"))))
    portal_table = wikitable(portal_rows)

    map_section = _build_map_section(site, loc, version, name)
    screenshots_section = _build_screenshots_section(site, loc, version, name)

    found_entities_block = ""
    found = loc.get("FoundGameObjects") or []
    if found:
        fe_cells = [
            _render_entity_preview_cell(site, str(n), version, go_name_to_id, entity_id_to_path, entity_name_to_go)
            for n in found
        ]
        found_entities_block = _entity_multicolumn_wikitable("== Found entities ==", "Entity", fe_cells)

    dropped_from_block = ""
    dropped_from = _entities_that_drop_location(name, entity_name_to_go)
    if dropped_from:
        df_cells = [
            _render_entity_preview_cell(site, n, version, go_name_to_id, entity_id_to_path, entity_name_to_go)
            for n in dropped_from
        ]
        dropped_from_block = _entity_multicolumn_wikitable("== Dropped from ==", "Enemy", df_cells)

    cat_lines = ["[[Category:Locations]]"]
    if unreleased:
        cat_lines.append("[[Category:Unreleased]]")
    categories_block = "\n".join(cat_lines)

    body = template_invocation(
        "PQ Location",
        [
            ("difficulty", difficulty),
            ("portal_image", portal_image_block),
            ("portal_table", portal_table),
            ("map_section", map_section),
            ("screenshots_section", screenshots_section),
            ("found_entities", found_entities_block),
            ("dropped_from", dropped_from_block),
            ("categories", categories_block),
        ],
    )
    return f"<!-- PQ bot generated {version} -->{body}"


def _key_inline_wikitext(
    site: pywikibot.Site,
    location_name: str,
    version: str,
    item_name_to_id: dict[str, int],
    item_id_to_path: dict[int, str],
    item_id_to_item: dict[int, dict] | None,
) -> str:
    key_id = find_dungeon_key(location_name, item_name_to_id)
    if key_id is None:
        return ""
    kpath = item_id_to_path.get(key_id)
    if not kpath:
        return ""
    kn = f"{location_name} Key"
    link = f"[[{kpath}|{kn}]]"
    icon = ""
    if item_id_to_item and int(key_id) in item_id_to_item:
        icon = upload_sprite_if_possible(
            site,
            item_id_to_item[int(key_id)].get("Sprite"),
            version,
            thumb_size=40,
        )
    if icon and kpath:
        icon = _link_image_wikitext(icon, kpath)
    if icon:
        return (
            '<span style="display:inline-flex; align-items:center; gap:8px;">'
            f"{icon} {link}</span>"
        )
    return link


def _portal_and_key_row(portal_wikitext: str, key_wikitext: str) -> str:
    """Portal preview with dungeon key to the right, vertically centered (flex)."""
    p = portal_wikitext.strip()
    k = key_wikitext.strip()
    if p and k:
        return (
            '<div style="display:flex; flex-wrap:wrap; align-items:center; gap:16px;">'
            f"{p}{k}"
            "</div>"
        )
    if p:
        return p
    return k


def _commons_placeholder_thumb(caption: str, width: int = 250) -> str:
    safe = caption.replace("|", " ")
    return f"[[File:{_COMMONS_PLACEHOLDER_FILE}|thumb|upright=1|{width}px|{safe}]]"


def _build_map_section(site: pywikibot.Site, loc: dict, version: str, location_name: str) -> str:
    """
    Minimap: uses MinimapSprite or Minimap when present; otherwise a Commons placeholder thumb.
    """
    sprite = loc.get("MinimapSprite") or loc.get("Minimap")
    cap_uploaded = f"Minimap of {location_name}"
    cap_placeholder = (
        f"Minimap placeholder — replace with in-game minimap of {location_name}. "
        "Wikimedia Commons: No image available-4x.png."
    )
    if isinstance(sprite, dict) and sprite:
        block = upload_sprite_thumb_block(site, sprite, version, 320, cap_uploaded)
        if block:
            return f"== Map ==\n{block}"
    return f"== Map ==\n{_commons_placeholder_thumb(cap_placeholder)}"


def _build_screenshots_section(site: pywikibot.Site, loc: dict, version: str, location_name: str) -> str:
    """
    Screenshots: Screenshots = [ { \"Sprite\": {...}, \"Caption\": \"...\" }, ... ] when present;
    otherwise a packed gallery of Commons placeholders with captions.
    """
    raw = loc.get("Screenshots")
    lines: list[str] = []
    if isinstance(raw, list) and raw:
        for i, entry in enumerate(raw):
            if not isinstance(entry, dict):
                continue
            cap = str(entry.get("Caption") or entry.get("caption") or f"Screenshot {i + 1}").strip()
            sp = entry.get("Sprite") or entry.get("Image")
            if isinstance(sp, dict) and sp:
                block = upload_sprite_thumb_block(site, sp, version, 400, cap)
                if block:
                    lines.append(block)
    if lines:
        return "== Screenshots ==\n" + "\n".join(lines)
    g1 = (
        f"Gameplay screenshot placeholder — replace with in-game capture ({location_name}). "
        "Wikimedia Commons placeholder image."
    )
    g2 = (
        f"Area or boss room placeholder — replace when available ({location_name}). "
        "Wikimedia Commons placeholder image."
    )
    return "\n".join(
        [
            "== Screenshots ==",
            '<gallery mode="packed" heights="220px">',
            f"{_COMMONS_PLACEHOLDER_FILE}|{g1}",
            f"{_COMMONS_PLACEHOLDER_FILE}|{g2}",
            "</gallery>",
        ]
    )


def _location_difficulty_int(raw: object) -> int:
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def _difficulty_display(raw: object, skull_icon: str) -> str:
    d = _location_difficulty_int(raw)
    if d <= 0:
        return ""
    if not skull_icon:
        return fmt_num(d)
    return " ".join([skull_icon] * d)


def _entity_tag(go: dict | None) -> str:
    if not go:
        return ""
    if go.get("IsDungeonBoss"):
        return "Dungeon Boss"
    if go.get("IsTroomBoss"):
        return "Troom Boss"
    if go.get("IsQuestEntity"):
        return "Quest Entity"
    return ""


def _entity_multicolumn_wikitable(section_heading: str, column_header: str, cells: list[str]) -> str:
    """Same wrapping as item == Dropped by == and entity loot: scroll div + wikitable + multicolumn inner."""
    if not cells:
        return ""
    inner = _layout_drops_multicolumn(cells, max_per_col=5, inner_table_width="auto")
    return "\n".join(
        [
            section_heading,
            '<div style="display:inline-block; max-width:100%; overflow-x:auto; vertical-align:top;">',
            '{| class="wikitable sortable" style="width:auto;"',
            f"! {column_header}",
            "|-",
            f"| {inner}",
            "|}",
            "</div>",
        ]
    )


def _render_entity_preview_cell(
    site: pywikibot.Site,
    name: str,
    version: str,
    go_name_to_id: dict[str, int],
    entity_id_to_path: dict[int, str],
    entity_name_to_go: dict[str, dict] | None,
) -> str:
    go = entity_name_to_go.get(name) if entity_name_to_go else None
    icon = ""
    if go:
        icon = upload_sprite_if_possible(site, go.get("Sprite"), version, thumb_size=40)
    if icon and name in go_name_to_id:
        eid = go_name_to_id[name]
        path = entity_id_to_path.get(eid)
        if path:
            icon = _link_image_wikitext(icon, path)
    label = link_entity(name, go_name_to_id, entity_id_to_path)
    tag = _entity_tag(go)
    suffix = f" <small>({tag})</small>" if tag else ""
    text = f"{label}{suffix}"
    if icon:
        return (
            '<span style="display:inline-flex; align-items:center; gap:8px;">'
            f"{icon} {text}"
            "</span>"
        )
    return text.strip()


def _entities_that_drop_location(location_name: str, entity_name_to_go: dict[str, dict] | None) -> list[str]:
    if not entity_name_to_go:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for n, go in entity_name_to_go.items():
        drops = go.get("DungeonDrops") or []
        if location_name in drops and n not in seen:
            seen.add(n)
            out.append(n)
    return sorted(out)


def _link_image_wikitext(img_wiki: str, page_path: str) -> str:
    marker = "]]"
    i = img_wiki.find(marker)
    if i == -1:
        return img_wiki
    return f"{img_wiki[:i]}|link={page_path}{img_wiki[i:]}"
