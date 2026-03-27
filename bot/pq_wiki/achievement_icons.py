"""Achievement sheet: Textures.ACHIEVEMENTS_16X16_RENDERED_3X — crop by (sequence, category)."""

from __future__ import annotations

import io
from typing import Any

import pywikibot
from PIL import Image

from pq_wiki.datadump_helpers import texture_url_from_root
from pq_wiki.roblox_assets import fetch_asset_bytes, parse_asset_id
from pq_wiki.texture_names import achievement_icon_base
from pq_wiki.texture_service import upload_raw_bytes_named

_TEX_KEY = "ACHIEVEMENTS_16X16_RENDERED_3X"
# Vector2.new(17 + 2, 18 + 2) * 3
_CELL_W = (17 + 2) * 3
_CELL_H = (18 + 2) * 3


def upload_achievement_icon(
    site: pywikibot.Site,
    data: dict[str, Any],
    version: str,
    *,
    category_id: int,
    sequence_number: int,
    category_label: str,
    thumb_px: int | None = None,
) -> str:
    """Upload one cell; basename uses normalized category display name + sequence."""
    tex = texture_url_from_root(data, _TEX_KEY)
    aid = parse_asset_id(tex or "")
    if not aid:
        return ""
    try:
        raw = fetch_asset_bytes(aid)
        sheet = Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception:
        return ""

    x1 = int(sequence_number) * _CELL_W
    y1 = int(category_id) * _CELL_H
    x2 = x1 + _CELL_W
    y2 = y1 + _CELL_H
    if sheet.width < x2 or sheet.height < y2:
        return ""

    icon = sheet.crop((x1, y1, x2, y2))
    buf = io.BytesIO()
    icon.save(buf, format="PNG")
    tw = thumb_px if thumb_px is not None else _CELL_W
    return upload_raw_bytes_named(
        site,
        buf.getvalue(),
        "png",
        achievement_icon_base(category_label, int(sequence_number)),
        version,
        thumb_size=tw,
    )
