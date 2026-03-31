from __future__ import annotations

from typing import Any

import pywikibot

from pq_wiki.achievement_icons import upload_achievement_icon
from pq_wiki.datadump_helpers import (
    achievement_category_id,
    achievement_category_label,
    achievement_group_label,
    achievement_series_label,
    achievement_series_name_if_defined,
    find_item_id_by_name,
    find_t0_weapon_item_for_class,
)
from pq_wiki.texture_names import portal_preview_base, slug
from pq_wiki.texture_service import upload_portal_preview
from pq_wiki.honor_icons import honor_bronze_wikitext
from pq_wiki.reward_wikitext import render_metadata_section, render_rewards_wikitable
from pq_wiki.seo import first_wiki_filename_from_file_wikitext, plain_text_for_seo, wiki_seo_block
from pq_wiki.wikitext_util import html_to_wikitext, template_invocation


_LUCKY_ACHIEVEMENT_GROUP_ID = 5


def _link_file_wikitext_to_page(img_wiki: str, page_path: str) -> str:
    marker = "]]"
    i = img_wiki.find(marker)
    if i == -1:
        return img_wiki
    return f"{img_wiki[:i]}|link={page_path}{img_wiki[i:]}"


def _norm_metadata(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for k, v in raw.items():
        out[str(k)] = v
    return out


def build_achievement_wikitext(
    site: pywikibot.Site,
    ach: dict[str, Any],
    data: dict[str, Any],
    version: str,
    *,
    item_id_to_path: dict[int, str],
    item_id_to_item: dict[int, dict[str, Any]],
    item_name_to_id: dict[str, int],
    items_list: list[dict[str, Any]],
    stat_icons: dict[str, str] | None,
    valor_icon_wikitext: str,
    honor_icon_map: dict[int, str],
    location_id_to_path: dict[int, str],
    location_name_to_path: dict[str, str],
    location_id_to_loc: dict[int, dict[str, Any]] | None = None,
    achievement_categories: dict[str, Any] | None,
    achievement_series: dict[str, Any] | None,
    achievement_groups: dict[str, Any] | None = None,
    wiki_hidden: bool = False,
    unreleased: bool = False,
) -> str:
    aid = int(ach.get("Id") or 0)
    name = str(ach.get("Name") or f"Achievement {aid}")
    desc = html_to_wikitext(str(ach.get("Description") or ""))
    desc_block = f"''{desc}''" if desc else ""

    cat_num = achievement_category_id(ach.get("Category"), achievement_categories)
    cat_label = achievement_category_label(cat_num, achievement_categories)
    seq = int(ach.get("SequenceNumber") or 0)

    def _ach_int(key: str, default: int = -1) -> int:
        raw = ach.get(key)
        if raw is None:
            return default
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    series_id = _ach_int("SeriesId")
    group_id = _ach_int("Group")
    subgroup_id = _ach_int("SubGroup")
    class_id = _ach_int("Classification")

    icon_w = upload_achievement_icon(
        site,
        data,
        version,
        category_id=cat_num,
        sequence_number=seq,
        category_label=cat_label,
        thumb_px=57,
    )

    lucky_id = find_item_id_by_name(items_list, "Lucky Clover")
    mastery_by_class: dict[str, dict[str, Any]] = {}
    # Pre-fill weapon classes from rewards
    rewards_raw = ach.get("Rewards") or []
    if isinstance(rewards_raw, list):
        for rw in rewards_raw:
            if not isinstance(rw, dict):
                continue
            if str(rw.get("Type") or "") == "MasteryBoost":
                wc = str(rw.get("WeaponClass") or "").strip()
                if wc and wc not in mastery_by_class:
                    t0 = find_t0_weapon_item_for_class(items_list, wc)
                    if t0:
                        mastery_by_class[wc] = t0

    rewards_block = ""
    if isinstance(rewards_raw, list) and rewards_raw:
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

    meta = _norm_metadata(ach.get("Metadata"))
    meta_block = render_metadata_section(
        meta,
        item_id_to_path=item_id_to_path,
        item_id_to_item=item_id_to_item,
        location_id_to_path=location_id_to_path,
    )

    details_rows: list[tuple[str, str]] = [
        ("Category", cat_label),
    ]
    if series_id != -1:
        details_rows.append(("Series", achievement_series_label(series_id, achievement_series)))
        details_rows.append(("Sequence", str(seq)))
    if group_id != -1:
        details_rows.append(
            ("Group", achievement_group_label(group_id, achievement_groups)),
        )
    if group_id == _LUCKY_ACHIEVEMENT_GROUP_ID and subgroup_id != -1:
        loc = (location_id_to_loc or {}).get(subgroup_id)
        if loc:
            lname = str(loc.get("Name") or f"Location {subgroup_id}")
            path = location_id_to_path.get(subgroup_id, lname)
            link = f"[[{path}|{lname}]]"
            portal_w = ""
            portal = loc.get("PortalSprite")
            if isinstance(portal, dict) and portal:
                portal_w = upload_portal_preview(
                    site,
                    portal,
                    version,
                    logical_name=portal_preview_base(slug(lname)),
                    thumb_size=48,
                )
                if portal_w:
                    portal_w = _link_file_wikitext_to_page(portal_w, path)
            cell = f"{portal_w} {link}".strip() if portal_w else link
            details_rows.append(("Dungeon", cell))
        else:
            details_rows.append(("Dungeon", str(subgroup_id)))
    elif subgroup_id != -1:
        details_rows.append(("Sub-group", str(subgroup_id)))
    if class_id != -1:
        details_rows.append(("Classification", str(class_id)))
    from pq_wiki.wikitext_util import wikitable

    details_block = wikitable(details_rows)

    tag_hidden = ""
    if wiki_hidden:
        tag_hidden = "''This achievement is hidden in-game; it is shown on the wiki by override.''"

    cat_lines = ["[[Category:Achievements]]", f"[[Category:{cat_label} achievements]]"]
    if series_id != -1:
        series_for_cat = achievement_series_name_if_defined(series_id, achievement_series)
        if series_for_cat:
            cat_lines.append(f"[[Category:{series_for_cat} achievements]]")
    if group_id != -1:
        group_cat = achievement_group_label(group_id, achievement_groups)
        cat_lines.append(f"[[Category:{group_cat} achievements]]")
    if subgroup_id != -1 and group_id != _LUCKY_ACHIEVEMENT_GROUP_ID:
        cat_lines.append(f"[[Category:Sub-group {subgroup_id} achievements]]")
    if class_id != -1:
        cat_lines.append(f"[[Category:Classification {class_id} achievements]]")
    if wiki_hidden:
        cat_lines.append("[[Category:Hidden achievements]]")
    if unreleased:
        cat_lines.append("[[Category:Unreleased]]")
    categories_block = "\n".join(cat_lines)

    body = template_invocation(
        "PQ Achievement",
        [
            ("tag_hidden", tag_hidden),
            ("icon", icon_w),
            ("desc", desc_block),
            ("details", details_block + ( "\n\n" + meta_block if meta_block else "" )),
            ("rewards", rewards_block),
            ("categories", categories_block),
        ],
    )
    desc_plain = plain_text_for_seo(desc)
    seo_desc = (
        f"{name} — {desc_plain}. Pixel Quest Wiki achievement."
        if desc_plain
        else f"{name} — Pixel Quest Wiki achievement."
    )
    seo = wiki_seo_block(
        site,
        page_title=name,
        description=seo_desc,
        wiki_image_filename=first_wiki_filename_from_file_wikitext(icon_w),
        image_alt=f"{name} achievement",
    )
    return f"{body}\n\n{seo}"
