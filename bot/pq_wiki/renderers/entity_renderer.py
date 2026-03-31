from __future__ import annotations

import html
import pywikibot

from pq_wiki.renderers.shared import fmt_range, format_drop
from pq_wiki.seo import first_wiki_filename_from_file_wikitext, wiki_seo_block
from pq_wiki.skin_drops import format_skin_drop_cell
from pq_wiki.texture_names import (
    entity_sprite_base,
    item_sprite_base,
    portal_preview_base,
    projectile_sprite_base,
    slug,
    tier_icon_filename_base,
)
from pq_wiki.texture_service import upload_portal_preview, upload_projectile_sprite, upload_sprite_if_possible
from pq_wiki.wikitext_util import (
    defense_penetration_attack_line_html,
    fmt_num,
    template_invocation,
)


def _trailing_nl(s: str) -> str:
    """So consecutive template params can be written on one line without merging sections."""
    if not s:
        return s
    return s if s.endswith("\n") else s + "\n"


def _html_statistics_table(rows: list[tuple[str, str]]) -> str:
    """HTML table (not wikitext {{!}}) so {{PQ Entity|statistics=…}} survives pipe escaping."""
    if not rows:
        return ""
    lines = ['<table class="wikitable">']
    for k, v in rows:
        lines.append(f'<tr><th scope="row">{k}</th><td>{v}</td></tr>')
    lines.append("</table>")
    return "\n".join(lines)


def build_entity_wikitext(
    site: pywikibot.Site,
    go: dict,
    version: str,
    item_name_to_id: dict[str, int],
    item_id_to_path: dict[int, str],
    item_id_to_item: dict[int, dict] | None,
    go_name_to_id: dict[str, int],
    entity_id_to_path: dict[int, str],
    location_name_to_path: dict[str, str] | None = None,
    location_name_to_portal: dict[str, dict] | None = None,
    entity_name_to_locations: dict[str, list[str]] | None = None,
    drop_tier_icon_parts: dict[int, dict[str, str]] | None = None,
    stat_icons: dict[str, str] | None = None,
    status_effect_icons: dict[str, str] | None = None,
    status_effect_name_to_path: dict[str, str] | None = None,
    unreleased: bool = False,
    entity_id_to_go: dict[int, dict] | None = None,
    skin_id_to_skin: dict[int, dict] | None = None,
    skin_id_to_path: dict[int, str] | None = None,
    skin_rarity_icon_wikitext: dict[int, str] | None = None,
) -> str:
    gid = go["Id"]
    name = go.get("Name", f"Entity {gid}")
    hostile = go.get("IsHostile")
    is_boss = bool(
        go.get("IsBiomeBoss")
        or go.get("IsTroomBoss")
        or go.get("IsDungeonBoss")
        or go.get("IsWorldBoss")
    )

    icon = upload_sprite_if_possible(
        site, go.get("Sprite"), version, logical_name=entity_sprite_base(gid, str(name))
    )

    hp = go.get("Health")
    stats = go.get("Stats") or {}
    df = stats.get("Defense")
    if df is None:
        df = go.get("Defense")

    found_parts: list[str] = []
    if entity_name_to_locations:
        for loc_name in entity_name_to_locations.get(str(name), []) or []:
            found_parts.append(
                _found_in_location_cell(
                    site,
                    str(loc_name),
                    version,
                    location_name_to_path,
                    location_name_to_portal,
                )
            )
    if found_parts:
        # Use <h2> not == … == — "=" in params is escaped as {{=}} and breaks wiki headings.
        found_in_str = "<h2>Found in locations</h2>\n" + ", ".join(found_parts)
    else:
        found_in_str = ""

    event_biomes = go.get("EventBiomes") or []
    if event_biomes:
        event_biomes_str = "<h2>Event biomes</h2>\n" + ", ".join(
            _link_location_name(str(b), location_name_to_path) for b in event_biomes
        )
    else:
        event_biomes_str = ""

    exp = go.get("ExperienceValue") or {}
    st_rows: list[tuple[str, str]] = []
    if hostile:
        st_rows.extend(
            [
                (f"{_stat_icon('Health', stat_icons)} Health".strip(), f"{fmt_num(hp)} HP"),
                (f"{_stat_icon('Defense', stat_icons)} Defense".strip(), fmt_num(df)),
                ("Experience", fmt_range(exp.get("Min"), exp.get("Max"))),
            ]
        )
    imm_txt = _format_immunities(
        go.get("Immunity"), status_effect_icons, status_effect_name_to_path
    )
    if imm_txt:
        st_rows.append(("Immunity", imm_txt))
    statistics_table = _html_statistics_table(st_rows) if st_rows else ""

    private_drops = go.get("PrivateDrops") or []
    public_drops = go.get("PublicDrops") or []
    drops = [*private_drops, *public_drops]
    loot_block = _build_loot_section_wikitext(
        site,
        go,
        drops,
        version,
        item_name_to_id,
        item_id_to_path,
        item_id_to_item,
        go_name_to_id,
        drop_tier_icon_parts,
        skin_id_to_skin=skin_id_to_skin,
        skin_id_to_path=skin_id_to_path,
        skin_rarity_icon_wikitext=skin_rarity_icon_wikitext,
    )

    projs = go.get("ProjectileDescriptors") or []
    attacks_block = _build_attacks_section_wikitext(
        site, projs, version, status_effect_icons, status_effect_name_to_path
    )

    speeches_block = _format_speeches_section(go)
    spawns_block = _format_spawns_section(
        site,
        go,
        version,
        entity_id_to_path,
        entity_id_to_go,
    )

    if hostile:
        cat_lines = ["[[Category:Enemies]]"]
    else:
        cat_lines = ["[[Category:Entities]]", "[[Category:Friendlies]]"]
    # Sidebar navigation buckets.
    if is_boss:
        cat_lines.append("[[Category:Bosses]]")
    elif not hostile:
        cat_lines.append("[[Category:NPCs]]")
    if unreleased:
        cat_lines.append("[[Category:Unreleased]]")
    categories_block = "\n".join(cat_lines)

    body = template_invocation(
        "PQ Entity",
        [
            ("icon", _trailing_nl(icon) if icon else ""),
            ("found_in", _trailing_nl(found_in_str)),
            ("event_biomes", _trailing_nl(event_biomes_str)),
            ("statistics", _trailing_nl(statistics_table)),
            ("speeches", _trailing_nl(speeches_block)),
            ("spawns", _trailing_nl(spawns_block)),
            ("loot", _trailing_nl(loot_block)),
            ("attacks", _trailing_nl(attacks_block)),
            ("categories", categories_block),
        ],
    )
    if is_boss:
        seo_desc = f"{name} — boss in Pixel Quest."
    elif hostile:
        seo_desc = f"{name} — enemy in Pixel Quest."
    else:
        seo_desc = f"{name} — friendly NPC in Pixel Quest."
    seo = wiki_seo_block(
        site,
        page_title=name,
        description=seo_desc,
        wiki_image_filename=first_wiki_filename_from_file_wikitext(icon),
        image_alt=f"{name} sprite",
    )
    return f"{body}\n\n{seo}"


