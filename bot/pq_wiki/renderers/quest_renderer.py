from __future__ import annotations

from typing import Any

import pywikibot

from pq_wiki.quest_helpers import (
    EVENT_BIOME_ENEMY_KILLED,
    EVENT_ENEMY_KILLED,
    EVENT_RIFT_COMPLETED,
    biome_sprite_dict,
    category_wikilink,
    icon_dedupe_key,
    normalize_icon_to_sprite,
    quest_category_display,
    reward_is_choice_stat_quest,
    sanitize_quest_description,
    sanitize_quest_name,
)
from pq_wiki.renderers.achievement_renderer import _link_file_wikitext_to_page
from pq_wiki.reward_wikitext import render_rewards_wikitable
from pq_wiki.seo import first_wiki_filename_from_file_wikitext, plain_text_for_seo, wiki_seo_block
from pq_wiki.texture_names import portal_preview_base, slug
from pq_wiki.honor_icons import honor_bronze_wikitext
from pq_wiki.texture_service import upload_portal_preview, upload_sprite_if_possible
from pq_wiki.wikitext_util import html_to_wikitext, template_invocation, wikitable

_EVENT_NAMES: dict[int, str] = {
    0: "Experience earned",
    1: "Damage dealt",
    2: "Tiles travelled",
    3: "Rifts completed",
    4: "Enemies killed",
    5: "Projectiles fired",
    6: "Dungeon Rush complete",
    7: "Dungeon Rush checkpoint",
    8: "Biome enemies killed",
    9: "Gauntlet completed",
}


def _go_sprite_for_upload(go: dict[str, Any]) -> dict[str, Any] | None:
    from pq_wiki.sprites import normalize_image_rect_offset_size

    sp = go.get("Sprite")
    if not isinstance(sp, dict):
        return None
    tex = sp.get("texture") or sp.get("Texture")
    if not tex:
        return None
    out = {**sp, "Texture": tex}
    if "ImageRectOffset" not in out and "imageRectOffset" in out:
        out["ImageRectOffset"] = out["imageRectOffset"]
    if "ImageRectSize" not in out and "imageRectSize" in out:
        out["ImageRectSize"] = out["imageRectSize"]
    ro = out.get("ImageRectOffset") or out.get("imageRectOffset") or {}
    rs = out.get("ImageRectSize") or out.get("imageRectSize") or {}
    (ox, oy), (w, h) = normalize_image_rect_offset_size(ro, rs)
    out["ImageRectOffset"] = {"X": ox, "Y": oy}
    out["ImageRectSize"] = {"X": w, "Y": h}
    return out


def _sanitize_random_quest(name: str, desc: str, q: dict[str, Any]) -> tuple[str, str]:
    """Replace {dispatchKey} placeholders; generic title when randomized."""
    rk = int(q.get("RandomKeyAmount") or 1)
    name = sanitize_quest_name(name, q)
    desc = sanitize_quest_description(desc)
    if q.get("RandomizesDispatchKeys"):
        desc = (desc or "").strip()
        if len(desc) < 10:
            desc = (
                "Each cycle, one of the possible targets below is chosen at random "
                f"({rk} at a time when multiple apply)."
            )
    return name, desc


def _dispatch_target_lines(
    event_type: int,
    keys: list[Any],
    *,
    location_id_to_path: dict[int, str],
    location_id_to_loc: dict[int, dict[str, Any]],
    entity_id_to_path: dict[int, str],
    entity_id_to_go: dict[int, dict[str, Any]],
    biome_id_to_path: dict[int, str],
    biomes_by_id: dict[int, dict[str, Any]],
) -> list[str]:
    lines: list[str] = []
    for raw in keys:
        try:
            k = int(raw)
        except (TypeError, ValueError):
            continue
        if event_type == EVENT_RIFT_COMPLETED:
            loc = location_id_to_loc.get(k)
            if loc:
                nm = str(loc.get("Name") or f"Location {k}")
                p = location_id_to_path.get(k, nm)
                lines.append(f"* [[{p}|{nm}]]")
            else:
                lines.append(f"* Location id {k}")
        elif event_type == EVENT_ENEMY_KILLED:
            go = entity_id_to_go.get(k)
            if go:
                nm = str(go.get("Name") or f"Enemy {k}")
                p = entity_id_to_path.get(k, nm)
                lines.append(f"* [[{p}|{nm}]]")
            else:
                lines.append(f"* Enemy id {k}")
        elif event_type == EVENT_BIOME_ENEMY_KILLED:
            bio = biomes_by_id.get(k)
            if bio:
                nm = str(bio.get("Name") or f"Biome {k}")
                p = biome_id_to_path.get(k, nm)
                lines.append(f"* [[{p}|{nm}]]")
            else:
                lines.append(f"* Biome id {k}")
        else:
            lines.append(f"* {k}")
    return lines


