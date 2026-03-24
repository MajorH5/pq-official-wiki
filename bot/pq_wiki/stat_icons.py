from __future__ import annotations

import io
from typing import Optional

import pywikibot
from PIL import Image

from pq_wiki.roblox_assets import fetch_asset_bytes, parse_asset_id
from pq_wiki.sprites import content_hash
from pq_wiki.texture_service import upload_raw_bytes_fixed_hash

# Canonical stat order in the 18x18 strip row.
STAT_INDEX_MAP = {
    "health": 0,
    "mana": 1,
    "defense": 2,
    "vitality": 3,
    "speed": 4,
    "wisdom": 5,
    "attack": 6,
    "dexterity": 7,
}

_ICON_SIZE = 18
_ICON_ROW_Y = 18


def _sheet_asset_id_from_dump(datadump: dict) -> Optional[str]:
    textures = datadump.get("Textures") or {}
    tex = textures.get("STAT_ICONS_16X16_RENDERED_1X")
    if not tex:
        return None
    if isinstance(tex, dict):
        tex = tex.get("Texture") or tex.get("texture")
    if not isinstance(tex, str):
        return None
    return parse_asset_id(tex)


def build_stat_icon_wikitext_map(
    site: pywikibot.Site,
    datadump: dict,
    version: str,
) -> dict[str, str]:
    """
    Returns lowercase stat-name -> 18px file wikitext.
    Missing/failed icons are omitted.
    """
    aid = _sheet_asset_id_from_dump(datadump)
    if not aid:
        return {}

    raw = fetch_asset_bytes(aid)
    sheet = Image.open(io.BytesIO(raw)).convert("RGBA")
    out: dict[str, str] = {}
    for stat, idx in STAT_INDEX_MAP.items():
        x = idx * _ICON_SIZE
        icon = sheet.crop((x, _ICON_ROW_Y, x + _ICON_SIZE, _ICON_ROW_Y + _ICON_SIZE))
        buf = io.BytesIO()
        icon.save(buf, format="PNG")
        data = buf.getvalue()
        key = content_hash(f"stat-icon:{aid}:{stat}:{_ICON_SIZE}:{_ICON_ROW_Y}")
        w = upload_raw_bytes_fixed_hash(
            site,
            data,
            "png",
            content_key=key,
            version=version,
            thumb_size=_ICON_SIZE,
        )
        if w:
            out[stat] = w
    return out


def stat_label(name: str, icon_map: dict[str, str] | None) -> str:
    if not icon_map:
        return name
    icon = icon_map.get(name.lower())
    return f"{icon} {name}" if icon else name