def _format_speeches_section(go: dict) -> str:
    raw = go.get("Speeches")
    if not isinstance(raw, list) or not raw:
        return ""
    spawn_m = go.get("SpawnMessage")
    despawn_m = go.get("DespawnMessage")
    lines: list[str] = []
    for entry in raw:
        text = str(entry).strip() if entry is not None else ""
        if not text:
            continue
        safe = html.escape(text, quote=True)
        line = f'<span style="font-style:italic">"{safe}"</span>'
        tags: list[str] = []
        if spawn_m is not None and text == str(spawn_m).strip():
            tags.append("Spawn cue")
        if despawn_m is not None and text == str(despawn_m).strip():
            tags.append("Despawn cue")
        if tags:
            tag_txt = ", ".join(tags)
            line += f' <small style="color:#666">({tag_txt})</small>'
        lines.append(f"* {line}")
    if not lines:
        return ""
    return "<h2>Dialogue</h2>\n" + "\n".join(lines)


def _format_spawns_section(
    site: pywikibot.Site,
    go: dict,
    version: str,
    entity_id_to_path: dict[int, str],
    entity_id_to_go: dict[int, dict] | None,
) -> str:
    raw = go.get("Reproduction")
    if not isinstance(raw, list) or not raw:
        return ""
    if not entity_id_to_go or not entity_id_to_path:
        return ""
    eids: list[int] = []
    seen: set[int] = set()
    for entry in raw:
        try:
            eid = int(entry)
        except (TypeError, ValueError):
            continue
        if eid in seen:
            continue
        child = entity_id_to_go.get(eid)
        path = entity_id_to_path.get(eid)
        if not child or not path:
            continue
        seen.add(eid)
        eids.append(eid)

    if not eids:
        return ""

    def _spawn_sort_key(eid: int) -> tuple[str, int]:
        ch = entity_id_to_go[eid]
        label = str(ch.get("Name") or f"Entity {eid}")
        return (label.lower(), eid)

    eids.sort(key=_spawn_sort_key)
    out_lines = [
        f"* {_format_spawned_entity_line(site, eid, version, entity_id_to_path, entity_id_to_go)}"
        for eid in eids
    ]
    return "<h2>Spawns</h2>\n" + "\n".join(out_lines)


