from __future__ import annotations

import pywikibot

from pq_wiki.renderers.location_renderer import (
    _difficulty_display,
    _entity_multicolumn_wikitable,
    _entity_resolves_to_page,
    _render_entity_preview_cell,
    _sort_entity_names_by_tag,
)
from pq_wiki.seo import first_wiki_filename_from_file_wikitext, wiki_seo_block
from pq_wiki.texture_names import biome_sprite_base
from pq_wiki.texture_service import upload_sprite_if_possible
from pq_wiki.wikitext_util import template_invocation

_COMMONS_PLACEHOLDER_FILE = "No image available-4x.png"

# Main overworld hub location title in datadump (links from every biome page).
OVERWORLD_LOCATION_NAME = "Overworld"


def _commons_placeholder_thumb(caption: str, width: int = 250) -> str:
    safe = caption.replace("|", " ")
    return f"[[File:{_COMMONS_PLACEHOLDER_FILE}|thumb|upright=1|{width}px|{safe}]]"


def _overworld_line(overworld_path: str | None) -> str:
    if overworld_path:
        return (
            f"''This biome is part of the '''[[{overworld_path}|{OVERWORLD_LOCATION_NAME}]]'''.''"
        )
    return f"''This biome is part of the '''{OVERWORLD_LOCATION_NAME}'''.''"


def _build_biome_map_section(biome_name: str) -> str:
    cap_placeholder = (
        f"Overworld minimap placeholder — replace with in-game minimap showing {biome_name}. "
        "Wikimedia Commons: No image available-4x.png."
    )
    return f"== Map ==\n{_commons_placeholder_thumb(cap_placeholder)}"


def _build_biome_screenshots_section(biome_name: str) -> str:
    g1 = (
        f"Gameplay screenshot placeholder — replace with in-game capture ({biome_name}). "
        "Wikimedia Commons placeholder image."
    )
    g2 = (
        f"Area view placeholder — replace when available ({biome_name}). "
        "Wikimedia Commons placeholder image."
    )
    return "\n".join(
        [
            "== Screenshots ==",
            '<gallery mode="packed" heights="220px">',
            f"{_COMMONS_PLACEHOLDER_FILE}|{g1}",
            f"{_COMMONS_PLACEHOLDER_FILE}|{g2}",
            "</gallery>",
        ]
    )


def build_biome_wikitext(
    site: pywikibot.Site,
    biome: dict,
    version: str,
    go_name_to_id: dict[str, int],
    entity_id_to_path: dict[int, str],
    entity_name_to_go: dict[str, dict] | None,
    location_name_to_path: dict[str, str] | None,
    difficulty_skull_icon: str = "",
    extra_found_entity_names: list[str] | None = None,
) -> str:
    bid = int(biome["Id"])
    name = str(biome.get("Name") or f"Biome {bid}")

    overworld_path = (location_name_to_path or {}).get(OVERWORLD_LOCATION_NAME)
    overworld_line = _overworld_line(overworld_path)

    # Native pixel size + pq-pixel-sprite wrapper — same idea as location portal_image (no thumb/caption).
    biome_lead_img = upload_sprite_if_possible(
        site,
        biome.get("Sprite"),
        version,
        thumb_size=None,
        logical_name=biome_sprite_base(bid, name),
    )
    biome_image_block = biome_lead_img

    difficulty = _difficulty_display(biome.get("Difficulty"), difficulty_skull_icon)

    map_section = _build_biome_map_section(name)
    screenshots_section = _build_biome_screenshots_section(name)

    found_entities_block = ""
    raw_found = [str(n) for n in (biome.get("FoundGameObjects") or []) if n]
    extras = [str(n) for n in (extra_found_entity_names or []) if str(n).strip()]
    seen_names: set[str] = set()
    merged_found: list[str] = []
    for n in raw_found:
        if n not in seen_names:
            seen_names.add(n)
            merged_found.append(n)
    for n in extras:
        if n not in seen_names:
            seen_names.add(n)
            merged_found.append(n)
    found = merged_found
    if found:
        found_names = _sort_entity_names_by_tag(found, entity_name_to_go)
        found_names = [n for n in found_names if _entity_resolves_to_page(n, go_name_to_id, entity_id_to_path)]
        if found_names:
            fe_cells = [
                _render_entity_preview_cell(
                    site, n, version, go_name_to_id, entity_id_to_path, entity_name_to_go
                )
                for n in found_names
            ]
            found_entities_block = _entity_multicolumn_wikitable("== Found entities ==", "Entity", fe_cells)

    cat_lines = ["[[Category:Biomes]]"]
    categories_block = "\n".join(cat_lines)

    seo_image_fname = first_wiki_filename_from_file_wikitext(biome_lead_img) or first_wiki_filename_from_file_wikitext(
        map_section
    )

    body = template_invocation(
        "PQ Biome",
        [
            ("biome_image", biome_image_block),
            ("overworld_line", overworld_line),
            ("difficulty", difficulty),
            ("map_section", map_section),
            ("screenshots_section", screenshots_section),
            ("found_entities", found_entities_block),
            ("categories", categories_block),
        ],
    )
    seo = wiki_seo_block(
        site,
        page_title=name,
        description=f"{name} — Pixel Quest Wiki overworld biome.",
        wiki_image_filename=seo_image_fname,
        image_alt=f"{name} biome",
    )
    return f"{body}\n\n{seo}"
