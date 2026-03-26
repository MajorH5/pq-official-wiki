from __future__ import annotations

from pq_wiki.wikitext_util import html_to_wikitext, wikitable


def build_account_stat_wikitext(account_stat: dict, version: str) -> str:
    sid = int(account_stat.get("Id") or 0)
    name = str(account_stat.get("Name") or f"Account Stat {sid}")
    category = str(account_stat.get("Category") or "").strip()
    tracking = str(account_stat.get("TrackingStartVersion") or "").strip()
    description = html_to_wikitext(str(account_stat.get("Description") or "")).strip()

    info_rows: list[tuple[str, str]] = [
        ("Name", name),
        ("Category", category or "—"),
        ("Tracking start version", tracking or "—"),
        ("Description", description or "—"),
    ]
    body = "\n".join(
        [
            wikitable(info_rows),
            "",
            "[[Category:Account Stats]]",
        ]
    )
    return f"<!-- PQ bot generated {version} — do not remove -->\n{body}"

