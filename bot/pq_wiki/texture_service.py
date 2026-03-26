from __future__ import annotations

import io
import re
from pathlib import Path

import pywikibot
from PIL import Image

from pq_wiki import sprites
from pq_wiki.config import TEXTURE_CACHE_DIR, ensure_dirs
from pq_wiki.sprites import (
    get_texture_url,
    normalize_gif_bytes_for_imagemagick,
    projectile_sprite_to_bytes,
)
from pq_wiki.wiki_assets import ensure_file_uploaded, file_wikitext


def _cache_path(semantic_base: str, ext: str) -> Path:
    ensure_dirs()
    safe = re.sub(r"[^a-z0-9_.-]", "_", semantic_base.lower())
    return TEXTURE_CACHE_DIR / f"{safe}.{ext}"


def _load_cached_texture(logical_name: str) -> tuple[bytes, str] | None:
    """
    Skip Roblox fetch + PIL when TEXTURE_CACHE_DIR already has this render.
    (Speeds items with many dropped-by entity icons on repeat imports.)
    """
    for ext in ("png", "gif"):
        p = _cache_path(logical_name, ext)
        if p.exists() and p.stat().st_size > 0:
            return p.read_bytes(), ext
    return None


def _dimensions_from_bytes(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as im:
        im.seek(0)
        return im.size


def upload_sprite_if_possible(
    site: pywikibot.Site,
    sprite: dict | None,
    version: str,
    thumb_size: int | None = None,
    *,
    logical_name: str,
) -> str:
    """Render sprite bytes and upload as File:{logical_name}.png|gif"""
    from pq_wiki.import_log import get_import_logger

    log = get_import_logger()
    if not sprite or not get_texture_url(sprite):
        log.debug("Sprite missing or no texture URL")
        return ""
    cached = _load_cached_texture(logical_name)
    if cached is not None:
        data, ext = cached
    else:
        try:
            data, ext = sprites.render_sprite_object(sprite)
        except Exception as e:
            log.warning("Sprite render failed: %s", e)
            return ""

        if ext == "gif":
            data = normalize_gif_bytes_for_imagemagick(data)

    path = _cache_path(logical_name, ext)
    if not path.exists():
        path.write_bytes(data)

    try:
        fname = ensure_file_uploaded(site, logical_name, ext, path, version)
        w, _h = _dimensions_from_bytes(data)
        display_w = thumb_size if thumb_size is not None else max(1, w)
        return file_wikitext(fname, display_w)
    except Exception as e:
        log.warning("Wiki image upload failed: %s", e)
        return ""


def upload_sprite_thumb_block(
    site: pywikibot.Site,
    sprite: dict | None,
    version: str,
    thumb_size: int,
    caption: str,
    *,
    logical_name: str,
) -> str:
    """Uploaded sprite as a thumb with caption (no inline pixel-art span)."""
    w = upload_sprite_if_possible(site, sprite, version, thumb_size=thumb_size, logical_name=logical_name)
    if not w:
        return ""
    m = re.search(r"\[\[File:([^|]+)\|", w)
    if not m:
        return ""
    fname = m.group(1)
    safe = caption.replace("|", " ")
    return f"[[File:{fname}|thumb|{thumb_size}px|{safe}]]"


def upload_raw_bytes_named(
    site: pywikibot.Site,
    data: bytes,
    ext: str,
    logical_name: str,
    version: str,
    thumb_size: int | None = None,
    max_thumb_size: int | None = None,
) -> str:
    """Upload raw PNG/GIF bytes under a semantic filename (no hash)."""
    ext = ext.lower()
    if ext == "gif":
        data = normalize_gif_bytes_for_imagemagick(data)
    path = _cache_path(logical_name, ext)
    if not path.exists():
        path.write_bytes(data)
    fname = ensure_file_uploaded(site, logical_name, ext, path, version)
    w, _h = _dimensions_from_bytes(data)
    display_w = thumb_size if thumb_size is not None else max(1, w)
    if max_thumb_size is not None:
        display_w = min(display_w, max_thumb_size)
    return file_wikitext(fname, display_w)


def upload_projectile_sprite(
    site: pywikibot.Site,
    proj_sprite: dict,
    version: str,
    *,
    logical_name: str,
    thumb_size: int | None = None,
    max_thumb_size: int | None = None,
) -> str:
    from pq_wiki.import_log import get_import_logger

    log = get_import_logger()
    cached = _load_cached_texture(logical_name)
    if cached is not None:
        data, ext = cached
    else:
        try:
            data, ext = projectile_sprite_to_bytes(proj_sprite)
        except Exception as e:
            log.debug("Projectile sprite failed: %s", e)
            return ""
    return upload_raw_bytes_named(
        site,
        data,
        ext,
        logical_name,
        version,
        thumb_size=thumb_size,
        max_thumb_size=max_thumb_size,
    )


def upload_portal_preview(
    site: pywikibot.Site,
    portal: dict | None,
    version: str,
    *,
    logical_name: str,
    thumb_size: int | None = None,
) -> str:
    if not portal:
        return ""
    prev = sprites.portal_sprite_preview_bytes(portal)
    if not prev:
        return ""
    data, ext = prev
    return upload_raw_bytes_named(site, data, ext, logical_name, version, thumb_size=thumb_size)
