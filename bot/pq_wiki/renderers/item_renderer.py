from __future__ import annotations

import pywikibot

from pq_wiki.drop_sources import ItemDropSource, format_item_drop_sources_wikitext
from pq_wiki.renderers.entity_renderer import _found_in_location_cell, _format_status_effects, _link_image_wikitext
from pq_wiki.renderers.shared import fmt_range, green, link_entity, signed_delta
from pq_wiki.texture_names import entity_sprite_base, item_sprite_base, tier_icon_filename_base
from pq_wiki.texture_service import upload_projectile_sprite, upload_sprite_if_possible
from pq_wiki.seo import first_wiki_filename_from_file_wikitext, plain_text_for_seo, wiki_seo_block
from pq_wiki.valor_icon import valor_label
from pq_wiki.wikitext_util import (
    defense_penetration_display_html,
    fmt_num,
    html_to_wikitext,
    stat_boosts_as_dict,
    template_invocation,
    type_hierarchy_links,
    wikitable,
)


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
    drop_sources: list[ItemDropSource] | None = None,
    entity_id_to_go: dict[int, dict] | None = None,
    item_name_to_id: dict[str, int] | None = None,
    item_id_to_path: dict[int, str] | None = None,
    item_id_to_item: dict[int, dict] | None = None,
    location_name_to_path: dict[str, str] | None = None,
    location_name_to_portal: dict[str, dict] | None = None,
    go_name_to_id: dict[str, int] | None = None,
    entity_id_to_path: dict[int, str] | None = None,
    status_effect_icons: dict[str, str] | None = None,
    status_effect_name_to_path: dict[str, str] | None = None,
    valor_icon_wikitext: str | None = None,
) -> str:
    tier = item.get("Tier", "")
    hier = item.get("TypeHierarchy") or []
    desc = html_to_wikitext(item.get("Description", ""))
    hier_l = [str(h).lower() for h in hier]
    show_tier = ("equipment" in hier_l) or ("skin" in hier_l)

    iid = int(item.get("Id") or 0)
    iname = str(item.get("Name") or f"Item {iid}")
    icon = upload_sprite_if_possible(
        site, item.get("Sprite"), version, logical_name=item_sprite_base(iid, iname)
    )
    tier_icon = ""
    if show_tier and item.get("TierIcon"):
        tier_icon = upload_sprite_if_possible(
            site,
            item["TierIcon"],
            version,
            thumb_size=16,
            logical_name=tier_icon_filename_base(item["TierIcon"]),
        )

    head = ""
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

    desc_block = f"''{desc}''" if desc else ""

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
                vb = _format_percent_bonus(item.get("ValorBonusPercentage"))
                info_rows.append(
                    (valor_label("Valor Bonus", valor_icon_wikitext), green(f"'''{vb}'''")),
                )
        except (TypeError, ValueError):
            pass
    if item.get("LootBonus") is not None:
        try:
            if float(item.get("LootBonus")) > 1:
                info_rows.append(("Loot Bonus", green(_format_percent_bonus(float(item.get("LootBonus")) - 1.0))))
        except (TypeError, ValueError):
            pass

    hier_set = {str(h) for h in hier}
    if item.get("IsGloballyAnnounced"):
        info_rows.append(
            (
                "Drop",
                '<span style="font-size:0.85em;border:1px solid #c9a227;border-radius:3px;padding:1px 6px;color:#b8860b" '
                'title="Globally announced in-game when this item drops">Globally Announced</span>',
            )
        )

    _append_consumable_value_row(item, hier, hier_set, hier_l, info_rows, valor_icon_wikitext)
    _append_numeric_and_commerce_rows(item, info_rows, valor_icon_wikitext)
    _append_weapon_and_area_rows(item, hier_set, info_rows)
    _append_status_and_effect_rows(
        item, hier_set, info_rows, status_effect_icons, status_effect_name_to_path
    )
    _append_type_specific_rows(
        site,
        item,
        version,
        hier_set,
        info_rows,
        item_name_to_id,
        item_id_to_path,
        item_id_to_item,
        location_name_to_path,
        location_name_to_portal,
        go_name_to_id,
        entity_id_to_path,
        entity_id_to_go,
        status_effect_icons,
        status_effect_name_to_path,
    )

    triggers = _format_trigger_descriptions(item.get("TriggerDescriptions"))
    if triggers:
        info_rows.append(("Item Passives", triggers))

    scaling = _format_scaling_boosts(item.get("ScalingBoosts"))
    if scaling:
        info_rows.append(("Scaling Boosts", scaling))

    props = _format_properties(item.get("Properties"))
    if props:
        info_rows.append(("Properties", props))

    information_table = wikitable(info_rows)

    on_equip_block = ""
    sb = stat_boosts_as_dict(item.get("StatBoosts"))
    if sb:
        rows = []
        for k, v in sorted(sb.items()):
            label = k.replace("_", " ").title()
            st_icon = _stat_icon(label, stat_icons)
            left = f"{st_icon} {label}".strip() if st_icon else label
            rows.append((left, signed_delta(v, bold=True)))
        on_equip_block = "== On equip ==\n" + wikitable(rows)

    weapon_block = ""
    proj = item.get("ProjectileDescriptor")
    if proj:
        wparts: list[str] = ["== Weapon stats =="]
        ps = proj.get("Sprite")
        if ps:
            pw = upload_projectile_sprite(site, ps, version)
            if pw:
                wparts.append(f"'''Projectile:''' {pw}")
                wparts.append("")
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
        tp = proj.get("TotalProjectiles")
        try:
            zero_projectiles = tp is not None and float(tp) == 0.0
        except (TypeError, ValueError):
            zero_projectiles = False

        healing_raw = proj.get("IsHealingProjectile")
        is_healing_projectile = False
        if isinstance(healing_raw, bool):
            is_healing_projectile = healing_raw
        elif isinstance(healing_raw, (int, float)):
            is_healing_projectile = float(healing_raw) != 0.0
        elif isinstance(healing_raw, str):
            is_healing_projectile = healing_raw.strip().lower() in {"1", "true", "yes", "y"}

        amount_label = "Heal" if is_healing_projectile else "Damage"
        amount_value = f"'''{fmt_range(dmin, dmax)}'''"
        if is_healing_projectile:
            amount_value = green(amount_value)

        ws_rows: list[tuple[str, str]] = [
            (amount_label, amount_value),
        ]
        if not zero_projectiles:
            ws_rows.append(("Range", range_txt))
            if speed is not None:
                try:
                    if float(speed) >= 0.1:
                        ws_rows.append(("Speed", f"{fmt_num(speed)} tiles/sec"))
                except (TypeError, ValueError):
                    ws_rows.append(("Speed", f"{fmt_num(speed)} tiles/sec"))
            rof = proj.get("RateOfFire")
            try:
                if rof is not None and float(rof) != 0.0:
                    ws_rows.append(("Rate of fire", f"{fmt_num(rof)} shots/sec"))
            except (TypeError, ValueError):
                if rof is not None:
                    ws_rows.append(("Rate of fire", f"{fmt_num(rof)} shots/sec"))
            ws_rows.extend(
                [
                    ("Total projectiles", fmt_num(proj.get("TotalProjectiles"))),
                    ("Projectile lifetime", f"{fmt_num(proj.get('ProjectileLifetime'))} sec"),
                    ("Pierces", "Yes" if proj.get("Pierces") else "No"),
                ]
            )
            if pattern_name:
                ws_rows.append(("Pattern", pattern_name))
            if proj.get("DefensePenetration") is not None:
                dp_cell = defense_penetration_display_html(proj.get("DefensePenetration"))
                if dp_cell:
                    ws_rows.append(("Defense penetration", dp_cell))
            if (proj.get("MaxHitsPerEntity") or 0) > 1:
                ws_rows.append(("Multi-hit", fmt_num(proj.get("MaxHitsPerEntity"))))
        pse = proj.get("StatusEffects")
        if pse:
            pse_cell = _format_status_effects(
                pse, status_effect_icons, status_effect_name_to_path
            )
            if pse_cell:
                ws_rows.append(("Status effects", pse_cell))
        if "Secondary Ability" in hier_set and item.get("Cooldown") is not None:
            try:
                cd = float(item["Cooldown"])
                ws_rows.append(("Cooldown", f"{fmt_num(cd)} sec"))
            except (TypeError, ValueError):
                pass
        wparts.append(wikitable(ws_rows))
        weapon_block = "\n".join(wparts)

    dropped_by_block = ""
    if drop_sources:
        dropped_by_block = format_item_drop_sources_wikitext(
            drop_sources,
            site,
            version,
            entity_id_to_go or {},
        )

    cat_lines = ["[[Category:Items]]"]
    if unreleased:
        cat_lines.append("[[Category:Unreleased]]")
    type_cats = _categories_from_hierarchy(hier)
    for cat in type_cats:
        cat_lines.append(f"[[Category:{cat}]]")
    tier_label = _normalized_tier_label(tier)
    if tier_label and ("equipment" in hier_l):
        cat_lines.append(f"[[Category:{tier_label} Items]]")
        for cat in type_cats:
            cat_lines.append(f"[[Category:{cat} {tier_label}]]")
    categories_block = "\n".join(cat_lines)

    body = template_invocation(
        "PQ Item",
        [
            ("head", head),
            ("icon", icon),
            ("desc", desc_block),
            ("information", information_table),
            ("on_equip", on_equip_block),
            ("weapon", weapon_block),
            ("dropped_by", dropped_by_block),
            ("categories", categories_block),
        ],
        always_emit_keys=frozenset({"head"}),
    )
    item_name = str(item.get("Name") or f"Item {item.get('Id')}")
    desc_plain = plain_text_for_seo(desc)
    seo_desc = (
        f"{item_name} — {desc_plain}. Pixel Quest Wiki."
        if desc_plain
        else f"{item_name} — Pixel Quest Wiki item."
    )
    seo = wiki_seo_block(
        site,
        page_title=item_name,
        description=seo_desc,
        wiki_image_filename=first_wiki_filename_from_file_wikitext(icon),
        image_alt=f"{item_name} icon",
    )
    return f"{body}\n\n{seo}"


