from __future__ import annotations

import pywikibot

from pq_wiki.renderers.shared import fmt_range, green
from pq_wiki.texture_service import upload_projectile_sprite, upload_sprite_if_possible
from pq_wiki.wikitext_util import fmt_num, html_to_wikitext, stat_boosts_as_dict, type_hierarchy_links, wikitable


def _categories_from_hierarchy(hier: list) -> list[str]:
    out = []
    for h in hier:
        if h and h != "Item":
            out.append(h)
    return out


def _normalized_tier_label(raw_tier: object) -> str:
    t = str(raw_tier or "").strip()
    if not t:
        return ""
    return t.upper() if t.lower().startswith("t") else t


def build_item_wikitext(
    site: pywikibot.Site,
    item: dict,
    version: str,
    stat_icons: dict[str, str] | None = None,
    drop_tier_icons: dict[int, str] | None = None,
    unreleased: bool = False,
) -> str:
    iid = item["Id"]
    tier = item.get("Tier", "")
    hier = item.get("TypeHierarchy") or []
    desc = html_to_wikitext(item.get("Description", ""))
    hier_l = [str(h).lower() for h in hier]
    show_tier = ("equipment" in hier_l) or ("skin" in hier_l)

    icon = upload_sprite_if_possible(site, item.get("Sprite"), version)
    tier_icon = ""
    if show_tier and item.get("TierIcon"):
        tier_icon = upload_sprite_if_possible(site, item["TierIcon"], version, thumb_size=16)

    lines = [f"<!-- PQ bot generated {version} — do not remove -->", ""]
    if show_tier:
        head = f"'''Tier {tier}'''"
        if tier_icon:
            head = (
                '<span style="display:inline-flex; align-items:center; gap:4px">'
                f"{tier_icon}<span>'''Tier {tier}'''</span>"
                "</span>"
            )
        if hier:
            head += f" · {hier[0]}"
        lines.append(head)
        lines.append("")
    if icon:
        lines.append(icon)
    lines.append("")
    if desc:
        lines.append(f"''{desc}''")
        lines.append("")

    lines.append("== Notes ==")
    lines.append("<!-- Add editor notes/history here. -->")
    lines.append("")

    drop_tier = int(item.get("DropTierType") or 0)
    drop_tier_wikitext = ""
    if drop_tier_icons:
        drop_tier_wikitext = drop_tier_icons.get(drop_tier, "")

    info_rows = [
        ("Type", type_hierarchy_links(hier)),
        ("Tradable", "Yes" if item.get("IsTradable") else "No"),
        ("Drop Type", drop_tier_wikitext or fmt_num(item.get("DropTierType"))),
    ]
    if item.get("ValorBonusPercentage") is not None:
        try:
            if float(item.get("ValorBonusPercentage")) > 0:
                info_rows.append(("Valor Bonus", green(_format_percent_bonus(item.get("ValorBonusPercentage")))))
        except (TypeError, ValueError):
            pass
    if item.get("LootBonus") is not None:
        try:
            if float(item.get("LootBonus")) > 1:
                info_rows.append(("Loot Bonus", green(_format_percent_bonus(float(item.get("LootBonus")) - 1.0))))
        except (TypeError, ValueError):
            pass

    triggers = _format_trigger_descriptions(item.get("TriggerDescriptions"))
    if triggers:
        info_rows.append(("Item Passives", triggers))

    scaling = _format_scaling_boosts(item.get("ScalingBoosts"))
    if scaling:
        info_rows.append(("Scaling Boosts", scaling))

    props = _format_properties(item.get("Properties"))
    if props:
        info_rows.append(("Properties", props))

    lines.append("== Information ==")
    lines.append(wikitable(info_rows))
    lines.append("")

    sb = stat_boosts_as_dict(item.get("StatBoosts"))
    if sb:
        lines.append("== On equip ==")
        rows = []
        for k, v in sorted(sb.items()):
            label = k.replace("_", " ").title()
            rows.append((f"{_stat_icon(label, stat_icons)} {label}".strip(), green(f"+{fmt_num(v)}")))
        lines.append(wikitable(rows))
        lines.append("")

    proj = item.get("ProjectileDescriptor")
    if proj:
        lines.append("== Weapon stats ==")
        ps = proj.get("Sprite")
        if ps:
            pw = upload_projectile_sprite(site, ps, version)
            if pw:
                lines.append(f"'''Projectile:''' {pw}")
                lines.append("")
        props = item.get("Properties") or {}
        dmg = proj.get("Damage") or {}
        dmin, dmax = dmg.get("Min"), dmg.get("Max")
        range_txt = ""
        if "OVERRIDE_RANGE_TILES" in props:
            range_txt = f"{fmt_num(props['OVERRIDE_RANGE_TILES'])} tiles"
        elif proj.get("Range") is not None:
            range_txt = f"{fmt_num(proj['Range'])} tiles"
        speed = proj.get("Speed")
        pattern = proj.get("Pattern")
        pattern_name = ""
        if isinstance(pattern, dict):
            pattern_name = str(pattern.get("Name") or "")
        elif pattern:
            pattern_name = str(pattern)
        ws_rows = [
            ("Damage", f"'''{fmt_range(dmin, dmax)}'''"),
            ("Range", range_txt),
        ]
        if speed is not None:
            try:
                if float(speed) >= 0.1:
                    ws_rows.append(("Speed", fmt_num(speed)))
            except (TypeError, ValueError):
                ws_rows.append(("Speed", fmt_num(speed)))
        ws_rows.extend([
            ("Rate of fire", f"{fmt_num(proj.get('RateOfFire'))} shots/sec"),
            ("Total projectiles", fmt_num(proj.get("TotalProjectiles"))),
            ("Projectile lifetime", fmt_num(proj.get("ProjectileLifetime"))),
            ("Pierces", "Yes" if proj.get("Pierces") else "No"),
        ])
        if pattern_name:
            ws_rows.append(("Pattern", pattern_name))
        if proj.get("DefensePenetration") is not None:
            try:
                if float(proj.get("DefensePenetration")) > 0:
                    ws_rows.append(("Defense penetration", fmt_num(proj.get("DefensePenetration"))))
            except (TypeError, ValueError):
                pass
        if (proj.get("MaxHitsPerEntity") or 0) > 1:
            ws_rows.append(("Multi-hit", fmt_num(proj.get("MaxHitsPerEntity"))))
        lines.append(wikitable(ws_rows))
        lines.append("")

    lines.append("[[Category:Items]]")
    if unreleased:
        lines.append("[[Category:Unreleased]]")
    type_cats = _categories_from_hierarchy(hier)
    for cat in type_cats:
        lines.append(f"[[Category:{cat}]]")
    tier_label = _normalized_tier_label(tier)
    if tier_label and ("equipment" in hier_l):
        lines.append(f"[[Category:Tier {tier_label} Items]]")
        for cat in type_cats:
            lines.append(f"[[Category:{cat} Tier {tier_label}]]")

    return "\n".join(lines)


