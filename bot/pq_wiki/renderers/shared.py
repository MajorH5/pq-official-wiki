from __future__ import annotations

from typing import Any, Optional

from pq_wiki.wikitext_util import fmt_num


def green(s: str) -> str:
    return f'<span style="color:green">{s}</span>'


def link_entity(
    name: str,
    go_name_to_id: Optional[dict[str, int]],
    entity_id_to_path: dict[int, str],
) -> str:
    if go_name_to_id and name in go_name_to_id:
        path = entity_id_to_path.get(go_name_to_id[name])
        if path:
            return f"[[{path}|{name}]]"
    return name


def find_dungeon_key(dungeon_name: str, item_name_to_id: dict[str, int]) -> Optional[int]:
    key_name = f"{dungeon_name} Key"
    return item_name_to_id.get(key_name)


def fmt_group(val: Any) -> str:
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        parts = []
        for x in val:
            if isinstance(x, (list, tuple)):
                parts.append("/".join(str(y) for y in x))
            else:
                parts.append(str(x))
        return ", ".join(parts)
    return str(val)


def format_drop(
    drop: Any,
    item_name_to_id: dict[str, int],
    item_id_to_path: dict[int, str],
    go_name_to_id: dict[str, int],
) -> str:
    dt = drop.get("DropType")
    val = drop.get("Value")
    if dt == "Item" and isinstance(val, str):
        iid = item_name_to_id.get(val)
        if iid:
            path = item_id_to_path.get(iid)
            if path:
                return f"[[{path}|{val}]]"
        return val
    if dt == "ItemGroup":
        return f"Item group: {fmt_group(val)}"
    return f"{dt}: {val!s}"


def fmt_range(min_v: Any, max_v: Any, suffix: str = "") -> str:
    """
    Format min/max values; collapse equal values to one number.
    """
    a = fmt_num(min_v)
    b = fmt_num(max_v)
    if a and b:
        base = a if a == b else f"{a}–{b}"
    else:
        base = a or b
    if suffix and base:
        return f"{base} {suffix}".strip()
    return base