_POTION_STAT_SHORT = {
    "Health": "HP",
    "Mana": "MP",
    "Defense": "DEF",
    "Attack": "ATK",
    "Vitality": "VIT",
    "Wisdom": "WIS",
    "Dexterity": "DEX",
}


def _format_duration_short(sec: object) -> str:
    try:
        w = float(sec)
    except (TypeError, ValueError):
        return str(sec)
    if w < 0:
        return str(sec)
    whole = int(w)
    if whole < 60:
        return f"{whole}s"
    parts: list[str] = []
    remaining = whole
    days = remaining // 86400
    remaining %= 86400
    hours = remaining // 3600
    remaining %= 3600
    mins = remaining // 60
    secs = remaining % 60
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    if not parts and secs:
        parts.append(f"{secs}s")
    elif parts and secs:
        parts.append(f"{secs}s")
    return " ".join(parts) if parts else f"{whole}s"


def _format_multiplier_display(raw: object) -> str:
    try:
        f = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    return f"{f:g}x"


def _mana_cost_cell(raw: object) -> str:
    return f'<span style="color:#1e6fd9;font-weight:bold">{fmt_num(raw)}</span>'


def _append_numeric_and_commerce_rows(
    item: dict,
    info_rows: list[tuple[str, str]],
    valor_icon_wikitext: str | None,
) -> None:
    rp = item.get("RobuxPrice")
    try:
        if rp is not None and float(rp) > 0:
            info_rows.append(("Robux price", fmt_num(rp)))
    except (TypeError, ValueError):
        pass
    # Only show stack limit for stackable items.
    if "IsStackable" in item:
        is_stackable_raw = item.get("IsStackable")
        is_stackable = False
        if isinstance(is_stackable_raw, bool):
            is_stackable = is_stackable_raw
        elif isinstance(is_stackable_raw, (int, float)):
            is_stackable = float(is_stackable_raw) > 0
        elif isinstance(is_stackable_raw, str):
            is_stackable = is_stackable_raw.strip().lower() in ("1", "true", "yes", "y")

        if is_stackable:
            sl = item.get("StackLimit")
            try:
                if sl is not None and float(sl) > 0:
                    info_rows.append(("Stack limit", fmt_num(sl)))
            except (TypeError, ValueError):
                pass
    vp = item.get("ValorPrice")
    try:
        if vp is not None and float(vp) > 0:
            info_rows.append(
                (valor_label("Valor price", valor_icon_wikitext), fmt_num(vp)),
            )
    except (TypeError, ValueError):
        pass
    fv = item.get("ForgeValor")
    try:
        if fv is not None and float(fv) > 0:
            info_rows.append(
                (valor_label("Forge valor", valor_icon_wikitext), fmt_num(fv)),
            )
    except (TypeError, ValueError):
        pass
    if item.get("ExpBonus") is not None:
        try:
            if float(item.get("ExpBonus")) > 1:
                info_rows.append(
                    ("EXP bonus", green(_format_percent_bonus(float(item.get("ExpBonus")) - 1.0))),
                )
        except (TypeError, ValueError):
            pass


