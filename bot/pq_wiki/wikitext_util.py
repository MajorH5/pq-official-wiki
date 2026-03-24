from __future__ import annotations

import re
from typing import Any, Optional


def slugify(s: Optional[str], fallback: str = "unnamed") -> str:
    """Convert to URL-safe slug. Handles ???, empty, and special chars."""
    if s is None or not isinstance(s, str):
        return fallback
    t = s.strip()
    if not t:
        return fallback
    # Treat ??? and similar placeholders
    if re.match(r"^[\?\s\-_\.]+$", t) or t == "???":
        return "unknown"
    # Lowercase, replace spaces/special with hyphen
    t = t.lower()
    t = re.sub(r"[^\w\s\-]", "", t)
    t = re.sub(r"[\s_]+", "-", t)
    t = re.sub(r"-+", "-", t).strip("-")
    return t or fallback


def title_case_slug(slug: str) -> str:
    """Title-case each hyphen segment: ``travelers-sword`` → ``Travelers-Sword``."""
    if not slug:
        return slug
    return "-".join(p.capitalize() for p in slug.split("-"))


def page_title_slug(name: Optional[str], fallback: str) -> str:
    """Normalized slug for wiki page titles (sentence/title case segments)."""
    return title_case_slug(slugify(name, fallback=fallback))


def html_to_wikitext(s: Optional[str]) -> str:
    if not s:
        return ""
    t = s
    t = re.sub(r"<b>(.*?)</b>", r"'''\1'''", t, flags=re.I | re.DOTALL)
    t = re.sub(r"<i>(.*?)</i>", r"''\1''", t, flags=re.I | re.DOTALL)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    return t.strip()


def fmt_num(n: Any) -> str:
    if n is None:
        return ""
    if isinstance(n, float):
        if abs(n - round(n)) < 1e-9:
            return str(int(round(n)))
        s = f"{n:.4f}".rstrip("0").rstrip(".")
        return s
    return str(n)


_DEF_PEN_STYLE = "color:#e85d04;font-weight:bold"


def defense_penetration_display_html(raw: Any) -> str:
    """
    Orange bold value for tables. Dump uses 0–1 fractions (0.4 → 40%).
    Values > 1 are treated as whole percent (e.g. 40 → 40%).
    """
    if raw is None:
        return ""
    try:
        dp = float(raw)
    except (TypeError, ValueError):
        return ""
    if dp <= 0:
        return ""
    if abs(dp - 1.0) < 1e-9:
        inner = "Ignores Defense"
    elif dp <= 1.0:
        inner = f"{fmt_num(dp * 100.0)}%"
    else:
        inner = f"{fmt_num(dp)}%"
    return f'<span style="{_DEF_PEN_STYLE}">{inner}</span>'


def defense_penetration_attack_line_html(raw: Any) -> str:
    """Enemy attacks Other column: Ignores Defense or Def-Pen N%, orange bold."""
    if raw is None:
        return ""
    try:
        dp = float(raw)
    except (TypeError, ValueError):
        return ""
    if dp <= 0:
        return ""
    if abs(dp - 1.0) < 1e-9:
        inner = "Ignores Defense"
    elif dp <= 1.0:
        inner = f"Def-Pen {fmt_num(dp * 100.0)}%"
    else:
        inner = f"Def-Pen {fmt_num(dp)}%"
    return f'<span style="{_DEF_PEN_STYLE}">{inner}</span>'


def stat_boosts_as_dict(obj: Any) -> dict:
    if isinstance(obj, dict):
        return obj
    return {}


def type_hierarchy_links(hierarchy: list) -> str:
    if not hierarchy:
        return ""
    parts = [p for p in reversed(hierarchy) if p and p != "Item"]
    if not parts:
        return ""
    # Link to category pages without categorizing current page.
    linked = [f"[[:Category:{p}|{p}]]" for p in parts]
    return " &gt; ".join(linked)


def wikitable(rows: list[tuple[str, str]]) -> str:
    lines = ['{| class="wikitable"']
    for k, v in rows:
        lines.append("|-")
        lines.append(f"! {k}")
        lines.append(f"| {v}")
    lines.append("|}")
    return "\n".join(lines)


def escape_template_param_value(s: str) -> str:
    """Escape | and = for named template parameters ({{PQ Item|information=...}}).

    - ``|`` → ``{{!}}`` so table pipes do not end the parameter.
    - ``=`` → ``{{=}}`` so HTML attrs (href=, class=, …) are not parsed as new params.
    """
    s = s.replace("|", "{{!}}")
    return s.replace("=", "{{=}}")


def template_invocation(
    template_name: str,
    ordered_params: list[tuple[str, str]],
    omit_empty: bool = True,
    always_emit_keys: frozenset[str] | None = None,
) -> str:
    """
    Build {{TemplateName|a=...|b=...}} with pipe-safe values.
    ordered_params preserves key order; omit_empty skips keys whose value is empty.
    Keys in always_emit_keys are still emitted when empty (keeps named-arg alignment).
    """
    parts: list[str] = [f"{{{{{template_name}"]
    always = always_emit_keys or frozenset()
    for key, val in ordered_params:
        if omit_empty and not val and key not in always:
            continue
        # Values starting with "=" break {{...|name== section ==}} — parser eats "=" as part of name.
        if val and val.lstrip().startswith("="):
            val = "\n" + val
        parts.append(f"|{key}={escape_template_param_value(val)}")
    parts.append("}}")
    return "\n".join(parts)