def _format_spawned_entity_line(
    site: pywikibot.Site,
    eid: int,
    version: str,
    entity_id_to_path: dict[int, str],
    entity_id_to_go: dict[int, dict] | None,
) -> str:
    child = entity_id_to_go.get(eid) if entity_id_to_go else None
    path = entity_id_to_path.get(eid)
    if not child or not path:
        return ""
    nm = str(child.get("Name") or f"Entity {eid}")
    icon = upload_sprite_if_possible(
        site,
        child.get("Sprite"),
        version,
        thumb_size=40,
        logical_name=entity_sprite_base(eid, nm),
    )
    if icon:
        icon = _link_image_wikitext(icon, path)
    label = f"[[{path}|{nm}]]"
    return f"{icon} {label}".strip()


_LOOT_DROP_ROWS_PER_SUBCOLUMN = 5


def _layout_drops_multicolumn(
    rendered_rows: list[str],
    max_per_col: int = _LOOT_DROP_ROWS_PER_SUBCOLUMN,
    inner_table_width: str = "100%",
) -> str:
    """
    Stack drops in sub-columns: at most max_per_col rows per column, then more columns to the right.

    Uses HTML <table> (not nested wikitext {|) so layout survives inside {{PQ Entity|loot=…}}
    where | is escaped as {{!}} — nested {|…|} breaks after escaping.
    """
    if not rendered_rows:
        return ""
    if len(rendered_rows) <= max_per_col:
        return "<br>".join(rendered_rows)
    cols: list[str] = []
    for i in range(0, len(rendered_rows), max_per_col):
        cols.append("<br>".join(rendered_rows[i : i + max_per_col]))
    tds: list[str] = []
    for ci, col_text in enumerate(cols):
        if ci > 0:
            td_style = (
                "vertical-align:top; border:none; border-left:1px solid #a7a7a7; "
                "padding-left:10px;"
            )
        else:
            td_style = "vertical-align:top; border:none; padding-right:6px;"
        tds.append(f'<td style="{td_style}">{col_text}</td>')
    tbl_style = (
        f"width:{inner_table_width}; border-collapse:collapse; border:none; "
        "background:transparent; margin:0;"
    )
    return (
        f'<table role="presentation" style="{tbl_style}"><tr>'
        + "".join(tds)
        + "</tr></table>"
    )


def _build_loot_section_wikitext(
    site: pywikibot.Site,
    go: dict,
    drops: list,
    version: str,
    item_name_to_id: dict[str, int],
    item_id_to_path: dict[int, str],
    item_id_to_item: dict[int, dict] | None,
    go_name_to_id: dict[str, int],
    drop_tier_icon_parts: dict[int, dict[str, str]] | None,
    skin_id_to_skin: dict[int, dict] | None = None,
    skin_id_to_path: dict[int, str] | None = None,
    skin_rarity_icon_wikitext: dict[int, str] | None = None,
) -> str:
    if not drops:
        return ""
    lines: list[str] = [
        "<h2>Loot</h2>",
        '<table class="wikitable">',
        "<tr><th>Drop Type</th><th>Drop</th></tr>",
    ]
    normalized = _normalize_enemy_drops(
        drops,
        item_name_to_id,
        item_id_to_item,
        skin_id_to_skin=skin_id_to_skin,
    )
    groups: dict[int, list[dict]] = {}
    for nd in normalized:
        tier = int(nd.get("drop_tier_type") or 0)
        groups.setdefault(tier, []).append(nd)
    is_boss = bool(
        go.get("IsBiomeBoss")
        or go.get("IsTroomBoss")
        or go.get("IsDungeonBoss")
        or go.get("IsWorldBoss")
    )
    for tier in sorted(groups.keys(), reverse=True):
        entries = sorted(
            groups[tier],
            key=lambda x: (
                -int(x.get("tier_sort_value") or 0),
                str(x.get("type_label") or ""),
                str(x.get("name") or ""),
            ),
        )
        rendered_rows: list[str] = []
        for nd in entries:
            body = _render_normalized_enemy_drop_entry(
                site,
                nd,
                version,
                item_id_to_path,
                item_id_to_item,
                skin_id_to_skin=skin_id_to_skin,
                skin_id_to_path=skin_id_to_path,
                skin_rarity_icon_wikitext=skin_rarity_icon_wikitext,
            )
            if not body:
                continue
            rendered_rows.append(str(body).replace("\n", "<br>"))
        if not rendered_rows:
            continue
        group_icon = ""
        if drop_tier_icon_parts and tier in drop_tier_icon_parts:
            part = "chest" if is_boss else "bag"
            group_icon = drop_tier_icon_parts[tier].get(part, "")
        drop_cell = _layout_drops_multicolumn(rendered_rows)
        lines.append(
            '<tr><td style="vertical-align:middle;text-align:center;">'
            f"{group_icon}</td><td>{drop_cell}</td></tr>"
        )
    if not groups:
        for d in drops:
            fd = format_drop(
                d,
                item_name_to_id,
                item_id_to_path,
                go_name_to_id,
                skin_id_to_skin=skin_id_to_skin,
                skin_id_to_path=skin_id_to_path,
                skin_rarity_icon_wikitext=skin_rarity_icon_wikitext,
                site=site,
                version=version,
            )
            lines.append(
                '<tr><td style="vertical-align:middle;text-align:center;"></td>'
                f"<td>{fd}</td></tr>"
            )
    lines.append("</table>")
    return "\n".join(lines)