def _potion_value_row(item: dict) -> tuple[str, str] | None:
    val = item.get("Value")
    try:
        v = float(val) if val is not None else 0.0
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    if item.get("IsExp"):
        return ("Effect", green(f"+{fmt_num(v)} Exp"))
    stat = item.get("Stat")
    st = str(stat).strip() if stat is not None else ""
    if not st or st.lower() == "none":
        return ("Value", fmt_num(v))
    short = _POTION_STAT_SHORT.get(st, st)
    return ("Effect", green(f"+{fmt_num(v)} {short}"))


def _append_consumable_value_row(
    item: dict,
    hier: list,
    hier_set: set[str],
    hier_l: list[str],
    info_rows: list[tuple[str, str]],
    valor_icon_wikitext: str | None,
) -> None:
    if "consumable" not in hier_l:
        return
    if hier and str(hier[0]) == "Potion":
        row = _potion_value_row(item)
        if row:
            info_rows.append(row)
        return
    val = item.get("Value")
    try:
        v = float(val) if val is not None else 0.0
    except (TypeError, ValueError):
        return
    if v <= 0:
        return
    name = str(item.get("Name") or "")
    if hier and str(hier[0]) == "Backpack":
        info_rows.append(("Inventory space", green(f"+{fmt_num(v)}")))
        return
    if "Event Consumable" in hier_set:
        info_rows.append(("Global points", green(f"+{fmt_num(v)}")))
        return
    if hier and str(hier[0]) == "Coin" and "Valor" in name:
        info_rows.append(
            (valor_label("Valor", valor_icon_wikitext), green(f"+{fmt_num(v)}")),
        )
        return
    info_rows.append(("Value", fmt_num(v)))


