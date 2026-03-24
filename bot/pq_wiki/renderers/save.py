from __future__ import annotations

import pywikibot


def save_bot_page(
    site: pywikibot.Site,
    title: str,
    text: str,
    version: str,
    bot_user: str,
    kind: str,
    force_overwrite: bool = False,
) -> str:
    page = pywikibot.Page(site, title)
    if page.exists():
        if "__NOPQBOT__" in page.text:
            return "skipped_nopqbot"
        if not force_overwrite and page.userName != bot_user:
            return "skipped_human"
        if (not force_overwrite) and page.text.strip() == text.strip():
            return "unchanged"
    summary = f"PQ bot datadump {version} ({kind})"
    page.text = text
    page.save(summary=summary, minor=False)
    return "saved"
