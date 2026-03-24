from __future__ import annotations

import io
from pathlib import Path

import pywikibot
from PIL import Image

from pq_wiki import sprites
from pq_wiki.config import TEXTURE_CACHE_DIR, ensure_dirs
from pq_wiki.sprites import (
    content_hash,
    get_texture_url,
    projectile_sprite_to_bytes,
    sprite_signature_for_hash,
)
from pq_wiki.wiki_assets import ensure_file_uploaded, file_wikitext


def _cache_path(h: str, ext: str) -> Path:
    ensure_dirs()
    return TEXTURE_CACHE_DIR / f"{h}.{ext}"


def _dimensions_from_bytes(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as im:
        im.seek(0)
        return im.size


def upload_sprite_if_possible(
    site: pywikibot.Site,
    sprite: dict | None,
    version: str,
    thumb_size: int | None = None,
) -> str:
    from pq_wiki.import_log import get_import_logger
    log = get_import_logger()
    if not sprite or not get_texture_url(sprite):
        log.debug("Sprite missing or no texture URL")
        return ""
    sig = sprite_signature_for_hash(sprite)
    h = content_hash(sig)
    try:
        data, ext = sprites.render_sprite_object(sprite)
    except Exception as e:
        log.warning("Sprite render failed: %s", e)
        return ""

    path = _cache_path(h, ext)
    if not path.exists():
        path.write_bytes(data)

    try:
        fname = ensure_file_uploaded(site, h, ext, path, version)
        w, _h = _dimensions_from_bytes(data)
        display_w = thumb_size if thumb_size is not None else max(1, w)
        return file_wikitext(fname, display_w)
    except Exception as e:
        log.warning("Wiki image upload failed: %s", e)
        return ""


def upload_raw_bytes_fixed_hash(
    site: pywikibot.Site,
    data: bytes,
    ext: str,
    content_key: str,
    version: str,
    thumb_size: int | None = None,
    max_thumb_size: int | None = None,
) -> str:
    """Use deterministic hash from content_key (sprite sig) for stable filenames."""
    sig_hash = content_hash(content_key)
    path = _cache_path(sig_hash, ext)
    if not path.exists():
        path.write_bytes(data)
    fname = ensure_file_uploaded(site, sig_hash, ext, path, version)
    w, _h = _dimensions_from_bytes(data)
    display_w = thumb_size if thumb_size is not None else max(1, w)
    if max_thumb_size is not None:
        display_w = min(display_w, max_thumb_size)
    return file_wikitext(fname, display_w)


def upload_projectile_sprite(
    site: pywikibot.Site,
    proj_sprite: dict,
    version: str,
    thumb_size: int | None = None,
    max_thumb_size: int | None = None,
) -> str:
    from pq_wiki.import_log import get_import_logger
    log = get_import_logger()
    try:
        data, ext = projectile_sprite_to_bytes(proj_sprite)
    except Exception as e:
        log.debug("Projectile sprite failed: %s", e)
        return ""
    # Include speed profile marker so updated projectile timing invalidates old cached GIFs.
    sig = sprite_signature_for_hash({"Projectile": proj_sprite, "fps_scale": 0.5})
    return upload_raw_bytes_fixed_hash(
        site,
        data,
        ext,
        sig,
        version,
        thumb_size=thumb_size,
        max_thumb_size=max_thumb_size,
    )


def upload_portal_preview(
    site: pywikibot.Site,
    portal: dict | None,
    version: str,
    thumb_size: int | None = None,
) -> str:
    if not portal:
        return ""
    prev = sprites.portal_sprite_preview_bytes(portal)
    if not prev:
        return ""
    data, ext = prev
    sig = sprite_signature_for_hash({"Portal": portal, "preview": "idle_first"})
    return upload_raw_bytes_fixed_hash(site, data, ext, sig, version, thumb_size=thumb_size)
