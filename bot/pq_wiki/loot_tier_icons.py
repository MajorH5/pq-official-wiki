from __future__ import annotations

import io
from typing import Iterable, Optional

import pywikibot
from PIL import Image

from pq_wiki.roblox_assets import fetch_asset_bytes, parse_asset_id
from pq_wiki.texture_names import loot_drop_base
from pq_wiki.texture_service import upload_raw_bytes_named

_CELL_SIZE = 50
_CHEST_Y = 0
_BAG_Y = 50


def _sheet_asset_id_from_dump(datadump: dict) -> Optional[str]:
    textures = datadump.get("Textures") or {}
    tex = textures.get("LOOT_CONTAINERS_8X8_RENDERED")
    if not tex:
        return None
    if isinstance(tex, dict):
        tex = tex.get("Texture") or tex.get("texture")
    if not isinstance(tex, str):
        return None
    return parse_asset_id(tex)


def _crop_cell(sheet: Image.Image, tier: int, y: int) -> bytes:
    x = tier * _CELL_SIZE
    icon = sheet.crop((x, y, x + _CELL_SIZE, y + _CELL_SIZE)).convert("RGBA")
    buf = io.BytesIO()
    icon.save(buf, format="PNG")
    return buf.getvalue()


def build_drop_tier_wikitext_map(
    site: pywikibot.Site,
    datadump: dict,
    version: str,
    tiers: Iterable[int],
) -> dict[int, str]:
    """
    Returns dropTierType -> '<bag 40px> <chest 40px>' wikitext.
    Missing/failed icons are omitted.
    """
    aid = _sheet_asset_id_from_dump(datadump)
    if not aid:
        return {}

    raw = fetch_asset_bytes(aid)
    sheet = Image.open(io.BytesIO(raw)).convert("RGBA")
    out: dict[int, str] = {}
    for t in sorted(set(int(x) for x in tiers)):
        bag_bytes = _crop_cell(sheet, t, _BAG_Y)
        chest_bytes = _crop_cell(sheet, t, _CHEST_Y)

        bag_w = upload_raw_bytes_named(
            site,
            bag_bytes,
            "png",
            loot_drop_base("bag", t),
            version,
            thumb_size=40,
        )
        chest_w = upload_raw_bytes_named(
            site,
            chest_bytes,
            "png",
            loot_drop_base("chest", t),
            version,
            thumb_size=40,
        )
        combo = " ".join(x for x in (chest_w, bag_w) if x)
        if combo:
            out[t] = combo
    return out


def build_drop_tier_icon_parts_map(
    site: pywikibot.Site,
    datadump: dict,
    version: str,
    tiers: Iterable[int],
) -> dict[int, dict[str, str]]:
    """
    Returns dropTierType -> {"chest": ..., "bag": ...} (40px each).
    """
    aid = _sheet_asset_id_from_dump(datadump)
    if not aid:
        return {}

    raw = fetch_asset_bytes(aid)
    sheet = Image.open(io.BytesIO(raw)).convert("RGBA")
    out: dict[int, dict[str, str]] = {}
    for t in sorted(set(int(x) for x in tiers)):
        bag_bytes = _crop_cell(sheet, t, _BAG_Y)
        chest_bytes = _crop_cell(sheet, t, _CHEST_Y)

        bag_w = upload_raw_bytes_named(
            site,
            bag_bytes,
            "png",
            loot_drop_base("bag", t),
            version,
            thumb_size=40,
        )
        chest_w = upload_raw_bytes_named(
            site,
            chest_bytes,
            "png",
            loot_drop_base("chest", t),
            version,
            thumb_size=40,
        )
        out[t] = {"chest": chest_w, "bag": bag_w}
    return out
