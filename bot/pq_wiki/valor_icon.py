"""Inline Valor icon from Textures.VALOR_ICONS_8X8_RENDERED_2X (same crop as in-game)."""

from __future__ import annotations

import io
from typing import Optional

import pywikibot
from PIL import Image

from pq_wiki.roblox_assets import fetch_asset_bytes, parse_asset_id
from pq_wiki.sprites import content_hash
from pq_wiki.texture_service import upload_raw_bytes_fixed_hash

# imageRectSize = Vector2.new((8 + 2), (8 + 2)) * 2  → 20×20
# imageRectOffset = Vector2.new(2, 0) * ((8 + 2) * 2) → (40, 0)
_VALOR_CROP_X = 40
_VALOR_CROP_Y = 0
_VALOR_SIZE = 20


def _sheet_asset_id_from_dump(datadump: dict) -> Optional[str]:
    textures = datadump.get("Textures") or {}
    tex = textures.get("VALOR_ICONS_8X8_RENDERED_2X")
    if not tex:
        return None
    if isinstance(tex, dict):
        tex = tex.get("Texture") or tex.get("texture")
    if not isinstance(tex, str):
        return None
    return parse_asset_id(tex)


def build_valor_icon_wikitext(
    site: pywikibot.Site,
    datadump: dict,
    version: str,
    thumb_size: int = 16,
) -> str:
    """
    Single uploaded icon wikitext for Valor table labels, or "" if missing/failed.
    """
    aid = _sheet_asset_id_from_dump(datadump)
    if not aid:
        return ""

    raw = fetch_asset_bytes(aid)
    sheet = Image.open(io.BytesIO(raw)).convert("RGBA")
    x1 = _VALOR_CROP_X
    y1 = _VALOR_CROP_Y
    x2 = x1 + _VALOR_SIZE
    y2 = y1 + _VALOR_SIZE
    if sheet.width < x2 or sheet.height < y2:
        return ""
    icon = sheet.crop((x1, y1, x2, y2))
    buf = io.BytesIO()
    icon.save(buf, format="PNG")
    data = buf.getvalue()
    key = content_hash(f"valor-icon:{aid}:{_VALOR_CROP_X}:{_VALOR_CROP_Y}:{_VALOR_SIZE}")
    return upload_raw_bytes_fixed_hash(
        site,
        data,
        "png",
        content_key=key,
        version=version,
        thumb_size=thumb_size,
    )


def valor_label(text: str, valor_icon_wikitext: str | None) -> str:
    """Prefix table header cell with Valor icon when available."""
    if not valor_icon_wikitext:
        return text
    return f"{valor_icon_wikitext} {text}".strip()
