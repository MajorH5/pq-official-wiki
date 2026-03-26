from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pywikibot

from pq_wiki.texture_names import entity_sprite_base
from pq_wiki.texture_service import upload_sprite_if_possible


@dataclass(frozen=True)
class ItemDropSource:
    entity_id: int
    entity_name: str
    entity_path: str | None
    via: str  # "direct" or "group"
    group_label: str | None


def _iter_item_ids_from_drop(
    drop: dict[str, Any],
    item_name_to_id: dict[str, int],
    item_id_to_item: dict[int, dict[str, Any]] | None,
) -> list[tuple[int, str, str | None]]:
    """
    From one loot drop entry, yield (item_id, via, group_label).
    via is 'direct' or 'group'; group_label is set when via=='group'.
    """
    from pq_wiki.renderers.entity_renderer import (
        _item_group_label,
        _normalize_enemy_drop_entries,
        _resolve_item_group_item_ids,
    )

    if not item_id_to_item:
        return []
    entries = _normalize_enemy_drop_entries(drop, item_name_to_id, item_id_to_item)
    out: list[tuple[int, str, str | None]] = []
    for nd in entries:
        kind = nd.get("kind")
        if kind == "item":
            iid = nd.get("item_id")
            if iid is not None and int(iid) in item_id_to_item:
                out.append((int(iid), "direct", None))
        elif kind == "itemgroup":
            gk = nd.get("group_kind")
            gt = nd.get("group_tier")
            label = str(nd.get("name") or "").strip() or None
            if gk and gt:
                for iid in _resolve_item_group_item_ids([gk, gt], item_name_to_id, item_id_to_item):
                    out.append((iid, "group", label))
    if out:
        return out
    dt = drop.get("DropType")
    val = drop.get("Value")
    if dt == "Item" and isinstance(val, str):
        iid = item_name_to_id.get(val)
        if iid is not None and iid in item_id_to_item:
            out.append((int(iid), "direct", None))
    elif dt == "ItemGroup" and val is not None:
        lbl = _item_group_label(val)
        lbl = str(lbl).strip() or None
        for iid in _resolve_item_group_item_ids(val, item_name_to_id, item_id_to_item):
            out.append((iid, "group", lbl))
    return out


def build_item_id_to_drop_sources(
    game_objects: list[dict[str, Any]],
    item_name_to_id: dict[str, int],
    item_id_to_item: dict[int, dict[str, Any]] | None,
    entity_id_to_path: dict[int, str],
) -> dict[int, list[ItemDropSource]]:
    """
    Reverse lookup: which entities drop this item (direct item line or item group pool).
    Uses the same rules as entity loot rendering.
    """
    bucket: dict[int, dict[tuple[int, str, str], ItemDropSource]] = {}

    for go in game_objects:
        if not go.get("IsEntity", True):
            continue
        gid = int(go["Id"])
        name = str(go.get("Name") or f"Entity {gid}")
        path = entity_id_to_path.get(gid)
        drops = [*(go.get("PrivateDrops") or []), *(go.get("PublicDrops") or [])]
        for d in drops:
            if not isinstance(d, dict):
                continue
            for iid, via, glabel in _iter_item_ids_from_drop(d, item_name_to_id, item_id_to_item):
                key = (gid, via, glabel or "")
                rec = ItemDropSource(
                    entity_id=gid,
                    entity_name=name,
                    entity_path=path,
                    via=via,
                    group_label=glabel,
                )
                inner = bucket.setdefault(iid, {})
                inner[key] = rec

    out: dict[int, list[ItemDropSource]] = {}
    for iid, inner in bucket.items():
        rows = sorted(
            inner.values(),
            key=lambda r: (r.entity_name.lower(), r.via, r.group_label or ""),
        )
        out[iid] = rows
    return out


def format_item_drop_sources_wikitext(
    sources: list[ItemDropSource],
    site: pywikibot.Site,
    version: str,
    entity_id_to_go: dict[int, dict[str, Any]],
) -> str:
    """Wikitext for == Dropped by == (multicolumn: max 5 enemies per column, like enemy loot)."""
    from pq_wiki.renderers.entity_renderer import _layout_drops_multicolumn, _link_image_wikitext

    if not sources:
        return ""
    seen_entity: set[int] = set()
    rows: list[str] = []
    for s in sources:
        if s.entity_id in seen_entity:
            continue
        seen_entity.add(s.entity_id)
        go = entity_id_to_go.get(s.entity_id)
        icon = ""
        if go:
            nm = str(go.get("Name") or f"Entity {s.entity_id}")
            icon = upload_sprite_if_possible(
                site,
                go.get("Sprite"),
                version,
                thumb_size=40,
                logical_name=entity_sprite_base(s.entity_id, nm),
            )
        if icon and s.entity_path:
            icon = _link_image_wikitext(icon, s.entity_path)
        enemy = f"[[{s.entity_path}|{s.entity_name}]]" if s.entity_path else s.entity_name
        if icon:
            cell = (
                '<span style="display:inline-flex; align-items:center; gap:8px;">'
                f"{icon} {enemy}"
                "</span>"
            )
        else:
            cell = enemy
        rows.append(cell)

    inner = _layout_drops_multicolumn(rows, max_per_col=5, inner_table_width="auto")
    return "\n".join([
        "== Dropped by ==",
        '<div style="display:inline-block; max-width:100%; overflow-x:auto; vertical-align:top;">',
        '{| class="wikitable sortable" style="width:auto;"',
        "! Enemy",
        "|-",
        f"| {inner}",
        "|}",
        "</div>",
    ])
