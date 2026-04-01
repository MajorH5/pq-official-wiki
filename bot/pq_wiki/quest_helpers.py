"""Quest datadump helpers: categories, event types, display names."""
from __future__ import annotations

import re
from typing import Any

# Align with game QuestEventType enum (numbers in dump).
EVENT_EXP_EARNED = 0
EVENT_DAMAGE_DEALT = 1
EVENT_TILES_TRAVELLED = 2
EVENT_RIFT_COMPLETED = 3
EVENT_ENEMY_KILLED = 4
EVENT_PROJECTILES_FIRED = 5
EVENT_DUNGEON_RUSH_COMPLETE = 6
EVENT_DUNGEON_RUSH_CHECKPOINT = 7
EVENT_BIOME_ENEMY_KILLED = 8
EVENT_GAUNTLET_COMPLETED = 9


def enum_key_to_display(key: str) -> str:
    """FLOWER_WOODLAND -> Flower Woodland"""
    return key.replace("_", " ").strip().title()


def sanitize_quest_name(name: str, q: dict[str, Any]) -> str:
    """
    Replace ``{dispatchKey}`` and apply the same random-dungeon title rules as the wiki body.

    Must run before ``_clean_title`` / page paths: MediaWiki titles strip ``{}``, which would
    turn ``{dispatchKey}`` into the bogus word ``dispatchKey``.
    """
    rk = int(q.get("RandomKeyAmount") or 1)
    name = re.sub(r"\{dispatchKey\}", "X", name, flags=re.IGNORECASE)
    # If braces were stripped upstream or data used a bare token.
    name = re.sub(r"\bdispatchKey\b", "X", name, flags=re.IGNORECASE)
    if q.get("RandomizesDispatchKeys"):
        m = re.search(r"\b(\d+)\b", name)
        n = m.group(1) if m else str(rk)
        if re.search(r"clear.*dungeon", name, re.I) or "dungeon" in name.lower():
            name = f"Clear {n} random dungeons (rotating pool)"
    return name


def sanitize_quest_description(desc: str) -> str:
    """Replace ``{dispatchKey}`` in descriptions (same token as names)."""
    desc = re.sub(r"\{dispatchKey\}", "a random target", desc, flags=re.IGNORECASE)
    desc = re.sub(r"\bdispatchKey\b", "a random target", desc, flags=re.IGNORECASE)
    return desc


def quest_category_display(
    category_raw: Any,
    quest_categories: dict[str, Any] | None,
) -> str:
    """
    Resolve Category field to a human display string.
    Dump may store string ("Beach", "Hourly Quests") or int (index into QuestCategories).
    """
    if category_raw is None:
        return "Quest"
    if isinstance(category_raw, str) and category_raw.strip():
        return category_raw.strip()
    if isinstance(category_raw, (int, float)) and quest_categories:
        try:
            idx = int(category_raw)
        except (TypeError, ValueError):
            return "Quest"
        rev: dict[int, str] = {}
        for k, v in quest_categories.items():
            try:
                rev[int(v)] = str(k)
            except (TypeError, ValueError):
                continue
        key = rev.get(idx)
        if key:
            return enum_key_to_display(key)
    return str(category_raw)


def category_wikilink(display: str) -> str:
    """Category line for wiki — avoid 'Hourly Quests Quests'."""
    d = (display or "").strip()
    if not d:
        return ""
    dl = d.lower()
    if dl.endswith(" quests"):
        return f"[[Category:{d}]]"
    return f"[[Category:{d} Quests]]"


def reward_is_choice_stat_quest(rewards: list[dict[str, Any]]) -> bool:
    """Choice award whose options are StatBoost — tag as Stat Quest."""
    for rw in rewards:
        if not isinstance(rw, dict):
            continue
        if str(rw.get("Type") or "") != "Choice":
            continue
        val = rw.get("Value")
        if not isinstance(val, list) or len(val) < 2:
            continue
        if all(
            isinstance(ch, dict) and str(ch.get("Type") or "") == "StatBoost" for ch in val
        ):
            return True
    return False


def icon_dedupe_key(icon: dict[str, Any]) -> str:
    """Stable key for quest Icons[] to skip duplicate crops."""
    from pq_wiki.sprites import normalize_image_rect_offset_size

    img = str(icon.get("image") or icon.get("Texture") or "")
    ro = icon.get("imageRectOffset") or icon.get("ImageRectOffset") or {}
    rs = icon.get("imageRectSize") or icon.get("ImageRectSize") or {}
    try:
        (ox, oy), (sx, sy) = normalize_image_rect_offset_size(ro, rs)
    except (TypeError, ValueError):
        ox = oy = sx = sy = 0
    return f"{img}|{ox},{oy}|{sx},{sy}"


def normalize_icon_to_sprite(icon: dict[str, Any]) -> dict[str, Any]:
    """Map quest Icon dict (image, imageRect*) to sprite dict for upload_sprite_if_possible."""
    from pq_wiki.sprites import normalize_image_rect_offset_size

    out: dict[str, Any] = {}
    tex = icon.get("image") or icon.get("Texture")
    if tex:
        out["Texture"] = tex
    ro = icon.get("imageRectOffset") or icon.get("ImageRectOffset") or {}
    rs = icon.get("imageRectSize") or icon.get("ImageRectSize") or {}
    (ox, oy), (sx, sy) = normalize_image_rect_offset_size(ro, rs)
    out["ImageRectOffset"] = {"X": ox, "Y": oy}
    out["ImageRectSize"] = {"X": sx, "Y": sy}
    return out


def biome_sprite_dict(bio: dict[str, Any]) -> dict[str, Any] | None:
    """Prefer top-level Sprite on biome row."""
    sp = bio.get("Sprite")
    return sp if isinstance(sp, dict) and sp else None
