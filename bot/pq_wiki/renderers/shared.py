from __future__ import annotations

from typing import Any, Optional

from pq_wiki.wikitext_util import fmt_num


def green(s: str) -> str:
    return f'<span style="color:green">{s}</span>'


def red(s: str) -> str:
    return f'<span style="color:red">{s}</span>'


def signed_delta(v: Any, *, bold: bool = False) -> str:
    """
    Format a numeric delta with correct sign + color.
    Positive: +N (green)
    Negative: -N (red)
    Zero/unknown: N (no forced plus; green for 0)
    """
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        try:
            v = float(v)
        except Exception:
            return str(v)
    num = float(v)
    inner = fmt_num(int(num) if num.is_integer() else num)
    if num > 0:
        inner = f"+{inner}"
        inner = f"'''{inner}'''" if bold else inner
        return green(inner)
    if num < 0:
        # fmt_num already contains the '-' sign
        inner = f"'''{inner}'''" if bold else inner
        return red(inner)
    inner = f"'''{inner}'''" if bold else inner
    return green(inner)

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
    *,
    skin_id_to_skin: dict[int, dict] | None = None,
    skin_id_to_path: dict[int, str] | None = None,
    skin_rarity_icon_wikitext: dict[int, str] | None = None,
    site: Any = None,
    version: str | None = None,
) -> str:
    dt = drop.get("DropType")
    val = drop.get("Value")
    if dt == "Item" and isinstance(val, str):
        if (
            val == "Skin"
            and skin_id_to_skin
            and skin_id_to_path
            and site
            and version
            and isinstance(drop.get("Metadata"), dict)
        ):
            from pq_wiki.skin_drops import format_skin_drop_cell

            try:
                sid = int((drop.get("Metadata") or {}).get("rid"))
            except (TypeError, ValueError):
                sid = None
            if sid is not None and sid in skin_id_to_skin and sid in skin_id_to_path:
                cell = format_skin_drop_cell(
                    site,
                    version,
                    sid,
                    skin_id_to_skin,
                    skin_id_to_path,
                    skin_rarity_icon_wikitext or {},
                )
                if cell:
                    return cell
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
