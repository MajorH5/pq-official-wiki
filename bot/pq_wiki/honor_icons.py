"""Upload honor rank crown crops from Textures.HONOR_ICONS_8X8_RENDERED_2X (20×20 per rank)."""

from __future__ import annotations

import io
from typing import Any

import pywikibot
from PIL import Image

from pq_wiki.datadump_helpers import texture_url_from_root
from pq_wiki.roblox_assets import fetch_asset_bytes, parse_asset_id
from pq_wiki.texture_names import honor_icon_base
from pq_wiki.texture_service import upload_raw_bytes_named

_CROP = 20
_TEX_KEY = "HONOR_ICONS_8X8_RENDERED_2X"


def _honor_rank_ids_and_names(data: dict[str, Any]) -> list[tuple[int, str]]:
    """HonorToName: string id -> display name; fall back to HonorIds enum order."""
    htn = data.get("HonorToName") or {}
    out: list[tuple[int, str]] = []
    if isinstance(htn, dict):
        for k, v in htn.items():
            try:
                rid = int(k)
            except (TypeError, ValueError):
                continue
            name = str(v).strip() or f"Rank {rid}"
            out.append((rid, name))
        out.sort(key=lambda x: x[0])
    if out:
        return out
    # Fallback: numeric keys only from HonorIds
    hid = data.get("HonorIds") or {}
    if isinstance(hid, dict):
        for _enum_name, rid in hid.items():
            try:
                ir = int(rid)
            except (TypeError, ValueError):
                continue
            out.append((ir, f"Honor {ir}"))
        out.sort(key=lambda x: x[0])
    return out


def build_honor_icon_wikitext_map(
    site: pywikibot.Site,
    data: dict[str, Any],
    version: str,
    thumb_px: int = 20,
) -> dict[int, str]:
    """rank_id -> [[File:...]] wikitext for honor crowns."""
    tex = texture_url_from_root(data, _TEX_KEY)
    aid = parse_asset_id(tex or "")
    if not aid:
        return {}
    try:
        raw = fetch_asset_bytes(aid)
        sheet = Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception:
        return {}

    rows = _honor_rank_ids_and_names(data)
    if not rows:
        return {}

    out: dict[int, str] = {}
    for rid, display in rows:
        x1 = rid * _CROP
        y1 = 0
        x2 = x1 + _CROP
        y2 = y1 + _CROP
        if sheet.width < x2 or sheet.height < y2:
            continue
        icon = sheet.crop((x1, y1, x2, y2))
        buf = io.BytesIO()
        icon.save(buf, format="PNG")
        w = upload_raw_bytes_named(
            site,
            buf.getvalue(),
            "png",
            honor_icon_base(display),
            version,
            thumb_size=thumb_px,
        )
        if w:
            out[rid] = w
    return out


def honor_bronze_wikitext(honor_map: dict[int, str]) -> str:
    return honor_map.get(0, "")
