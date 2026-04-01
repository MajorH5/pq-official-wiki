from __future__ import annotations

import os
import json
import re
from pathlib import Path
from typing import Any, Optional

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


def sanitize_filename_base(name: str) -> str:
    """Single path segment: a-z 0-9 _ . -"""
    s = re.sub(r"[^a-z0-9_.-]", "_", (name or "").lower().strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "asset"


def wiki_filename_for_semantic(base: str, ext: str) -> str:
    return f"{sanitize_filename_base(base)}.{ext.lower()}"


def _filename_from_map_entry(value: Any) -> Optional[str]:
    """wiki_image_map.json may store a bare filename or {filename, sha256, ...}."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        fn = value.get("filename") or value.get("name")
        if isinstance(fn, str) and fn.strip():
            return fn.strip()
    return None


def ensure_file_uploaded(
    site: pywikibot.Site,
    semantic_base: str,
    ext: str,
    source_path: Path,
    version: str,
) -> str:
    """
    Upload file if missing. semantic_base is filename without extension (searchable name).
    Map key = semantic_base|ext for idempotent re-imports.
    """
    dry_run_uploads = os.environ.get("PQ_BOT_DRY_RUN_UPLOADS", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    fname = wiki_filename_for_semantic(semantic_base, ext)
    map_key = f"{semantic_base}|{ext.lower()}"
    m = _load_map()
    if map_key in m:
        existing = _filename_from_map_entry(m[map_key])
        if existing:
            fp = pywikibot.FilePage(site, f"File:{existing}")
            if fp.exists():
                return existing

    fp = pywikibot.FilePage(site, f"File:{fname}")
    if fp.exists():
        if not dry_run_uploads:
            m[map_key] = fname
            _save_map(m)
        return fname

    # Preview/dry-run: do not upload; still return the deterministic filename that the
    # real import would link to.
    if dry_run_uploads:
        return fname

    comment = f"PQ bot texture {fname} (datadump {version})"
    fp.upload(
        source=str(source_path),
        comment=comment,
        ignore_warnings=True,
    )
    m[map_key] = fname
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
        return f'<span class="pq-pixel-sprite" style="{_PIXEL_ART_STYLE}; display: inline-block">{img}</span>'
    return img


_PIXEL_ART_CSS = """
/* PQ bot: crisp pixel-art sprites (nearest-neighbor scaling) */
.pq-pixel-sprite img,
img[src*="PQ_tex_"] {
    image-rendering: pixelated;
    image-rendering: -moz-crisp-edges;
    image-rendering: crisp-edges;
}
"""

_LOOT_CHEST_TOC_CSS = """
/* PQ bot: loot chest multi-variant pages — keep TOC scrollable so it does not stretch layout */
.mw-parser-output:has(.pq-loot-chest-root) > #toc {
	max-height: min(40vh, 22em);
	max-width: 22em;
	overflow-y: auto;
	overflow-x: hidden;
}

/* Vector 2022 (TOC in sidebar / pinnable panel) */
body:has(.pq-loot-chest-root) .vector-toc {
	max-height: min(75vh, 32em);
	overflow-y: auto;
	overflow-x: hidden;
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


def ensure_loot_chest_toc_css(site: pywikibot.Site) -> None:
    """Scrollable / height-limited TOC when .pq-loot-chest-root is present (import adds wrapper)."""
    page = pywikibot.Page(site, "MediaWiki:Common.css")
    text = page.text or ""
    marker = "PQ bot: loot chest multi-variant pages"
    if marker in text:
        return
    addition = _LOOT_CHEST_TOC_CSS.strip()
    new_text = f"{text.rstrip()}\n\n{addition}\n" if text.strip() else f"{addition}\n"
    page.text = new_text
    page.save(
        summary="Add PQ bot loot chest TOC layout (scrollable TOC)",
        minor=True,
    )
