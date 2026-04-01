"""
Chest variant icons from ITEM_SPAWNS_* sheets (matches in-game UV math).

Positive ChestId: ITEM_SPAWNS_8X8_RENDERED, 50×50 cells, base index 21, sheet width 7.
Negative ChestId: ITEM_SPAWNS_16X16_RENDERED, 90×90 cells, base index 16, sheet width 6;
effective index uses abs(chestId) - 1.
"""

from __future__ import annotations

import io
from typing import Any

from PIL import Image

from pq_wiki.roblox_assets import fetch_asset_bytes, parse_asset_id

TEX_KEY_8 = "ITEM_SPAWNS_8X8_RENDERED"
TEX_KEY_16 = "ITEM_SPAWNS_16X16_RENDERED"


def chest_spawn_cell_rect(chest_id: int) -> tuple[int, int, int, int, bool]:
    """left, top, width, height, use_8x8_sheet (50px vs 90px cell)."""
    if chest_id >= 0:
        base_idx = 21
        sheet_w = 7
        size = 50
        ck = chest_id
        use_8 = True
    else:
        base_idx = 16
        sheet_w = 6
        size = 90
        ck = abs(chest_id) - 1
        use_8 = False
    current_index = base_idx + ck
    col = current_index % sheet_w
    row = current_index // sheet_w
    left = col * size
    top = row * size
    return (left, top, size, size, use_8)


def chest_spawn_png_bytes(chest_id: int, textures: dict[str, Any]) -> bytes | None:
    left, top, w, h, use_8 = chest_spawn_cell_rect(chest_id)
    key = TEX_KEY_8 if use_8 else TEX_KEY_16
    url = textures.get(key)
    if not url or not isinstance(url, str):
        return None
    aid = parse_asset_id(url)
    if not aid:
        return None
    try:
        raw = fetch_asset_bytes(aid)
        sheet = Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception:
        return None
    sw, sh = sheet.size
    if left + w > sw or top + h > sh:
        return None
    crop = sheet.crop((left, top, left + w, top + h))
    buf = io.BytesIO()
    crop.save(buf, format="PNG")
    return buf.getvalue()
