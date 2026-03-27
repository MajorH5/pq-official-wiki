"""Render achievement/badge reward rows as wikitext (icons + text)."""
from __future__ import annotations

from typing import Any

from pq_wiki.texture_names import item_sprite_base
from pq_wiki.wiki_assets import file_wikitext

# Reuse stat icon filenames from stat_icons pattern - bot uploads stat_{name}.png
def _stat_icon_wikitext(stat_icons: dict[str, str] | None, stat: str, label: str) -> str:
    if stat_icons:
        k = (stat or "").strip().lower()
        w = stat_icons.get(k, "")
        if w:
            return f"{w} {label}"
    return label


def _stat_boost_display(val: Any, stat: str) -> str:
    try:
        f = float(val)
    except (TypeError, ValueError):
        return str(stat)
    st = (stat or "").strip()
    if abs(f) > 1.0 or f == 0:
        sign = "+" if f > 0 else ("-" if f < 0 else "")
        return f"{sign}{abs(f):g} {st}".strip()
    sign = "+" if f >= 0 else ""
    return f"{sign}{f * 100:.0f}% {st}"


def _pct_from_fraction(v: float) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    sign = "+" if f >= 0 else ""
    return f"{sign}{f * 100:.0f}%"


def _format_duration_seconds(sec: float) -> str:
    try:
        s = int(float(sec))
    except (TypeError, ValueError):
        return str(sec)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s}s" if s else f"{m}m"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


def format_reward_cell_wikitext(
    reward: dict[str, Any],
    *,
    item_id_to_path: dict[int, str],
    item_id_to_item: dict[int, dict[str, Any]],
    item_name_to_id: dict[str, int],
    stat_icons: dict[str, str] | None,
    valor_icon_wikitext: str,
    honor_bronze_icon_wikitext: str,
    lucky_clover_item_id: int | None,
    mastery_weapon_item: dict[str, Any] | None,
    location_id_to_path: dict[int, str],
    location_name_to_path: dict[str, str],
    thumb_px: int = 24,
) -> str:
    """Single reward description with optional inline icon wikitext."""
    rtype = str(reward.get("Type") or "")
    parts: list[str] = []

    if rtype == "ItemReward":
        qty = reward.get("Value")
        iname = reward.get("ItemName") or reward.get("Item") or ""
        iid = item_name_to_id.get(str(iname).strip()) if iname else None
        if iid is None and iname:
            for it in item_id_to_item.values():
                if str(it.get("Name") or "").strip() == str(iname).strip():
                    iid = int(it["Id"])
                    break
        if iid and iid in item_id_to_item:
            it = item_id_to_item[iid]
            base = item_sprite_base(iid, str(it.get("Name") or f"Item {iid}"))
            parts.append(
                file_wikitext(f"{base}.png", thumb_px)
                + f" [[{item_id_to_path[iid]}|{it.get('Name', iname)}]] ×{qty}"
            )
        else:
            parts.append(f"'''{iname}''' ×{qty}" if iname else f"Item reward ×{qty}")

    elif rtype == "StatBoost":
        stat = str(reward.get("Stat") or "")
        val = reward.get("Value")
        label = _stat_boost_display(val, stat) if val is not None else stat
        parts.append(_stat_icon_wikitext(stat_icons, stat, label))

    elif rtype == "LuckBoost":
        dungeon = str(reward.get("Dungeon") or "")
        val = reward.get("Value")
        pct = _pct_from_fraction(float(val)) if val is not None else ""
        if lucky_clover_item_id and lucky_clover_item_id in item_id_to_item:
            it = item_id_to_item[lucky_clover_item_id]
            base = item_sprite_base(lucky_clover_item_id, str(it.get("Name") or "Lucky Clover"))
            parts.append(
                file_wikitext(f"{base}.png", thumb_px)
                + f" Luck in '''{dungeon}''': {pct}"
            )
        else:
            parts.append(f"Luck in '''{dungeon}''': {pct}")

    elif rtype == "MasteryBoost":
        wclass = str(reward.get("WeaponClass") or "").strip()
        val = reward.get("Value")
        pct = _pct_from_fraction(float(val)) if val is not None else ""
        label = f"Mastery {pct} {wclass} damage".strip() if wclass else f"Mastery {pct} damage"
        if mastery_weapon_item:
            mid = int(mastery_weapon_item["Id"])
            base = item_sprite_base(mid, str(mastery_weapon_item.get("Name") or f"Item {mid}"))
            parts.append(file_wikitext(f"{base}.png", thumb_px) + f" {label}")
        else:
            parts.append(label)

    elif rtype == "HonorBoost":
        val = reward.get("Value")
        hi = honor_bronze_icon_wikitext or ""
        if hi:
            parts.append(f"{hi} +{val} Honor")
        else:
            parts.append(f"+{val} Honor")

    elif rtype == "ValorBoost":
        val = reward.get("Value")
        vi = valor_icon_wikitext or ""
        if vi:
            parts.append(f"{vi} +{val} Valor")
        else:
            parts.append(f"+{val} Valor")

    elif rtype == "ExperienceBoost":
        val = reward.get("Value")
        if val is not None:
            try:
                f = float(val)
                pct = _pct_from_fraction(f)
                parts.append(_stat_icon_wikitext(stat_icons, "experience", f"{pct} experience"))
            except (TypeError, ValueError):
                parts.append(str(val))
        else:
            parts.append("Experience boost")

    else:
        parts.append(f"'''{rtype}''': {reward.get('Value', '')}")

    return " ".join(parts)


