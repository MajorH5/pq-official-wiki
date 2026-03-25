from __future__ import annotations

import pywikibot

from pq_wiki.sprites import character_skin_animation_first_frame_png, content_hash
from pq_wiki.texture_service import upload_raw_bytes_fixed_hash


def _inject_file_link_target(img_wiki: str, page_path: str) -> str:
    marker = "]]"
    i = img_wiki.find(marker)
    if i == -1:
        return img_wiki
    return f"{img_wiki[:i]}|link={page_path}{img_wiki[i:]}"


def format_skin_drop_cell(
    site: pywikibot.Site,
    version: str,
    sid: int,
    skin_id_to_skin: dict[int, dict],
    skin_id_to_path: dict[int, str],
    skin_rarity_icon_wikitext: dict[int, str],
) -> str:
    """e_idle preview + skin rarity corner; links to skin wiki page."""
    sk = skin_id_to_skin.get(sid)
    path = skin_id_to_path.get(sid)
    if not sk or not path:
        return ""
    png = character_skin_animation_first_frame_png(sk, "e_idle")
    if not png:
        return ""
    key = content_hash(f"skin_drop_idle:{sid}")
    base = upload_raw_bytes_fixed_hash(site, png, "png", content_key=key, version=version, thumb_size=40)
    if not base:
        return ""
    base = _inject_file_link_target(base, path)
    name = str(sk.get("Name") or f"Skin {sid}")
    label = f"[[{path}|{name}]]"
    rarity = int(sk.get("Rarity") or 0)
    corner = ""
    if skin_rarity_icon_wikitext:
        corner = skin_rarity_icon_wikitext.get(rarity, "")
    if not corner:
        return f"{base} {label}".strip()
    return (
        '<span style="display:inline-block;position:relative;line-height:0;">'
        f"{base}"
        '<span style="position:absolute;right:-2px;bottom:-2px;pointer-events:none;">'
        f"{corner}"
        "</span></span> "
        f"{label}"
    ).strip()