def _upload_quest_icons_deduped(
    site: pywikibot.Site,
    quest: dict[str, Any],
    version: str,
) -> list[str]:
    qid = int(quest.get("Id") or 0)
    icons_raw = quest.get("Icons") or []
    if not isinstance(icons_raw, list):
        return []
    cells: list[str] = []
    seen: set[str] = set()
    idx = 0
    for ic in icons_raw:
        if not isinstance(ic, dict):
            continue
        k = icon_dedupe_key(ic)
        if k in seen:
            continue
        seen.add(k)
        sp = normalize_icon_to_sprite(ic)
        if not sp:
            continue
        idx += 1
        w = upload_sprite_if_possible(
            site,
            sp,
            version,
            thumb_size=48,
            logical_name=f"quest_{qid}_icon_{idx}",
        )
        if w:
            cells.append(w)
    return cells


def _build_icon_row(
    site: pywikibot.Site,
    quest: dict[str, Any],
    version: str,
    *,
    event_type: int,
    location_id_to_path: dict[int, str],
    location_id_to_loc: dict[int, dict[str, Any]],
    entity_id_to_path: dict[int, str],
    entity_id_to_go: dict[int, dict[str, Any]],
    biome_id_to_path: dict[int, str],
    biomes_by_id: dict[int, dict[str, Any]],
) -> str:
    keys = quest.get("DispatchKeys") or []
    if not isinstance(keys, list):
        keys = []
    cells: list[str] = []

    if event_type == EVENT_RIFT_COMPLETED:
        for lid in keys:
            try:
                lid = int(lid)
            except (TypeError, ValueError):
                continue
            loc = location_id_to_loc.get(lid)
            if not loc:
                continue
            lname = str(loc.get("Name") or f"Location {lid}")
            path = location_id_to_path.get(lid, lname)
            portal = loc.get("PortalSprite")
            w = ""
            if isinstance(portal, dict) and portal:
                w = upload_portal_preview(
                    site,
                    portal,
                    version,
                    logical_name=portal_preview_base(slug(lname)),
                    thumb_size=48,
                )
                if w:
                    w = _link_file_wikitext_to_page(w, path)
            link = f"[[{path}|{lname}]]"
            cells.append(f"{w} {link}".strip() if w else link)
        if cells:
            return " ".join(cells)
        return " ".join(_upload_quest_icons_deduped(site, quest, version))

    if event_type == EVENT_ENEMY_KILLED:
        for eid in keys:
            try:
                eid = int(eid)
            except (TypeError, ValueError):
                continue
            go = entity_id_to_go.get(eid)
            if not go:
                continue
            ename = str(go.get("Name") or f"Enemy {eid}")
            path = entity_id_to_path.get(eid, ename)
            sp = _go_sprite_for_upload(go)
            w = ""
            if sp:
                w = upload_sprite_if_possible(
                    site,
                    sp,
                    version,
                    thumb_size=40,
                    logical_name=f"quest_enemy_{eid}_{slug(ename)}",
                )
                if w:
                    w = _link_file_wikitext_to_page(w, path)
            link = f"[[{path}|{ename}]]"
            cells.append(f"{w} {link}".strip() if w else link)
        if cells:
            return " ".join(cells)
        return " ".join(_upload_quest_icons_deduped(site, quest, version))

    if event_type == EVENT_BIOME_ENEMY_KILLED:
        for bid in keys:
            try:
                bid = int(bid)
            except (TypeError, ValueError):
                continue
            bio = biomes_by_id.get(bid)
            if not bio:
                continue
            bname = str(bio.get("Name") or f"Biome {bid}")
            path = biome_id_to_path.get(bid, bname)
            sp = biome_sprite_dict(bio)
            w = ""
            if sp:
                w = upload_sprite_if_possible(
                    site,
                    sp,
                    version,
                    thumb_size=48,
                    logical_name=f"quest_biome_{bid}_{slug(bname)}",
                )
                if w:
                    w = _link_file_wikitext_to_page(w, path)
            link = f"[[{path}|{bname}]]"
            cells.append(f"{w} {link}".strip() if w else link)
        if cells:
            return " ".join(cells)
        return " ".join(_upload_quest_icons_deduped(site, quest, version))

    return " ".join(_upload_quest_icons_deduped(site, quest, version))


