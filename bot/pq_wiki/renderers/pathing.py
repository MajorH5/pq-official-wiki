from __future__ import annotations

import re


def _clean_title(name: str | None, fallback: str) -> str:
    """MediaWiki-friendly human title (spaces, not slug hyphens)."""
    raw = (name or "").strip()
    if not raw:
        return fallback
    # Remove title-illegal characters in MediaWiki and normalize whitespace.
    t = re.sub(r"[#<>\[\]\|{}]", "", raw)
    t = re.sub(r"\s+", " ", t).strip()
    if not t or re.match(r"^[\?\s\-_\.]+$", t):
        return fallback
    return t


def _claim_unique_title(
    name: str | None,
    fallback_title: str,
    pk: int,
    used: set[str],
) -> str:
    """
    Page title is human-readable (e.g. Red Party Hat, Swamp).
    First claimant wins the bare title; duplicates get " (id)", then " (id-2)", …
    pk is the row id (item / location / game object) so ties are stable.
    """
    base = _clean_title(name, fallback_title)
    if base not in used:
        used.add(base)
        return base
    candidate = f"{base} ({pk})"
    if candidate not in used:
        used.add(candidate)
        return candidate
    n = 2
    while True:
        c = f"{base} ({pk}-{n})"
        if c not in used:
            used.add(c)
            return c
        n += 1


def item_page_path(item: dict, used_paths: set[str] | None = None) -> str:
    """Flat human title: Red Party Hat (shared namespace with locations/entities)."""
    iid = item["Id"]
    fb = f"Item {iid}"
    if used_paths is None:
        return _clean_title(item.get("Name"), fb)
    return _claim_unique_title(item.get("Name"), fb, iid, used_paths)


def location_page_path(loc: dict, used_paths: set[str] | None = None) -> str:
    """Flat title: Swamp."""
    lid = loc["Id"]
    fb = f"Location {lid}"
    if used_paths is None:
        return _clean_title(loc.get("Name"), fb)
    return _claim_unique_title(loc.get("Name"), fb, lid, used_paths)


def entity_page_path(go: dict, used_paths: set[str] | None = None) -> str:
    """Flat human title: Boss Name (no Enemies/ prefix; category still marks type)."""
    gid = go["Id"]
    fb = f"Entity {gid}"
    if used_paths is None:
        return _clean_title(go.get("Name"), fb)
    return _claim_unique_title(go.get("Name"), fb, gid, used_paths)


def skin_page_path(skin: dict, used_paths: set[str] | None = None) -> str:
    """Flat title for CharacterSkins (shared namespace)."""
    sid = int(skin["Id"])
    fb = f"Skin {sid}"
    if used_paths is None:
        return _clean_title(skin.get("Name"), fb)
    return _claim_unique_title(skin.get("Name"), fb, sid, used_paths)


def account_stat_page_path(stat: dict, used_paths: set[str] | None = None) -> str:
    """Flat title for AccountStats rows (shared namespace)."""
    sid = int(stat["Id"])
    fb = f"Account Stat {sid}"
    if used_paths is None:
        return _clean_title(stat.get("Name"), fb)
    return _claim_unique_title(stat.get("Name"), fb, sid, used_paths)


def badge_page_path(badge: dict, used_paths: set[str] | None = None) -> str:
    bid = int(badge["Id"])
    fb = f"Badge {bid}"
    if used_paths is None:
        return _clean_title(badge.get("Name"), fb)
    return _claim_unique_title(badge.get("Name"), fb, bid, used_paths)


def achievement_page_path(ach: dict, used_paths: set[str] | None = None) -> str:
    aid = int(ach["Id"])
    fb = f"Achievement {aid}"
    if used_paths is None:
        return _clean_title(ach.get("Name"), fb)
    return _claim_unique_title(ach.get("Name"), fb, aid, used_paths)


# Bot emits one article; sections use == headings ==. Links: [[Status effects#Fragment|Name]].
STATUS_EFFECTS_INDEX_TITLE = "Status effects"


def status_effect_wikilink_path(heading_text: str) -> str:
    """Wikilink target for a section heading (spaces → underscores in the fragment)."""
    frag = str(heading_text).strip().replace(" ", "_")
    return f"{STATUS_EFFECTS_INDEX_TITLE}#{frag}"
