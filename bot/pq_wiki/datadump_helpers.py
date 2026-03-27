"""Lookups against pq-datadump Items / Textures for reward rendering and icons."""
from __future__ import annotations

from typing import Any, Optional


def texture_url_from_root(data: dict[str, Any], key: str) -> Optional[str]:
    """Textures[key] may be a rbxassetid string or a sprite dict with Texture."""
    tex = (data.get("Textures") or {}).get(key)
    if isinstance(tex, str) and tex.startswith("rbxassetid://"):
        return tex
    if isinstance(tex, dict):
        t = tex.get("Texture") or tex.get("texture")
        if isinstance(t, str) and t.startswith("rbxassetid://"):
            return t
    return None


def find_item_id_by_name(items: list[dict[str, Any]], name: str) -> Optional[int]:
    n = (name or "").strip()
    if not n:
        return None
    for it in items:
        if str(it.get("Name") or "").strip() == n:
            try:
                return int(it["Id"])
            except (TypeError, ValueError, KeyError):
                continue
    return None


def find_t0_weapon_item_for_class(items: list[dict[str, Any]], weapon_class: str) -> Optional[dict[str, Any]]:
    """First item with TypeHierarchy containing weapon_class and Tier T0 (or numeric 0)."""
    wc = (weapon_class or "").strip()
    if not wc:
        return None
    candidates: list[dict[str, Any]] = []
    for it in items:
        hier = it.get("TypeHierarchy") or []
        if not isinstance(hier, list) or wc not in [str(x) for x in hier]:
            continue
        tier = it.get("Tier")
        t_ok = False
        if isinstance(tier, str) and tier.upper() == "T0":
            t_ok = True
        elif tier in (0, "0"):
            t_ok = True
        if t_ok:
            candidates.append(it)
    if not candidates:
        return None
    candidates.sort(key=lambda x: int(x.get("Id") or 0))
    return candidates[0]


def achievement_category_id(raw: Any, achievement_categories: dict[str, Any] | None) -> int:
    """Resolve Achievement.Category: int id or enum string (e.g. COMBAT -> 0 via AchievementCategories)."""
    if raw is None or raw == "":
        return 0
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, (int, float)):
        return int(raw)
    s = str(raw).strip()
    if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
        return int(s)
    if achievement_categories and isinstance(achievement_categories, dict):
        if s in achievement_categories:
            v = achievement_categories[s]
            try:
                return int(v)
            except (TypeError, ValueError):
                return 0
        sup = s.upper()
        for k, v in achievement_categories.items():
            if str(k).upper() == sup:
                try:
                    return int(v)
                except (TypeError, ValueError):
                    return 0
    return 0


def achievement_category_label(cat_num: int, achievement_categories: dict[str, Any] | None) -> str:
    """Normalize enum name to display (e.g. COMBAT -> Combat)."""
    if achievement_categories and isinstance(achievement_categories, dict):
        for k, v in achievement_categories.items():
            try:
                if int(v) == int(cat_num):
                    return _normalize_enum_display(str(k))
            except (TypeError, ValueError):
                continue
    return f"Category {cat_num}"


def achievement_series_label(series_num: int, achievement_series: dict[str, Any] | None) -> str:
    if achievement_series and isinstance(achievement_series, dict):
        for k, v in achievement_series.items():
            if int(v) == int(series_num):
                return _normalize_enum_display(str(k))
    return f"Series {series_num}"


def _normalize_enum_display(name: str) -> str:
    """ACHIEVEMENT_CATEGORY -> Achievement Category"""
    t = name.strip().replace("_", " ").lower()
    return " ".join(w.capitalize() for w in t.split()) if t else name