def build_quest_wikitext(
    site: pywikibot.Site,
    quest: dict[str, Any],
    data: dict[str, Any],
    version: str,
    *,
    quest_categories: dict[str, Any] | None,
    item_id_to_path: dict[int, str],
    item_id_to_item: dict[int, dict[str, Any]],
    item_name_to_id: dict[str, int],
    items_list: list[dict[str, Any]],
    stat_icons: dict[str, str] | None,
    valor_icon_wikitext: str,
    honor_icon_map: dict[int, str],
    location_id_to_path: dict[int, str],
    location_name_to_path: dict[str, str],
    location_id_to_loc: dict[int, dict[str, Any]] | None,
    entity_id_to_path: dict[int, str],
    entity_id_to_go: dict[int, dict[str, Any]],
    biome_id_to_path: dict[int, str],
    biomes_by_id: dict[int, dict[str, Any]],
) -> str:
    qid = int(quest.get("Id") or 0)
    name_raw = str(quest.get("Name") or f"Quest {qid}")
    desc_raw = str(quest.get("Description") or "")
    name_raw, desc_raw = _sanitize_random_quest(name_raw, desc_raw, quest)
    name = html_to_wikitext(name_raw)
    desc = html_to_wikitext(desc_raw)
    desc_block = f"''{desc}''" if desc else ""

    et = int(quest.get("EventType") or -1)
    et_label = _EVENT_NAMES.get(et, str(et))

    cat_display = quest_category_display(quest.get("Category"), quest_categories)

    rewards_raw = quest.get("Rewards") or []
    if not isinstance(rewards_raw, list):
        rewards_raw = []
    lucky_id = None
    for it in items_list:
        if str(it.get("Name") or "").strip() == "Lucky Clover":
            lucky_id = int(it["Id"])
            break
    mastery_by_class: dict[str, dict[str, Any]] = {}
    for rw in rewards_raw:
        if isinstance(rw, dict) and str(rw.get("Type") or "") == "MasteryBoost":
            wc = str(rw.get("WeaponClass") or "").strip()
            if wc and wc not in mastery_by_class:
                from pq_wiki.datadump_helpers import find_t0_weapon_item_for_class

                t0 = find_t0_weapon_item_for_class(items_list, wc)
                if t0:
                    mastery_by_class[wc] = t0

    rewards_block = ""
    if rewards_raw:
        table = render_rewards_wikitable(
            [r for r in rewards_raw if isinstance(r, dict)],
            item_id_to_path=item_id_to_path,
            item_id_to_item=item_id_to_item,
            item_name_to_id=item_name_to_id,
            stat_icons=stat_icons,
            valor_icon_wikitext=valor_icon_wikitext,
            honor_bronze_icon_wikitext=honor_bronze_wikitext(honor_icon_map),
            lucky_clover_item_id=lucky_id,
            mastery_weapon_item_by_class=mastery_by_class,
            location_id_to_path=location_id_to_path,
            location_name_to_path=location_name_to_path,
        )
        rewards_block = f"== Rewards ==\n\n{table}"

    loc_id_loc = location_id_to_loc or {}

    icon_row = _build_icon_row(
        site,
        quest,
        version,
        event_type=et,
        location_id_to_path=location_id_to_path,
        location_id_to_loc=loc_id_loc,
        entity_id_to_path=entity_id_to_path,
        entity_id_to_go=entity_id_to_go,
        biome_id_to_path=biome_id_to_path,
        biomes_by_id=biomes_by_id,
    )

    details_rows: list[tuple[str, str]] = [
        ("Event type", et_label),
        ("Category", cat_display),
    ]
    if quest.get("IsTimedQuest"):
        details_rows.append(("Timed", "Yes"))
    if quest.get("RandomizesDispatchKeys"):
        details_rows.append(
            ("Randomizes targets", f"Yes ({int(quest.get('RandomKeyAmount') or 1)} per cycle)"),
        )
    details_block = wikitable(details_rows)

    targets_lines = _dispatch_target_lines(
        et,
        quest.get("DispatchKeys") or [],
        location_id_to_path=location_id_to_path,
        location_id_to_loc=loc_id_loc,
        entity_id_to_path=entity_id_to_path,
        entity_id_to_go=entity_id_to_go,
        biome_id_to_path=biome_id_to_path,
        biomes_by_id=biomes_by_id,
    )
    targets_block = ""
    if quest.get("RandomizesDispatchKeys") and targets_lines:
        targets_block = "\n\n== Possible targets ==\n" + "\n".join(targets_lines)
    elif et in (EVENT_RIFT_COMPLETED, EVENT_ENEMY_KILLED, EVENT_BIOME_ENEMY_KILLED) and targets_lines:
        targets_block = "\n\n== Targets ==\n" + "\n".join(targets_lines)

    cat_lines = ["[[Category:Quests]]", category_wikilink(cat_display)]
    if quest.get("IsTimedQuest"):
        cat_lines.append("[[Category:Timed Quests]]")
    if reward_is_choice_stat_quest([r for r in rewards_raw if isinstance(r, dict)]):
        cat_lines.append("[[Category:Stat Quests]]")

    categories_block = "\n".join(cat_lines)

    body = template_invocation(
        "PQ Quest",
        [
            ("icon", icon_row),
            ("desc", desc_block),
            ("details", details_block),
            ("rewards", rewards_block),
            ("extra", targets_block),
            ("categories", categories_block),
        ],
    )
    desc_plain = plain_text_for_seo(desc_raw)
    seo_desc = (
        f"{name_raw} — {desc_plain}. Pixel Quest Wiki quest."
        if desc_plain
        else f"{name_raw} — Pixel Quest Wiki quest."
    )
    seo = wiki_seo_block(
        site,
        page_title=name_raw,
        description=seo_desc,
        wiki_image_filename=first_wiki_filename_from_file_wikitext(icon_row),
        image_alt=f"{name_raw} quest",
    )
    return f"{body}\n\n{seo}"
