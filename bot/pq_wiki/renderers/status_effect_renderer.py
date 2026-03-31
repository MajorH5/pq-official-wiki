from __future__ import annotations

from typing import Any

import pywikibot

from pq_wiki.renderers.pathing import STATUS_EFFECTS_INDEX_TITLE, _clean_title, status_effect_wikilink_path
from pq_wiki.seo import first_wiki_filename_from_file_wikitext, wiki_seo_block
from pq_wiki.status_effect_icons import effect_entry_to_png_bytes, load_status_effect_atlas
from pq_wiki.texture_names import status_effect_sprite_base
from pq_wiki.texture_service import upload_raw_bytes_named
from pq_wiki.wikitext_util import html_to_wikitext, wikitable

# Same 16×16 PNG as item/entity rows; display size in wikitext only (no second upload).
_PAGE_ICON_DISPLAY_PX = 48


def _effect_display_name(effect: dict[str, Any]) -> str:
    eid = int(effect.get("Id") or 0)
    fb = f"Status effect {eid}"
    return _clean_title(effect.get("Name"), fb)


def _section_headings_in_order(
    effects: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], str]]:
    """Stable == heading == per row; duplicate display names get ``Name (id)``."""
    used: dict[str, int] = {}
    out: list[tuple[dict[str, Any], str]] = []
    for effect in sorted(effects, key=lambda x: int(x.get("Id") or 0)):
        base = _effect_display_name(effect)
        n = used.get(base, 0)
        used[base] = n + 1
        heading = base if n == 0 else f"{base} ({int(effect.get('Id') or 0)})"
        out.append((effect, heading))
    return out


def _section_inner_wikitext(
    site: pywikibot.Site,
    effect: dict[str, Any],
    datadump: dict[str, Any],
    version: str,
) -> str:
    eid = int(effect.get("Id") or 0)
    name = _effect_display_name(effect)
    positive = bool(effect.get("IsPositiveEffect"))
    effect_type = "Positive" if positive else "Negative"

    icon_w = ""
    loaded = load_status_effect_atlas(datadump)
    sheet, sheet_tex = loaded if loaded else (None, "")
    png16 = effect_entry_to_png_bytes(effect, sheet, sheet_tex)
    if png16:
        icon_w = upload_raw_bytes_named(
            site,
            png16,
            "png",
            status_effect_sprite_base(eid, str(effect.get("Name") or name)),
            version,
            thumb_size=_PAGE_ICON_DISPLAY_PX,
        )
    if not icon_w:
        icon_w = (
            "''(Could not render status effect icon — add Sprite to datadump or configure "
            "Textures.STATUS_EFFECTS_16X16.)''"
        )

    stat_raw = str(effect.get("StatDescription") or "").strip()
    desc_line = ""
    if stat_raw:
        desc_plain = html_to_wikitext(stat_raw).strip()
        if desc_plain:
            desc_line = f"<br>''{desc_plain}''"

    icon_block = f"{icon_w}{desc_line}"
    details = wikitable([("Type", effect_type)])
    return f"{icon_block}\n\n{details}"


def build_status_effects_index_wikitext(
    site: pywikibot.Site,
    effects: list[dict[str, Any]],
    datadump: dict[str, Any],
    version: str,
) -> str:
    """
    Single article: one == section per effect. Cross-wiki links use
    ``[[Status effects#Fragment|Name]]`` (see ``status_effect_wikilink_path``).
    """
    parts: list[str] = [
        "__NOTOC__",
        "",
    ]
    first_icon_fname: str | None = None

    for effect, heading in _section_headings_in_order(effects):
        inner = _section_inner_wikitext(site, effect, datadump, version)
        if first_icon_fname is None:
            first_icon_fname = first_wiki_filename_from_file_wikitext(inner)
        parts.append(f"== {heading} ==")
        parts.append(inner)
        parts.append("")

    body = "\n".join(parts).rstrip() + "\n"
    categories_block = "[[Category:Status Effects]]"
    n = len(effects)
    seo = wiki_seo_block(
        site,
        page_title=STATUS_EFFECTS_INDEX_TITLE,
        description=f"In-game status effects in Pixel Quest ({n} entries).",
        wiki_image_filename=first_icon_fname,
        image_alt="Status effects",
    )
    return f"{body}\n{categories_block}\n\n{seo}"


def build_status_effect_name_to_path_map(effects: list[dict[str, Any]]) -> dict[str, str]:
    """Lowercase game name → ``Status effects#Anchor`` for wikilinks from items/entities."""
    out: dict[str, str] = {}
    for effect, heading in _section_headings_in_order(effects):
        raw_name = str(effect.get("Name") or "").strip()
        if raw_name:
            out[raw_name.lower()] = status_effect_wikilink_path(heading)
    return out
