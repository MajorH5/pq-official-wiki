from __future__ import annotations

import io
from typing import Optional

import pywikibot
from PIL import Image

from pq_wiki.roblox_assets import fetch_asset_bytes, parse_asset_id
from pq_wiki.sprites import content_hash
from pq_wiki.texture_service import upload_raw_bytes_fixed_hash

_ICON_SIZE = 16

# Dump-provided atlas positions.
_STATUS_POSITIONS: dict[str, dict[str, int]] = {
    "Reflecting": {"Y": 16, "X": 80},
    "Ignored": {"Y": 16, "X": 0},
    "Petrify Immune": {"Y": 16, "X": 64},
    "Dazed": {"Y": 16, "X": 80},
    "Exposed": {"Y": 16, "X": 64},
    "Vampric": {"Y": 16, "X": 64},
    "Hastened": {"Y": 16, "X": 48},
    "Recharging": {"Y": 16, "X": 32},
    "Bleeding": {"Y": 16, "X": 0},
    "Burning": {"Y": 16, "X": 0},
    "Protected": {"Y": 16, "X": 0},
    "Mana Burn": {"Y": 16, "X": 32},
    "Sick": {"Y": 16, "X": 0},
    "Speedy": {"Y": 16, "X": 48},
    "Frost": {"Y": 16, "X": 0},
    "Regeneration": {"Y": 16, "X": 16},
    "Quiet": {"Y": 16, "X": 16},
    "Petrify": {"Y": 16, "X": 48},
    "Rallied": {"Y": 16, "X": 150},
    "Invulnerable": {"Y": 16, "X": 16},
    "Focused": {"Y": 16, "X": 32},
    "HP Boost": {"Y": 16, "X": 32},
    "Spectating": {"Y": 16, "X": 32},
    "Healing": {"Y": 16, "X": 48},
    "Paralyze": {"Y": 16, "X": 0},
    "Tanky": {"Y": 16, "X": 32},
    "Slowed": {"Y": 16, "X": 80},
    "Vulnerable": {"Y": 16, "X": 64},
    "AFK": {"Y": 16, "X": 16},
    "Stunned": {"Y": 16, "X": 16},
    "MP Boost": {"Y": 16, "X": 32},
    "Strengthened": {"Y": 16, "X": 48},
    "Armored": {"Y": 16, "X": 16},
    "Armor Broken": {"Y": 16, "X": 0},
}


def _sheet_asset_id_from_dump(datadump: dict) -> Optional[str]:
    textures = datadump.get("Textures") or {}
    tex = textures.get("STATUS_EFFECTS_16X16")
    if not tex:
        return None
    if isinstance(tex, dict):
        tex = tex.get("Texture") or tex.get("texture")
    if not isinstance(tex, str):
        return None
    return parse_asset_id(tex)


def build_status_effect_icon_wikitext_map(
    site: pywikibot.Site,
    datadump: dict,
    version: str,
) -> dict[str, str]:
    """
    Returns lowercase status-name -> 16px file wikitext.
    """
    aid = _sheet_asset_id_from_dump(datadump)
    if not aid:
        return {}

    raw = fetch_asset_bytes(aid)
    sheet = Image.open(io.BytesIO(raw)).convert("RGBA")
    out: dict[str, str] = {}
    for name, pos in _STATUS_POSITIONS.items():
        x = int(pos.get("X", 0))
        y = int(pos.get("Y", 0))
        icon = sheet.crop((x, y, x + _ICON_SIZE, y + _ICON_SIZE))
        buf = io.BytesIO()
        icon.save(buf, format="PNG")
        data = buf.getvalue()
        key = content_hash(f"status-icon:{aid}:{name}:{x}:{y}:{_ICON_SIZE}")
        w = upload_raw_bytes_fixed_hash(
            site,
            data,
            "png",
            content_key=key,
            version=version,
            thumb_size=_ICON_SIZE,
        )
        if w:
            out[name.lower()] = w
    return out
