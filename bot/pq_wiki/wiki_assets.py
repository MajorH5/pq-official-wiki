from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pywikibot

from pq_wiki.config import WIKI_UPLOAD_MAP_PATH, ensure_dirs


def _load_map() -> dict:
    ensure_dirs()
    if not WIKI_UPLOAD_MAP_PATH.exists():
        return {}
    try:
        return json.loads(WIKI_UPLOAD_MAP_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_map(m: dict) -> None:
    ensure_dirs()
    WIKI_UPLOAD_MAP_PATH.write_text(json.dumps(m, indent=2, sort_keys=True), encoding="utf-8")


def wiki_filename_for_hash(content_hash: str, ext: str) -> str:
    short = content_hash[:16]
    return f"PQ_tex_{short}.{ext}"


def ensure_file_uploaded(
    site: pywikibot.Site,
    content_hash: str,
    ext: str,
    source_path: Path,
    version: str,
) -> str:
    """
    Upload file if missing. Returns wiki filename (no File: prefix).
    """
    fname = wiki_filename_for_hash(content_hash, ext)
    m = _load_map()
    if content_hash in m:
        existing = m[content_hash]
        fp = pywikibot.FilePage(site, f"File:{existing}")
        if fp.exists():
            return existing

    fp = pywikibot.FilePage(site, f"File:{fname}")
    if fp.exists():
        m[content_hash] = fname
        _save_map(m)
        return fname

    comment = f"PQ bot texture {content_hash[:12]}… (datadump {version})"
    fp.upload(
        source=str(source_path),
        comment=comment,
        ignore_warnings=True,
    )
    m[content_hash] = fname
    _save_map(m)
    return fname


_PIXEL_ART_STYLE = (
    "image-rendering: pixelated; "
    "image-rendering: -moz-crisp-edges; "
    "image-rendering: crisp-edges"
)


def file_wikitext(fname: str, size: int, pixelated: bool = True) -> str:
    """Wikitext for an image at ``size`` px width (match native sprite size for crisp pixels)."""
    if not fname:
        return ""
    img = f"[[File:{fname}|{size}px]]"
    if pixelated:
        return f'<span style="{_PIXEL_ART_STYLE}; display: inline-block">{img}</span>'
    return img


_PIXEL_ART_CSS = """
/* PQ bot: crisp pixel-art sprites (nearest-neighbor scaling) */
img[src*="PQ_tex_"] {
    image-rendering: pixelated;
    image-rendering: -moz-crisp-edges;
    image-rendering: crisp-edges;
}
"""


def ensure_pixel_art_css(site: pywikibot.Site) -> None:
    """Ensure MediaWiki:Common.css includes pixel-art rule for PQ texture images."""
    page = pywikibot.Page(site, "MediaWiki:Common.css")
    text = page.text or ""
    marker = "PQ bot: crisp pixel-art"
    if marker in text:
        return
    addition = _PIXEL_ART_CSS.strip()
    new_text = f"{text.rstrip()}\n\n{addition}\n" if text.strip() else f"{addition}\n"
    page.text = new_text
    page.save(
        summary="Add PQ bot pixel-art CSS (nearest-neighbor for sprites)",
        minor=True,
    )
