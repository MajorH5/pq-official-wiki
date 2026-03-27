"""
Semantic wiki upload filenames (searchable, no content-hash filenames).

Convention: lowercase, a-z 0-9 underscore hyphen; single extension.
See repo docs/TEXTURE_NAMING.md.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

# First animation-frame row in TierIcon strip → stable theme name (matches game art rows).
TIER_ROW_TO_THEME: dict[int, str] = {
    0: "tier_star",
    2: "tier_pixelween",
    8: "tier_pixelmas",
    9: "tier_gamemode",
}


def slug(text: str, default: str = "x") -> str:
    t = re.sub(r"[^a-z0-9]+", "-", (text or "").lower().strip())
    t = re.sub(r"-+", "-", t).strip("-")
    return t or default


def sanitize_base(name: str) -> str:
    """Safe single path segment for MediaWiki File: titles."""
    s = re.sub(r"[^a-z0-9_.-]", "_", (name or "").lower().strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "asset"


def item_sprite_base(item_id: int, name: str) -> str:
    return sanitize_base(f"item_{slug(name)}_{item_id}")


def tier_icon_theme_from_sprite(tier_icon: dict[str, Any]) -> str:
    frames = tier_icon.get("Frames") or []
    row = 0
    if isinstance(frames, list) and frames:
        cell = frames[0]
        if isinstance(cell, (list, tuple)) and len(cell) >= 2:
            row = int(cell[1])
    return TIER_ROW_TO_THEME.get(row, f"tier_row_{row}")


def tier_icon_filename_base(tier_icon: dict[str, Any]) -> str:
    return sanitize_base(tier_icon_theme_from_sprite(tier_icon))


def entity_sprite_base(entity_id: int, name: str) -> str:
    return sanitize_base(f"entity_{slug(name)}_{entity_id}")


def projectile_sprite_base(proj_sprite: dict[str, Any]) -> str:
    """
    One wiki file per unique rendered projectile (Roblox sheet + animation or static rect).

    Different ProjectileDescriptor.Id values that share the same texture and crop/animation
    get the same basename (deduplicates uploads). Matches sprites.projectile_visual_signature_payload.
    """
    from pq_wiki.sprites import projectile_visual_signature_payload

    payload = projectile_visual_signature_payload(proj_sprite)
    sig = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    short = hashlib.sha256(sig.encode("utf-8")).hexdigest()[:12]
    aid = payload.get("asset_id")
    if isinstance(aid, str) and aid:
        return sanitize_base(f"projectile_tex_{aid}_{short}")
    return sanitize_base(f"projectile_{short}")


def skin_name_base(skin_id: int, name: str) -> str:
    return sanitize_base(f"skin_{slug(name)}_{skin_id}")


def skin_animation_base(skin_id: int, name: str, anim_key: str) -> str:
    return sanitize_base(f"{skin_name_base(skin_id, name)}_{anim_key}")


def skin_sprite_preview_base(skin_id: int, name: str) -> str:
    return sanitize_base(f"{skin_name_base(skin_id, name)}_sprite")


def skin_drop_idle_preview_base(skin_id: int, name: str) -> str:
    return sanitize_base(f"{skin_name_base(skin_id, name)}_idle_preview")


def loot_drop_base(kind: str, tier: int) -> str:
    k = "chest" if kind == "chest" else "bag"
    return sanitize_base(f"drop_{k}_{tier}")


def skin_rarity_base(rarity: int) -> str:
    return sanitize_base(f"skin_rarity_{rarity}")


def stat_icon_base(stat_lower: str) -> str:
    return sanitize_base(f"stat_{stat_lower}")


def valor_icon_base() -> str:
    return "valor_icon"


def difficulty_skull_base() -> str:
    return "skull_difficulty"


def status_effect_base(effect_name: str) -> str:
    return sanitize_base(f"status_effect_{slug(effect_name)}")


def portal_preview_base(location_slug: str) -> str:
    return sanitize_base(f"portal_{location_slug}")


def location_minimap_base(location_slug: str) -> str:
    return sanitize_base(f"location_{location_slug}_minimap")


def location_screenshot_base(location_slug: str, index: int) -> str:
    return sanitize_base(f"location_{location_slug}_screenshot_{index}")


def game_object_sprite_base(go_id: int, name: str) -> str:
    return sanitize_base(f"go_{slug(name)}_{go_id}")


def badge_sprite_base(badge_id: int, name: str) -> str:
    return sanitize_base(f"badge_{slug(name)}_{badge_id}")


def honor_icon_base(display_name: str) -> str:
    """Uploaded crown file: honor_<slug(display_name)>.png — matches wiki convention."""
    return sanitize_base(f"honor_{slug(display_name)}")


def achievement_icon_base(category_label: str, sequence_number: int) -> str:
    """One sheet cell per category + sequence (see achievement_icons.py)."""
    return sanitize_base(f"achievement_{slug(category_label)}_{sequence_number}")