_ATTACK_TABLE_COLS: tuple[tuple[str, str], ...] = (
    ("image", "Image"),
    ("damage", "Damage"),
    ("range", "Range (tiles)"),
    ("speed", "Speed (tiles/sec)"),
    ("status", "Status effects"),
    ("other", "Other"),
)


def _build_attacks_section_wikitext(
    site: pywikibot.Site,
    projs: list,
    version: str,
    status_effect_icons: dict[str, str] | None,
    status_effect_name_to_path: dict[str, str] | None = None,
) -> str:
    if not projs:
        return ""
    attack_rows: list[dict[str, str]] = []
    has_image = False
    has_damage = False
    has_range = False
    has_speed = False
    has_status = False
    has_other = False
    for p in projs:
        pw = _attack_image_for_projectile(site, p, version)
        dmg = p.get("Damage") or {}
        speed = p.get("Speed")
        range_txt = ""
        is_aoe = False
        try:
            is_aoe = float(p.get("RadiusOfEffect") or 0) > 0
        except (TypeError, ValueError):
            is_aoe = False
        if not is_aoe and p.get("Range") is not None:
            try:
                if float(p.get("Range")) >= 0.1:
                    range_txt = fmt_num(p.get("Range"))
            except (TypeError, ValueError):
                range_txt = fmt_num(p.get("Range"))
        speed_txt = ""
        other: list[str] = []
        if is_aoe:
            try:
                aoe_tiles = float(p.get("RadiusOfEffect") or 0) / 50.0
                if aoe_tiles > 0:
                    other.append(f"AOE Radius {fmt_num(aoe_tiles)} tiles")
            except (TypeError, ValueError):
                pass
        if speed is not None:
            try:
                if float(speed) >= 0.1:
                    speed_txt = fmt_num(speed)
            except (TypeError, ValueError):
                speed_txt = fmt_num(speed)
        if p.get("DefensePenetration") is not None:
            line = defense_penetration_attack_line_html(p.get("DefensePenetration"))
            if line:
                other.append(line)
        if (p.get("MaxHitsPerEntity") or 0) > 1:
            other.append(f"Multi-hit {fmt_num(p.get('MaxHitsPerEntity'))}")
        if p.get("Pierces"):
            other.append("Pierces")
        status_txt = _format_status_effects(
            p.get("StatusEffects"), status_effect_icons, status_effect_name_to_path
        )
        other_txt = "<br>".join(other)
        dmg_plain = fmt_range(dmg.get("Min"), dmg.get("Max"))
        has_image = has_image or bool(str(pw).strip())
        has_damage = has_damage or bool(str(dmg_plain).strip())
        has_range = has_range or bool(str(range_txt).strip())
        has_speed = has_speed or bool(str(speed_txt).strip())
        has_status = has_status or bool(str(status_txt).strip())
        has_other = has_other or bool(str(other_txt).strip())
        attack_rows.append({
            "image": f'<div style="text-align:center">{pw}</div>',
            "damage": f"'''{dmg_plain}'''" if dmg_plain else "",
            "range": range_txt,
            "speed": speed_txt,
            "status": status_txt,
            "other": other_txt,
        })

    show: dict[str, bool] = {
        "image": has_image,
        "damage": has_damage,
        "range": has_range,
        "speed": has_speed,
        "status": has_status,
        "other": has_other,
    }
    if not any(show.values()):
        show = {k: True for k, _ in _ATTACK_TABLE_COLS}

    active_cols = [key for key, _ in _ATTACK_TABLE_COLS if show[key]]

    lines: list[str] = [
        "<h2>Attacks</h2>",
        '<table class="wikitable" style="text-align:center;">',
    ]
    hdr_cells = "".join(
        f"<th>{hdr}</th>" for key, hdr in _ATTACK_TABLE_COLS if show[key]
    )
    lines.append(f"<tr>{hdr_cells}</tr>")
    for row in attack_rows:
        cells = "".join(
            f"<td>{row[key]}</td>" for key, _ in _ATTACK_TABLE_COLS if show[key]
        )
        lines.append(f"<tr>{cells}</tr>")
    lines.append("</table>")
    return "\n".join(lines)


def _stat_icon(name: str, stat_icons: dict[str, str] | None) -> str:
    if not stat_icons:
        return ""
    return stat_icons.get(name.lower(), "")