def _stat_icon(name: str, stat_icons: dict[str, str] | None) -> str:
    if not stat_icons:
        return ""
    return stat_icons.get(name.lower(), "")


def _format_percent_bonus(v: object) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    sign = "+" if f >= 0 else ""
    return f"{sign}{f * 100:.0f}%"


def _format_trigger_descriptions(raw: object) -> str:
    if not isinstance(raw, list) or not raw:
        return ""
    out: list[str] = []
    for entry in raw:
        if isinstance(entry, (list, tuple)) and len(entry) >= 2:
            trigger = str(entry[0]).strip()
            desc = str(entry[1]).strip()
            if trigger or desc:
                out.append(f"{trigger} -> {desc}".strip(" ->"))
    return "<br>".join(out)


def _format_scaling_boosts(raw: object) -> str:
    if not isinstance(raw, dict) or not raw:
        return ""
    out: list[str] = []
    for stat, spec in sorted(raw.items()):
        label = str(stat)
        if isinstance(spec, dict):
            from_stat = spec.get("ScalesFrom")
            detail = []
            if spec.get("StatCost") is not None:
                detail.append(f"cost: {fmt_num(spec.get('StatCost'))}")
            if spec.get("Per") is not None:
                detail.append(f"per: {fmt_num(spec.get('Per'))}")
            detail_txt = f" ({', '.join(detail)})" if detail else ""
            if from_stat:
                out.append(f"{label}: scales from {from_stat}{detail_txt}")
            else:
                out.append(f"{label}: {spec!s}")
        else:
            out.append(f"{label}: {spec!s}")
    return "<br>".join(out)


def _format_properties(raw: object) -> str:
    if not isinstance(raw, dict) or not raw:
        return ""
    out: list[str] = []
    for k, v in sorted(raw.items()):
        out.append(f"{k}: {v}")
    return "<br>".join(out)
