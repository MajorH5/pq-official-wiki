"""
Upload layout templates from repo files (mediawiki/wiki_templates/*.wikitext) to the wiki.

Usage:
  python -m pq_wiki import-templates
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault(
    "PYWIKIBOT_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
)

import pywikibot

from pq_wiki.config import WIKI_BOT_USER, WIKI_LAYOUT_TEMPLATES_DIR, ensure_dirs
from pq_wiki.import_log import get_import_logger
from pq_wiki.renderers.save import save_bot_page


def _wikitext_file_to_title(filename: str) -> str | None:
    """PQ_Item.wikitext -> Template:PQ Item ; PQ_Item_preload.wikitext -> Template:PQ Item/preload"""
    if not filename.endswith(".wikitext"):
        return None
    stem = filename[: -len(".wikitext")]
    if stem.endswith("_preload"):
        base = stem[: -len("_preload")].replace("_", " ")
        return f"Template:{base}/preload"
    return f"Template:{stem.replace('_', ' ')}"


def run_import_templates() -> dict:
    log = get_import_logger()
    ensure_dirs()
    root = WIKI_LAYOUT_TEMPLATES_DIR
    if not root.is_dir():
        raise FileNotFoundError(
            f"Layout templates directory not found: {root}\n"
            "Set WIKI_LAYOUT_TEMPLATES_DIR or mount mediawiki/wiki_templates (see TEMPLATES.md)."
        )

    site = pywikibot.Site("en", "pqwiki")
    pywikibot.config.verbose_output = os.environ.get("PQ_BOT_VERBOSE", "").lower() in (
        "1",
        "true",
        "yes",
    )
    site.login()
    log.info("Uploading layout templates from %s", root)

    stats: dict[str, int] = {}
    errors: list[str] = []

    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        title = _wikitext_file_to_title(path.name)
        if title is None:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            errors.append(f"{path.name}: {e}")
            log.error("Read failed %s: %s", path, e)
            continue

        t0 = time.perf_counter()
        try:
            r = save_bot_page(
                site,
                title,
                text,
                version="templates",
                bot_user=WIKI_BOT_USER,
                kind="template",
                force_overwrite=True,
            )
            stats[r] = stats.get(r, 0) + 1
            log.info(
                "template %s | result=%s | %.0fms",
                title,
                r,
                (time.perf_counter() - t0) * 1000,
            )
        except Exception as e:
            errors.append(title)
            log.error("FAILED %s\n%s", title, e)

    log.info("Template import finished stats=%s errors=%d", stats, len(errors))
    return {
        "ok": len(errors) == 0,
        "stats": stats,
        "errors": errors,
        "source": str(root),
    }


def main(argv: list[str]) -> int:
    _ = argv
    try:
        out = run_import_templates()
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