# Game data may still send Intensity for these; it is not used in-game — show duration only in the wiki.
_STATUS_EFFECTS_OMIT_INTENSITY = frozenset({
    "INVULNERABLE",
    "ARMOR_BROKEN",
    "SLOWED",
    "ARMORED",
    "SICK",
    "PARALYZE",
    "QUIET",
    "STUNNED",
})


def _status_effect_name_key(name: object) -> str:
    return str(name).strip().upper().replace(" ", "_")


def _status_icon(name: str, icon_map: dict[str, str] | None) -> str:
    if not icon_map:
        return ""
    return icon_map.get(name.lower(), "")


def _status_effect_wikilink(display_name: str, name_to_path: dict[str, str] | None) -> str:
    path = (name_to_path or {}).get(str(display_name).strip().lower())
    if path:
        return f"[[{path}|{display_name}]]"
    return str(display_name)


def _format_immunities(
    raw: object,
    icon_map: dict[str, str] | None,
    name_to_path: dict[str, str] | None = None,
) -> str:
    """List immune status effects with icons (dump: Immunity: { \"Bleeding\": true, ... } or [])."""
    if raw is None:
        return ""
    if isinstance(raw, list):
        return ""
    if not isinstance(raw, dict):
        return ""
    names = sorted(str(k) for k, v in raw.items() if v)
    if not names:
        return ""
    parts: list[str] = []
    for n in names:
        icon = _status_icon(n, icon_map)
        link = _status_effect_wikilink(n, name_to_path)
        parts.append(f"{icon} {link}".strip())
    return "<br>".join(parts)


def _format_status_effects(
    raw: object,
    icon_map: dict[str, str] | None,
    name_to_path: dict[str, str] | None = None,
) -> str:
    if not raw:
        return ""
    if isinstance(raw, dict):
        out: list[str] = []
        for name, spec in raw.items():
            name_s = str(name)
            icon = _status_icon(name_s, icon_map)
            link = _status_effect_wikilink(name_s, name_to_path)
            if isinstance(spec, dict):
                parts = []
                omit_intensity = _status_effect_name_key(name) in _STATUS_EFFECTS_OMIT_INTENSITY
                if not omit_intensity and spec.get("Intensity") is not None:
                    parts.append(f"intensity {fmt_num(spec.get('Intensity'))}")
                if spec.get("Duration") is not None:
                    parts.append(f"duration {fmt_num(spec.get('Duration'))}s")
                if parts:
                    out.append(f"{icon} {link} ({', '.join(parts)})".strip())
                else:
                    out.append(f"{icon} {link}".strip())
            else:
                out.append(f"{icon} {link}: {spec}".strip())
        return "<br>".join(out)
    if isinstance(raw, list):
        out: list[str] = []
        for e in raw:
            if isinstance(e, dict):
                n = e.get("Name") or e.get("Type") or e.get("Effect")
                if n:
                    n = str(n)
                    icon = _status_icon(n, icon_map)
                    link = _status_effect_wikilink(n, name_to_path)
                    out.append(f"{icon} {link}".strip())
                else:
                    out.append(str(e))
            else:
                es = str(e)
                icon = _status_icon(es, icon_map)
                link = _status_effect_wikilink(es, name_to_path)
                out.append(f"{icon} {link}".strip())
        return ", ".join(out)
    return str(raw)


def _attack_image_for_projectile(site: pywikibot.Site, p: dict, version: str) -> str:
    radius = p.get("RadiusOfEffect")
    try:
        if radius is not None and float(radius) > 0:
            return _aoe_marker(p.get("Color"))
    except (TypeError, ValueError):
        pass
    ps = p.get("Sprite")
    return (
        upload_projectile_sprite(
            site,
            ps,
            version,
            max_thumb_size=90,
            logical_name=projectile_sprite_base(ps),
        )
        if ps
        else ""
    )


def _aoe_marker(color: object) -> str:
    r = g = b = 128
    if isinstance(color, dict):
        try:
            r = int(color.get("R", r))
            g = int(color.get("G", g))
            b = int(color.get("B", b))
        except (TypeError, ValueError):
            r = g = b = 128
    style = (
        "display:inline-flex;align-items:center;gap:6px;"
    )
    dot = (
        f'<span style="display:inline-block;width:18px;height:18px;'
        f'border-radius:50%;background:rgb({r},{g},{b});border:1px solid #222"></span>'
    )
    return f'<span style="{style}">{dot}<span>(AOE)</span></span>'


def _drop_icon_for_entry(
    drop: dict,
    is_boss: bool,
    drop_tier_icon_parts: dict[int, dict[str, str]] | None,
    item_name_to_id: dict[str, int],
    item_id_to_item: dict[int, dict] | None,
) -> str:
    tier = 0
    dt = drop.get("DropType")
    val = drop.get("Value")
    if dt == "Item" and isinstance(val, str):
        iid = item_name_to_id.get(val)
        if iid and item_id_to_item and iid in item_id_to_item:
            tier = int(item_id_to_item[iid].get("DropTierType") or 0)
    if drop_tier_icon_parts and tier in drop_tier_icon_parts:
        part = "chest" if is_boss else "bag"
        return drop_tier_icon_parts[tier].get(part, "")
    return ""