def _append_weapon_and_area_rows(item: dict, hier_set: set[str], info_rows: list[tuple[str, str]]) -> None:
    mc = item.get("ManaCost")
    try:
        if mc is not None and float(mc) > 0:
            info_rows.append(("Mana cost", _mana_cost_cell(mc)))
    except (TypeError, ValueError):
        pass
    mud = item.get("MaxUsageDistance")
    if mud is not None:
        try:
            if float(mud) > 0:
                tiles = float(mud) / 50.0
                info_rows.append(("Max usage distance", f"{fmt_num(tiles)} tiles"))
        except (TypeError, ValueError):
            pass


def _append_status_and_effect_rows(
    item: dict,
    hier_set: set[str],
    info_rows: list[tuple[str, str]],
    status_effect_icons: dict[str, str] | None,
    status_effect_name_to_path: dict[str, str] | None = None,
) -> None:
    se = item.get("StatusEffects")
    if se:
        cell = _format_status_effects(se, status_effect_icons, status_effect_name_to_path)
        if cell:
            info_rows.append(("Status effects", cell))
    if "Flag" in hier_set or "Bomb" in hier_set:
        er = item.get("EffectRange")
        try:
            if er is not None and float(er) > 0:
                tiles = float(er) / 50.0
                info_rows.append(("Effect range", f"{fmt_num(tiles)} tiles"))
        except (TypeError, ValueError):
            pass
    ed = item.get("EffectDuration")
    if ed is None:
        return
    try:
        edf = float(ed)
    except (TypeError, ValueError):
        return
    if edf <= 0:
        return
    if "Infusion" in hier_set:
        info_rows.append(("Effect duration", _format_duration_short(edf)))
    elif "Flag" in hier_set or "Bomb" in hier_set:
        info_rows.append(("Effect duration", f"{fmt_num(edf)} sec"))


