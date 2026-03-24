from __future__ import annotations

import pywikibot

from pq_wiki.renderers.shared import find_dungeon_key, link_entity
from pq_wiki.texture_service import upload_portal_preview, upload_sprite_if_possible
from pq_wiki.wikitext_util import fmt_num, wikitable


def build_location_wikitext(
    site: pywikibot.Site,
    loc: dict,
    version: str,
    item_name_to_id: dict[str, int],
    item_id_to_path: dict[int, str],
    go_name_to_id: dict[str, int],
    entity_id_to_path: dict[int, str],
    entity_name_to_go: dict[str, dict] | None = None,
    difficulty_skull_icon: str = "",
    unreleased: bool = False,
) -> str:
    lid = loc["Id"]
    name = loc.get("Name", f"Location {lid}")
    portal = loc.get("PortalSprite")
    pimg = upload_portal_preview(site, portal, version) if portal else ""

    lines = [
        f"<!-- PQ bot generated {version} -->",
        "",
        f"'''Difficulty''' {_difficulty_display(loc.get('Difficulty'), difficulty_skull_icon)}",
        "",
        "== Notes ==",
        "<!-- Add editor notes/history here. -->",
        "",
        "== Portal ==",
    ]
    if pimg:
        lines.append(pimg)
    lines.append("")
    portal_rows = [
        ("Teleportation", "Yes" if loc.get("TeleportationEnabled") else "No"),
        (
            "Perma death",
            ('<span style="color:red">Yes</span>' if loc.get("IsPermaDeath") else "No"),
        ),
        ("Max players", fmt_num(loc.get("MaxPlayerCount"))),
    ]
    lines.append(wikitable(portal_rows))
    lines.append("")

    key_id = find_dungeon_key(name, item_name_to_id)
    if key_id is not None:
        kpath = item_id_to_path.get(key_id)
        if kpath:
            kn = f"{name} Key"
            lines.append("== Key ==")
            lines.append(f"[[{kpath}|{kn}]]")
            lines.append("")

    found = loc.get("FoundGameObjects") or []
    if found:
        lines.append("== Found entities ==")
        for n in found:
            lines.append(_render_entity_preview_row(site, str(n), version, go_name_to_id, entity_id_to_path, entity_name_to_go))
        lines.append("")

    dropped_from = _entities_that_drop_location(name, entity_name_to_go)
    if dropped_from:
        lines.append("== Dropped from ==")
        for n in dropped_from:
            lines.append(_render_entity_preview_row(site, n, version, go_name_to_id, entity_id_to_path, entity_name_to_go))
        lines.append("")

    lines.append("[[Category:Locations]]")
    if unreleased:
        lines.append("[[Category:Unreleased]]")
    return "\n".join(lines)


def _difficulty_display(raw: object, skull_icon: str) -> str:
    try:
        d = int(raw or 0)
    except (TypeError, ValueError):
        d = 0
    if d <= 0:
        return fmt_num(raw)
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


def _render_entity_preview_row(
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
    return f"* {icon} {label}{suffix}".strip()


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
