from __future__ import annotations

import io

import pywikibot
from PIL import Image

from pq_wiki.roblox_assets import fetch_asset_bytes, parse_asset_id
from pq_wiki.sprites import (
    get_texture_url,
    normalize_gif_bytes_for_imagemagick,
    render_animation_to_gif_bytes,
)
from pq_wiki.seo import first_wiki_filename_from_file_wikitext, plain_text_for_seo, wiki_seo_block
from pq_wiki.texture_names import skin_animation_base, skin_sprite_preview_base
from pq_wiki.texture_service import upload_raw_bytes_named, upload_sprite_if_possible
from pq_wiki.wikitext_util import html_to_wikitext, template_invocation

# West animations aren't needed for the wiki; omit w_* to save time/uploads.
_DIRECTION_ORDER = ("e", "n", "s")
_ACTION_ORDER = ("idle", "walk", "attack")

_DIRECTION_LABEL = {
    "e": "East",
    "n": "North",
    "s": "South",
    "w": "West",
}

_ACTION_LABEL = {
    "idle": "Idle",
    "walk": "Walk",
    "attack": "Attack",
}

_RARITY_LABEL = ("Common", "Uncommon", "Rare", "Super Rare", "Super Secret Rare")
_RARITY_COLOR = ("#8B4513", "#C0C0C0", "#FFD700", "#4169E1", "#9932CC")


def _format_animation_caption(anim_key: str) -> str:
    parts = anim_key.split("_", 1)
    if len(parts) != 2:
        return anim_key.replace("_", " ").title()
    d, a = parts[0].lower(), parts[1].lower()
    dn = _DIRECTION_LABEL.get(d, d.upper())
    an = _ACTION_LABEL.get(a, a.title())
    return f"{dn} {an}"


def _rarity_head_wikitext(rarity: int) -> str:
    r = min(max(int(rarity), 0), 4)
    label = _RARITY_LABEL[r]
    color = _RARITY_COLOR[r]
    return f"'''Skin''' · <span style=\"color:{color};font-weight:bold\">{label}</span>"


def _upload_skin_animation_gif(
    site: pywikibot.Site,
    skin: dict,
    anim_key: str,
    sheet: Image.Image,
    version: str,
) -> str:
    anims = skin.get("Animations") or {}
    anim = anims.get(anim_key)
    if not anim:
        return ""
    try:
        # Wiki preview: fixed 5 fps (in-game Fps is dynamic).
        data = render_animation_to_gif_bytes(anim, sheet, fps_override=5.0)
    except Exception:
        return ""
    data = normalize_gif_bytes_for_imagemagick(data)
    sz = anim.get("Size") or {}
    fw = int(sz.get("X") or sz.get("x") or 50)
    sid = int(skin.get("Id") or 0)
    sname = str(skin.get("Name") or f"Skin {sid}")
    w = upload_raw_bytes_named(
        site,
        data,
        "gif",
        skin_animation_base(sid, sname, anim_key),
        version,
        thumb_size=max(1, fw),
    )
    return w


def _build_animations_section(
    site: pywikibot.Site,
    skin: dict,
    version: str,
) -> str:
    anims = skin.get("Animations") or {}
    if not anims:
        return ""
    tex = get_texture_url(skin.get("Sprite"))
    aid = parse_asset_id(tex or "")
    if not aid:
        return ""
    try:
        raw = fetch_asset_bytes(aid)
        sheet = Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception:
        return ""

    rows_html: list[str] = []
    for d in _DIRECTION_ORDER:
        if not any(f"{d}_{a}" in anims for a in _ACTION_ORDER):
            continue
        cells: list[str] = []
        for a in _ACTION_ORDER:
            key = f"{d}_{a}"
            if key not in anims:
                cells.append("<td></td>")
                continue
            gif_w = _upload_skin_animation_gif(site, skin, key, sheet, version)
            cap = _format_animation_caption(key).replace("|", " ")
            if gif_w:
                cells.append(
                    f'<td style="vertical-align:top;text-align:center;padding:6px">'
                    f"{gif_w}<br /><small>{cap}</small></td>"
                )
            else:
                cells.append("<td></td>")
        rows_html.append("<tr>" + "".join(cells) + "</tr>")

    if not rows_html:
        return ""
    table = (
        '<table class="wikitable" style="margin:0 auto;border-collapse:collapse">'
        + "".join(rows_html)
        + "</table>"
    )
    return "== Animations ==\n" + table


def build_skin_wikitext(
    site: pywikibot.Site,
    skin: dict,
    version: str,
    unreleased: bool = False,
) -> str:
    sid = int(skin.get("Id") or 0)
    name = str(skin.get("Name") or f"Skin {sid}")
    desc = html_to_wikitext(str(skin.get("Description") or ""))
    desc_block = f"''{desc}''" if desc else ""
    rarity = int(skin.get("Rarity") or 0)
    head = _rarity_head_wikitext(rarity)
    animations = _build_animations_section(site, skin, version)

    cat_lines = ["[[Category:Character skins]]"]
    if unreleased:
        cat_lines.append("[[Category:Unreleased]]")
    categories_block = "\n".join(cat_lines)

    body = template_invocation(
        "PQ Skin",
        [
            ("name", name),
            ("head", head),
            ("desc", desc_block),
            ("animations", animations),
            ("categories", categories_block),
        ],
        always_emit_keys=frozenset({"name", "head"}),
    )
    sprite_preview = upload_sprite_if_possible(
        site,
        skin.get("Sprite"),
        version,
        logical_name=skin_sprite_preview_base(sid, name),
    )
    desc_plain = plain_text_for_seo(desc)
    seo_desc = (
        f"{name} — {desc_plain}. Pixel Quest Wiki character skin."
        if desc_plain
        else f"{name} — Pixel Quest Wiki character skin."
    )
    seo = wiki_seo_block(
        site,
        page_title=name,
        description=seo_desc,
        wiki_image_filename=first_wiki_filename_from_file_wikitext(sprite_preview),
        image_alt=f"{name} skin",
    )
    return f"{body}\n\n{seo}"