def _format_item_link_with_sprite(
    site: pywikibot.Site,
    iid: int,
    item_name: str,
    version: str,
    item_id_to_path: dict[int, str] | None,
    item_id_to_item: dict[int, dict] | None,
) -> str:
    path = item_id_to_path.get(iid) if item_id_to_path else None
    it = item_id_to_item.get(iid) if item_id_to_item else None
    icon = ""
    if it:
        icon = upload_sprite_if_possible(
            site,
            it.get("Sprite"),
            version,
            thumb_size=40,
            logical_name=item_sprite_base(iid, str(it.get("Name") or f"Item {iid}")),
        )
        if icon and path:
            icon = _link_image_wikitext(icon, path)
    label = f"[[{path}|{item_name}]]" if path else item_name
    return f"{icon} {label}".strip()


def _format_entity_link_with_sprite(
    site: pywikibot.Site,
    go: dict,
    version: str,
    entity_id_to_path: dict[int, str] | None,
) -> str:
    gid = int(go["Id"])
    path = entity_id_to_path.get(gid) if entity_id_to_path else None
    name = str(go.get("Name") or gid)
    icon = upload_sprite_if_possible(
        site, go.get("Sprite"), version, thumb_size=40, logical_name=entity_sprite_base(gid, name)
    )
    if icon and path:
        icon = _link_image_wikitext(icon, path)
    label = f"[[{path}|{name}]]" if path else name
    return f"{icon} {label}".strip()


