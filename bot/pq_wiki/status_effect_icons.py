from __future__ import annotations

import io
from typing import Any, Optional

import pywikibot
from PIL import Image

from pq_wiki.roblox_assets import fetch_asset_bytes, parse_asset_id
from pq_wiki.sprites import get_texture_url, render_static_sprite
from pq_wiki.texture_names import status_effect_sprite_base
from pq_wiki.texture_service import upload_raw_bytes_named

_DISPLAY_16 = 16


def status_effects_atlas_texture_string(datadump: dict[str, Any]) -> Optional[str]:
    """Roblox texture string for the STATUS_EFFECTS_16X16 sheet (fallback when per-effect Sprite has no Texture)."""
    textures = datadump.get("Textures") or {}
    t = textures.get("STATUS_EFFECTS_16X16")
    if isinstance(t, dict):
        t = t.get("Texture") or t.get("texture")
    if isinstance(t, str) and t.strip():
        return t.strip()
    return None


def _sprite_dict_with_sheet(sprite: dict[str, Any], sheet_tex: str) -> dict[str, Any]:
    sp = dict(sprite)
    if not get_texture_url(sp):
        sp["Texture"] = sheet_tex
    return sp


def load_status_effect_atlas(datadump: dict[str, Any]) -> tuple[Image.Image, str] | None:
    tex = status_effects_atlas_texture_string(datadump)
    if not tex:
        return None
    aid = parse_asset_id(tex)
    if not aid:
        return None
    try:
        raw = fetch_asset_bytes(aid)
    except Exception:
        return None
    sheet = Image.open(io.BytesIO(raw)).convert("RGBA")
    return sheet, tex


def effect_entry_to_png_bytes(
    effect: dict[str, Any],
    default_sheet: Image.Image | None,
    default_sheet_tex: str,
) -> Optional[bytes]:
    sp = effect.get("Sprite")
    if not isinstance(sp, dict):
        return None
    tex = get_texture_url(sp)
    if tex:
        aid = parse_asset_id(tex)
        if aid:
            try:
                raw = fetch_asset_bytes(aid)
                own = Image.open(io.BytesIO(raw)).convert("RGBA")
                return render_static_sprite(sp, own)
            except Exception:
                return None
    if default_sheet is None or not (default_sheet_tex or "").strip():
        return None
    merged = _sprite_dict_with_sheet(sp, default_sheet_tex)
    try:
        return render_static_sprite(merged, default_sheet)
    except Exception:
        return None


def build_status_effect_icon_wikitext_map(
    site: pywikibot.Site,
    datadump: dict[str, Any],
    version: str,
) -> dict[str, str]:
    """
    Lowercase status effect Name -> 16px [[File:...]] wikitext from StatusEffects[].Sprite + atlas.
    """
    loaded = load_status_effect_atlas(datadump)
    if not loaded:
        return {}
    sheet, sheet_tex = loaded

    rows = datadump.get("StatusEffects") or []
    if not isinstance(rows, list):
        return {}

    out: dict[str, str] = {}
    for effect in rows:
        if not isinstance(effect, dict):
            continue
        name = str(effect.get("Name") or "").strip()
        if not name:
            continue
        try:
            eid = int(effect.get("Id") or 0)
        except (TypeError, ValueError):
            continue
        if eid < 0:
            continue
        png = effect_entry_to_png_bytes(effect, sheet, sheet_tex)
        if not png:
            continue
        w = upload_raw_bytes_named(
            site,
            png,
            "png",
            status_effect_sprite_base(eid, name),
            version,
            thumb_size=_DISPLAY_16,
        )
        if w:
            out[name.lower()] = w
    return out
