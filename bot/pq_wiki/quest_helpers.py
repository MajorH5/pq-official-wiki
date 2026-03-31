"""Quest datadump helpers: categories, event types, display names."""
from __future__ import annotations

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
    img = str(icon.get("image") or icon.get("Texture") or "")
    ro = icon.get("imageRectOffset") or icon.get("ImageRectOffset") or {}
    rs = icon.get("imageRectSize") or icon.get("ImageRectSize") or {}
    try:
        ox = int(ro.get("X", ro.get("x", 0)))
        oy = int(ro.get("Y", ro.get("y", 0)))
        sx = int(rs.get("X", rs.get("x", 0)))
        sy = int(rs.get("Y", rs.get("y", 0)))
    except (TypeError, ValueError):
        ox = oy = sx = sy = 0
    return f"{img}|{ox},{oy}|{sx},{sy}"


def normalize_icon_to_sprite(icon: dict[str, Any]) -> dict[str, Any]:
    """Map quest Icon dict (image, imageRect*) to sprite dict for upload_sprite_if_possible."""
    out: dict[str, Any] = {}
    tex = icon.get("image") or icon.get("Texture")
    if tex:
        out["Texture"] = tex
    ro = icon.get("imageRectOffset") or icon.get("ImageRectOffset")
    rs = icon.get("imageRectSize") or icon.get("ImageRectSize")
    if isinstance(ro, dict):
        out["ImageRectOffset"] = {"X": ro.get("X", ro.get("x", 0)), "Y": ro.get("Y", ro.get("y", 0))}
    if isinstance(rs, dict):
        out["ImageRectSize"] = {"X": rs.get("X", rs.get("x", 0)), "Y": rs.get("Y", rs.get("y", 0))}
    return out


def biome_sprite_dict(bio: dict[str, Any]) -> dict[str, Any] | None:
    """Prefer top-level Sprite on biome row."""
    sp = bio.get("Sprite")
    return sp if isinstance(sp, dict) and sp else None