def _append_type_specific_rows(
    site: pywikibot.Site,
    item: dict,
    version: str,
    hier_set: set[str],
    info_rows: list[tuple[str, str]],
    item_name_to_id: dict[str, int] | None,
    item_id_to_path: dict[int, str] | None,
    item_id_to_item: dict[int, dict] | None,
    location_name_to_path: dict[str, str] | None,
    location_name_to_portal: dict[str, dict] | None,
    go_name_to_id: dict[str, int] | None,
    entity_id_to_path: dict[int, str] | None,
    entity_id_to_go: dict[int, dict] | None,
    status_effect_icons: dict[str, str] | None,
    status_effect_name_to_path: dict[str, str] | None = None,
) -> None:
    if "Clover" in hier_set:
        if item.get("LuckBoost") is not None:
            try:
                if float(item.get("LuckBoost")) > 1:
                    info_rows.append(("Luck boost", _format_multiplier_display(item.get("LuckBoost"))))
            except (TypeError, ValueError):
                pass
        ds = item.get("DurationSeconds")
        if ds is not None:
            try:
                if float(ds) > 0:
                    info_rows.append(("Duration", _format_duration_short(ds)))
            except (TypeError, ValueError):
                pass
    if "Experience Booster" in hier_set:
        if item.get("ExperienceMultiplier") is not None:
            try:
                if float(item.get("ExperienceMultiplier")) > 1:
                    info_rows.append(
                        ("EXP multiplier", _format_multiplier_display(item.get("ExperienceMultiplier"))),
                    )
            except (TypeError, ValueError):
                pass
        ds = item.get("DurationSeconds")
        if ds is not None:
            try:
                if float(ds) > 0:
                    info_rows.append(("Duration", _format_duration_short(ds)))
            except (TypeError, ValueError):
                pass
    if "Server Booster" in hier_set:
        if item.get("Boost") is not None:
            try:
                if float(item.get("Boost")) > 1:
                    info_rows.append(("Boost", _format_multiplier_display(item.get("Boost"))))
            except (TypeError, ValueError):
                pass
        ds = item.get("DurationSeconds")
        if ds is not None:
            try:
                if float(ds) > 0:
                    info_rows.append(("Duration", _format_duration_short(ds)))
            except (TypeError, ValueError):
                pass
        sbid = item.get("ServerBoostId")
        if sbid is not None:
            try:
                n = int(sbid)
                label = "Luck" if n == 0 else "EXP" if n == 1 else f"Type {n}"
                info_rows.append(("Server boost", label))
            except (TypeError, ValueError):
                pass
    if "Key" in hier_set and item.get("Dungeon"):
        dname = str(item.get("Dungeon"))
        info_rows.append(
            (
                "Dungeon",
                _found_in_location_cell(
                    site,
                    dname,
                    version,
                    location_name_to_path,
                    location_name_to_portal,
                ),
            ),
        )
    pk = item.get("PossibleKeys")
    if isinstance(pk, list) and pk:
        lines: list[str] = []
        for key_name in pk:
            if not isinstance(key_name, str):
                continue
            if item_name_to_id and item_id_to_path is not None:
                iid = item_name_to_id.get(key_name)
                if iid is not None:
                    lines.append(
                        _format_item_link_with_sprite(
                            site,
                            int(iid),
                            key_name,
                            version,
                            item_id_to_path,
                            item_id_to_item,
                        )
                    )
                else:
                    lines.append(key_name)
            else:
                lines.append(key_name)
        if lines:
            info_rows.append(("Possible keys", "<br>".join(lines)))
    if "Soul" in hier_set:
        cid = item.get("ChestItemId")
        if cid is not None:
            try:
                ci = int(cid)
            except (TypeError, ValueError):
                ci = None
            if ci is not None:
                it = item_id_to_item.get(ci) if item_id_to_item else None
                nm = str(it.get("Name") or f"Item {ci}") if it else f"Item {ci}"
                path = item_id_to_path.get(ci) if item_id_to_path else None
                if it and path and item_id_to_path is not None:
                    info_rows.append(
                        (
                            "Chest reward",
                            _format_item_link_with_sprite(
                                site, ci, nm, version, item_id_to_path, item_id_to_item
                            ),
                        ),
                    )
                elif path:
                    info_rows.append(("Chest reward", f"[[{path}|{nm}]]"))
                else:
                    info_rows.append(("Chest reward", nm))
        rq = item.get("RequiredQuantity")
        if rq is not None:
            try:
                if float(rq) > 0:
                    info_rows.append(("Souls to consume", fmt_num(rq)))
            except (TypeError, ValueError):
                pass
    if "Postcard" in hier_set:
        if item.get("Quote"):
            info_rows.append(("Quote", html_to_wikitext(str(item.get("Quote")))))
        if item.get("Signature"):
            info_rows.append(("Signature", html_to_wikitext(str(item.get("Signature")))))
        rid = item.get("RecipentUserId")
        if rid is not None:
            try:
                uid = int(rid)
                url = f"https://www.roblox.com/users/{uid}/profile"
                # External link syntax — not raw HTML: template param escaping mangles "=" in attributes.
                info_rows.append(
                    ("Recipient", f"[{url} Roblox profile ({uid})]"),
                )
            except (TypeError, ValueError):
                pass
    if "Object Spawner" in hier_set:
        tid = item.get("TargetObjectId")
        go_obj: dict | None = None
        if tid is not None and entity_id_to_go:
            try:
                tii = int(tid)
                go_obj = entity_id_to_go.get(tii)
            except (TypeError, ValueError):
                go_obj = None
        if go_obj:
            info_rows.append(
                ("Spawns", _format_entity_link_with_sprite(site, go_obj, version, entity_id_to_path)),
            )
        elif item.get("ObjectName") and go_name_to_id and entity_id_to_path is not None:
            oname = str(item.get("ObjectName"))
            info_rows.append(
                ("Spawns", link_entity(oname, go_name_to_id, entity_id_to_path)),
            )
        elif item.get("ObjectName"):
            info_rows.append(("Spawns", str(item.get("ObjectName"))))
        ol = item.get("ObjectLifetime")
        if ol is not None:
            try:
                if float(ol) > 0:
                    info_rows.append(("Object lifetime", f"{fmt_num(ol)} sec"))
            except (TypeError, ValueError):
                pass


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