def render_rewards_wikitable(
    rewards: list[dict[str, Any]],
    *,
    item_id_to_path: dict[int, str],
    item_id_to_item: dict[int, dict[str, Any]],
    item_name_to_id: dict[str, int],
    stat_icons: dict[str, str] | None,
    valor_icon_wikitext: str,
    honor_bronze_icon_wikitext: str,
    lucky_clover_item_id: int | None,
    mastery_weapon_item_by_class: dict[str, dict[str, Any]],
    location_id_to_path: dict[int, str],
    location_name_to_path: dict[str, str],
) -> str:
    """Wikitable of rewards (one row per reward)."""
    if not rewards:
        return ""
    lines = ['{| class="wikitable"', "|- ! Reward"]
    for rw in rewards:
        wclass = str(rw.get("WeaponClass") or "")
        mw = mastery_weapon_item_by_class.get(wclass) if wclass else None
        cell = format_reward_cell_wikitext(
            rw,
            item_id_to_path=item_id_to_path,
            item_id_to_item=item_id_to_item,
            item_name_to_id=item_name_to_id,
            stat_icons=stat_icons,
            valor_icon_wikitext=valor_icon_wikitext,
            honor_bronze_icon_wikitext=honor_bronze_icon_wikitext,
            lucky_clover_item_id=lucky_clover_item_id,
            mastery_weapon_item=mw,
            location_id_to_path=location_id_to_path,
            location_name_to_path=location_name_to_path,
        )
        lines.append("|-")
        lines.append(f"| {cell}")
    lines.append("|}")
    return "\n".join(lines)


def render_metadata_section(
    metadata: dict[str, Any] | None,
    *,
    item_id_to_path: dict[int, str],
    item_id_to_item: dict[int, dict[str, Any]],
    location_id_to_path: dict[int, str],
) -> str:
    """Achievement Metadata dict (string keys) for wiki."""
    if not metadata or not isinstance(metadata, dict):
        return ""
    rows: list[tuple[str, str]] = []

    if "0" in metadata:
        raw = metadata["0"]
        ids: list[int] = []
        if isinstance(raw, list):
            for x in raw:
                try:
                    ids.append(int(x))
                except (TypeError, ValueError):
                    pass
        if ids:
            bits = []
            for iid in ids:
                it = item_id_to_item.get(iid)
                if it:
                    path = item_id_to_path.get(iid, f"Item {iid}")
                    bits.append(f"[[{path}|{it.get('Name', iid)}]]")
                else:
                    bits.append(str(iid))
            rows.append(("Qualified Legendaries", ", ".join(bits)))

    if "1" in metadata:
        try:
            lid = int(metadata["1"])
        except (TypeError, ValueError):
            lid = None
        if lid is not None and lid in location_id_to_path:
            rows.append(("Location", f"[[{location_id_to_path[lid]}]]"))
        elif lid is not None:
            rows.append(("Location", str(lid)))

    if "2" in metadata:
        try:
            sec = float(metadata["2"])
        except (TypeError, ValueError):
            sec = 0.0
        rows.append(("Cursed Luck Time", _format_duration_seconds(sec)))

    if "3" in metadata:
        try:
            v = float(metadata["3"])
        except (TypeError, ValueError):
            v = 0.0
        rows.append(("Damage Threshold", _pct_from_fraction(v) + " DMG"))

    if not rows:
        return ""

    from pq_wiki.wikitext_util import wikitable

    return wikitable(rows)
