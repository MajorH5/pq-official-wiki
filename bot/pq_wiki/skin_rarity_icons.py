from __future__ import annotations

import io
from typing import Iterable, Optional

import pywikibot
from PIL import Image

from pq_wiki.roblox_assets import fetch_asset_bytes, parse_asset_id
from pq_wiki.sprites import render_skin_rarity_icon_bytes
from pq_wiki.texture_names import skin_rarity_base
from pq_wiki.texture_service import upload_raw_bytes_named

_TEXTURE_KEY = "TIER_ICONS_16X16_RENDERED_3X_OUTLINE"


def _sheet_asset_id_from_dump(datadump: dict) -> Optional[str]:
    textures = datadump.get("Textures") or {}
    tex = textures.get(_TEXTURE_KEY)
    if not tex:
        return None
    if isinstance(tex, dict):
        tex = tex.get("Texture") or tex.get("texture")
    if not isinstance(tex, str):
        return None
    return parse_asset_id(tex)


def build_skin_rarity_wikitext_map(
    site: pywikibot.Site,
    datadump: dict,
    version: str,
    rarities: Iterable[int],
) -> dict[int, str]:
    """
    rarity -> small wikitext icon (for loot overlay), 16px thumb.
    """
    aid = _sheet_asset_id_from_dump(datadump)
    if not aid:
        return {}

    raw = fetch_asset_bytes(aid)
    sheet = Image.open(io.BytesIO(raw)).convert("RGBA")
    out: dict[int, str] = {}
    for r in sorted(set(int(x) for x in rarities)):
        if r < 0 or r > 4:
            continue
        try:
            data, ext = render_skin_rarity_icon_bytes(r, sheet)
        except Exception:
            continue
        w = upload_raw_bytes_named(
            site,
            data,
            ext,
            skin_rarity_base(r),
            version,
            thumb_size=16,
        )
        if w:
            out[r] = w
    return out
