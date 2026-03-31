from __future__ import annotations

from typing import Any

import pywikibot

from pq_wiki.seo import first_wiki_filename_from_file_wikitext, plain_text_for_seo, wiki_seo_block
from pq_wiki.texture_names import badge_sprite_base
from pq_wiki.texture_service import upload_sprite_if_possible
from pq_wiki.wikitext_util import html_to_wikitext, template_invocation


def build_badge_wikitext(
    site: pywikibot.Site,
    badge: dict[str, Any],
    version: str,
    *,
    unreleased: bool = False,
) -> str:
    bid = int(badge.get("Id") or 0)
    name = str(badge.get("Name") or f"Badge {bid}")
    desc = html_to_wikitext(str(badge.get("Description") or ""))
    desc_block = f"''{desc}''" if desc else ""

    sprite_w = upload_sprite_if_possible(
        site,
        badge.get("Sprite"),
        version,
        thumb_size=64,
        logical_name=badge_sprite_base(bid, name),
    )

    cat_lines = ["[[Category:Badges]]"]
    if unreleased:
        cat_lines.append("[[Category:Unreleased]]")
    categories_block = "\n".join(cat_lines)

    body = template_invocation(
        "PQ Badge",
        [
            ("name", name),
            ("sprite", sprite_w),
            ("desc", desc_block),
            ("categories", categories_block),
        ],
        always_emit_keys=frozenset({"name"}),
    )
    desc_plain = plain_text_for_seo(desc)
    seo_desc = (
        f"{name} — {desc_plain}. Pixel Quest Wiki badge."
        if desc_plain
        else f"{name} — Pixel Quest Wiki badge."
    )
    seo = wiki_seo_block(
        site,
        page_title=name,
        description=seo_desc,
        wiki_image_filename=first_wiki_filename_from_file_wikitext(sprite_w),
        image_alt=f"{name} badge",
    )
    return f"{body}\n\n{seo}"
