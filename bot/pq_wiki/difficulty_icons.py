from __future__ import annotations

import pywikibot

from pq_wiki.roblox_assets import fetch_asset_bytes, parse_asset_id
from pq_wiki.sprites import content_hash
from pq_wiki.texture_service import upload_raw_bytes_fixed_hash


def build_difficulty_skull_wikitext(
    site: pywikibot.Site,
    datadump: dict,
    version: str,
    size_px: int = 40,
) -> str:
    textures = datadump.get("Textures") or {}
    tex = textures.get("UI_RIFT_DIFFICULTY_SKULL")
    if not isinstance(tex, str):
        return ""
    aid = parse_asset_id(tex)
    if not aid:
        return ""
    raw = fetch_asset_bytes(aid)
    key = content_hash(f"difficulty-skull:{aid}:{size_px}")
    return upload_raw_bytes_fixed_hash(
        site,
        raw,
        "png",
        content_key=key,
        version=version,
        thumb_size=size_px,
    )