def _render_enemy_drop_entry(
    site: pywikibot.Site,
    drop: dict,
    version: str,
    item_name_to_id: dict[str, int],
    item_id_to_path: dict[int, str],
    item_id_to_item: dict[int, dict] | None,
) -> str:
    dt = drop.get("DropType")
    val = drop.get("Value")
    if dt == "Item" and isinstance(val, str):
        iid = item_name_to_id.get(val)
        if iid:
            path = item_id_to_path.get(iid)
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
            label = f"[[{path}|{val}]]" if path else val
            return f"{icon} {label}".strip()
        return str(val)
    if dt == "ItemGroup":
        preview = _resolve_item_group_preview_items(val, item_name_to_id, item_id_to_item)
        chunks: list[str] = []
        group_label = _item_group_label(val)
        if group_label:
            chunks.append(_item_group_category_link_wikitext(group_label))
        icons: list[str] = []
        for iid in preview[:3]:
            it = item_id_to_item[iid] if item_id_to_item and iid in item_id_to_item else None
            if not it:
                continue
            nm = str(it.get("Name") or f"Item {iid}")
            path = item_id_to_path.get(iid)
            icon = upload_sprite_if_possible(
                site,
                it.get("Sprite"),
                version,
                thumb_size=40,
                logical_name=item_sprite_base(iid, str(it.get("Name") or f"Item {iid}")),
            )
            if icon and path:
                icon = _link_image_wikitext(icon, path)
            if icon:
                icons.append(icon)
            else:
                label = f"[[{path}|{nm}]]" if path else nm
                icons.append(label)
        if icons:
            chunks.append(" ".join(icons))
        if chunks:
            return "<br>".join(chunks)
    # fallback
    return ""


def _resolve_item_group_preview_items(
    val: object,
    item_name_to_id: dict[str, int],
    item_id_to_item: dict[int, dict] | None,
) -> list[int]:
    return _resolve_item_group_item_ids(val, item_name_to_id, item_id_to_item)[:3]


def _resolve_item_group_item_ids(
    val: object,
    item_name_to_id: dict[str, int],
    item_id_to_item: dict[int, dict] | None,
) -> list[int]:
    if not item_id_to_item:
        return []
    out: list[int] = []

    def add_iid(iid: int | None) -> None:
        if iid is None:
            return
        if iid in item_id_to_item and iid not in out:
            out.append(iid)

    def match_type_tier(kind: str, tier: str) -> None:
        for iid, it in item_id_to_item.items():
            hier = [str(x) for x in (it.get("TypeHierarchy") or [])]
            if kind in hier and str(it.get("Tier") or "") == tier:
                add_iid(iid)

    if isinstance(val, str):
        add_iid(item_name_to_id.get(val))
    elif isinstance(val, list):
        if val and all(isinstance(x, str) for x in val):
            if len(val) == 1:
                add_iid(item_name_to_id.get(str(val[0])))
            elif len(val) >= 2 and str(val[1]).startswith("T"):
                match_type_tier(str(val[0]), str(val[1]))
            else:
                for x in val:
                    add_iid(item_name_to_id.get(str(x)))
        else:
            for x in val:
                out.extend(_resolve_item_group_item_ids(x, item_name_to_id, item_id_to_item))
    deduped: list[int] = []
    seen: set[int] = set()
    for iid in out:
        if iid not in seen:
            seen.add(iid)
            deduped.append(iid)
    return deduped


def _item_group_category_link_wikitext(group_name: str) -> str:
    """Bold label linking to Category:Type Tier (e.g. Primary Weapon T6) without categorizing the page."""
    g = str(group_name).strip()
    if not g:
        return ""
    if "|" in g or "\n" in g or "]]" in g:
        return f"'''{g}'''"
    return f"'''[[:Category:{g}|{g}]]'''"


def _item_group_label(val: object) -> str:
    if isinstance(val, list):
        if len(val) >= 2 and all(isinstance(x, str) for x in val):
            return " ".join(str(x) for x in val)
        parts: list[str] = []
        for x in val:
            lbl = _item_group_label(x)
            if lbl:
                parts.append(lbl)
        return " / ".join(parts[:3])
    if isinstance(val, str):
        return val
    return ""


def _link_image_wikitext(img_wiki: str, page_path: str) -> str:
    # Inject MediaWiki file-link target: [[File:...|40px|link=Page]]
    marker = "]]"
    i = img_wiki.find(marker)
    if i == -1:
        return img_wiki
    return f"{img_wiki[:i]}|link={page_path}{img_wiki[i:]}"


def _found_in_location_cell(
    site: pywikibot.Site,
    loc_name: str,
    version: str,
    location_name_to_path: dict[str, str] | None,
    location_name_to_portal: dict[str, dict] | None,
) -> str:
    link = _link_location_name(loc_name, location_name_to_path)
    portal = None
    if location_name_to_portal:
        portal = location_name_to_portal.get(loc_name)
    pimg = (
        upload_portal_preview(
            site, portal, version, logical_name=portal_preview_base(slug(loc_name))
        )
        if portal
        else ""
    )
    path = location_name_to_path.get(loc_name) if location_name_to_path else None
    if pimg and path:
        pimg = _link_image_wikitext(pimg, path)
    if pimg:
        return (
            '<span style="display:inline-flex; align-items:center; gap:8px;">'
            f"{pimg} {link}</span>"
        )
    return link


def _link_location_name(name: str, location_name_to_path: dict[str, str] | None) -> str:
    if location_name_to_path and name in location_name_to_path:
        return f"[[{location_name_to_path[name]}|{name}]]"
    return name


def _normalize_enemy_drops(
    drops: list[dict],
    item_name_to_id: dict[str, int],
    item_id_to_item: dict[int, dict] | None,
    skin_id_to_skin: dict[int, dict] | None = None,
) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for d in drops:
        entries = _normalize_enemy_drop_entries(
            d,
            item_name_to_id,
            item_id_to_item,
            skin_id_to_skin=skin_id_to_skin,
        )
        for nd in entries:
            key = str(nd.get("key") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(nd)
    return out


def _skin_metadata_entry(
    drop: dict,
    skin_id_to_skin: dict[int, dict] | None,
) -> dict | None:
    if not skin_id_to_skin:
        return None
    val = drop.get("Value")
    if str(val) != "Skin":
        return None
    md = drop.get("Metadata")
    if not isinstance(md, dict):
        return None
    try:
        sid = int(md.get("rid"))
    except (TypeError, ValueError):
        return None
    if sid not in skin_id_to_skin:
        return None
    sk = skin_id_to_skin[sid]
    name = str(sk.get("Name") or f"Skin {sid}")
    rr = int(sk.get("Rarity") or 0)
    return {
        "kind": "skin",
        "key": f"skin:{sid}",
        "name": name,
        "skin_id": sid,
        # Group with drop tier 6 (other legendaries) in loot tables, not tier 0.
        "drop_tier_type": 6,
        "tier_sort_value": max(0, 10 - rr),
        "type_label": "Skin",
    }


def _normalize_enemy_drop_entries(
    drop: dict,
    item_name_to_id: dict[str, int],
    item_id_to_item: dict[int, dict] | None,
    skin_id_to_skin: dict[int, dict] | None = None,
) -> list[dict]:
    dt = drop.get("DropType")
    val = drop.get("Value")
    out: list[dict] = []

    def item_entry_from_name(name: str) -> dict | None:
        iid = item_name_to_id.get(name)
        if not iid or not item_id_to_item or iid not in item_id_to_item:
            return None
        it = item_id_to_item[iid]
        item_name = str(it.get("Name") or name)
        tier_raw = str(it.get("Tier") or "")
        return {
            "kind": "item",
            "key": f"item:{it.get('Id') or item_name}",
            "name": item_name,
            "item_id": iid,
            "type_label": str((it.get("TypeHierarchy") or ["Item"])[0]),
            "drop_tier_type": int(it.get("DropTierType") or 0),
            "tier_sort_value": _get_tier_sort_value(tier_raw),
        }

    def group_entry_or_item(kind: str, tier_raw: str) -> dict:
        group_name = f"{kind} {tier_raw}".strip()
        matched = _resolve_item_group_item_ids([kind, tier_raw], item_name_to_id, item_id_to_item)
        if len(matched) == 1 and item_id_to_item and matched[0] in item_id_to_item:
            it = item_id_to_item[matched[0]]
            item_name = str(it.get("Name") or f"Item {matched[0]}")
            return {
                "kind": "item",
                "key": f"item:{it.get('Id') or item_name}",
                "name": item_name,
                "item_id": matched[0],
                "type_label": str((it.get("TypeHierarchy") or ["Item"])[0]),
                "drop_tier_type": int(it.get("DropTierType") or 0),
                "tier_sort_value": _get_tier_sort_value(str(it.get("Tier") or "")),
            }
        preview = matched[:3]
        drop_tier_type = 0
        if item_id_to_item:
            for iid in preview:
                it = item_id_to_item.get(iid)
                if not it:
                    continue
                drop_tier_type = max(drop_tier_type, int(it.get("DropTierType") or 0))
        return {
            "kind": "itemgroup",
            "key": f"group:{group_name}",
            "name": group_name,
            "group_kind": kind,
            "group_tier": tier_raw,
            "preview_item_ids": preview[:3],
            "type_label": "Item Group",
            "drop_tier_type": drop_tier_type,
            "tier_sort_value": _get_tier_sort_value(tier_raw),
        }

    if dt == "Item" and isinstance(val, str):
        skin_e = _skin_metadata_entry(drop, skin_id_to_skin)
        if skin_e:
            return [skin_e]
        one = item_entry_from_name(val)
        return [one] if one else []
    if dt == "ItemGroup" and isinstance(val, list):
        # Handles mixed payloads such as:
        # [["Primary Weapon","T3"],["Armor","T3"],["Speed Infusion"],["Secondary Ability","T2"]]
        for part in val:
            if isinstance(part, list):
                if len(part) >= 2 and isinstance(part[0], str) and isinstance(part[1], str) and str(part[1]).upper().startswith("T"):
                    out.append(group_entry_or_item(str(part[0]), str(part[1])))
                elif len(part) == 1 and isinstance(part[0], str):
                    one = item_entry_from_name(str(part[0]))
                    if one:
                        out.append(one)
            elif isinstance(part, str):
                one = item_entry_from_name(part)
                if one:
                    out.append(one)
        # Also support flat ["Type","T3"] format
        if not out and len(val) >= 2 and isinstance(val[0], str) and isinstance(val[1], str) and str(val[1]).upper().startswith("T"):
            out.append(group_entry_or_item(str(val[0]), str(val[1])))
        return out
    return []


def _get_tier_sort_value(tier: str) -> int:
    t = str(tier or "").strip().upper()
    if t.startswith("T"):
        num = t[1:]
        if num.isdigit():
            return int(num)
    return 0


def _render_normalized_enemy_drop_entry(
    site: pywikibot.Site,
    nd: dict,
    version: str,
    item_id_to_path: dict[int, str],
    item_id_to_item: dict[int, dict] | None,
    skin_id_to_skin: dict[int, dict] | None = None,
    skin_id_to_path: dict[int, str] | None = None,
    skin_rarity_icon_wikitext: dict[int, str] | None = None,
) -> str:
    kind = nd.get("kind")
    if kind == "skin":
        sid = nd.get("skin_id")
        if sid is None or not skin_id_to_skin or not skin_id_to_path:
            return ""
        return format_skin_drop_cell(
            site,
            version,
            int(sid),
            skin_id_to_skin,
            skin_id_to_path,
            skin_rarity_icon_wikitext or {},
        )
    if kind == "item":
        iid = nd.get("item_id")
        if iid is None:
            return ""
        it = item_id_to_item.get(iid) if item_id_to_item else None
        name = str(nd.get("name") or (it.get("Name") if it else f"Item {iid}"))
        path = item_id_to_path.get(iid)
        icon = ""
        if it:
            icon = _render_drop_item_icon_with_tier(site, it, version, path)
        label = f"[[{path}|{name}]]" if path else name
        return f"{icon} {label}".strip()
    if kind == "itemgroup":
        chunks: list[str] = []
        nm = str(nd.get("name") or "")
        if nm:
            chunks.append(_item_group_category_link_wikitext(nm))
        icons: list[str] = []
        for iid in nd.get("preview_item_ids") or []:
            it = item_id_to_item[iid] if item_id_to_item and iid in item_id_to_item else None
            if not it:
                continue
            item_name = str(it.get("Name") or f"Item {iid}")
            path = item_id_to_path.get(iid)
            icon = _render_drop_item_icon_with_tier(site, it, version, path)
            if icon:
                icons.append(icon)
            else:
                icons.append(f"[[{path}|{item_name}]]" if path else item_name)
        if icons:
            chunks.append(" ".join(icons))
        return "<br>".join(chunks)
    return ""


def _render_drop_item_icon_with_tier(
    site: pywikibot.Site,
    item: dict,
    version: str,
    page_path: str | None,
) -> str:
    iid = int(item.get("Id") or 0)
    base_icon = upload_sprite_if_possible(
        site,
        item.get("Sprite"),
        version,
        thumb_size=40,
        logical_name=item_sprite_base(iid, str(item.get("Name") or f"Item {iid}")),
    )
    if not base_icon:
        return ""
    if page_path:
        base_icon = _link_image_wikitext(base_icon, page_path)
    tier_icon = ""
    if item.get("TierIcon"):
        tier_icon = upload_sprite_if_possible(
            site,
            item.get("TierIcon"),
            version,
            thumb_size=16,
            logical_name=tier_icon_filename_base(item["TierIcon"]),
        )
        if tier_icon and page_path:
            tier_icon = _link_image_wikitext(tier_icon, page_path)
    if not tier_icon:
        return base_icon
    return (
        '<span style="display:inline-block;position:relative;line-height:0;">'
        f"{base_icon}"
        '<span style="position:absolute;right:-2px;bottom:-2px;pointer-events:none;">'
        f"{tier_icon}"
        "</span></span>"
    )
