from __future__ import annotations

import pywikibot


def _canonical_username(x: object) -> str:
    """Normalize for comparison; Pywikibot may return str or User-like objects."""
    if x is None:
        return ""
    s = str(x).strip()
    return s


def _last_editors_match(bot_user: str, page: pywikibot.Page) -> bool:
    """True if the latest revision on the page is by the bot account."""
    b = _canonical_username(bot_user).lower()
    if not b:
        return False
    last = ""
    try:
        page.get()
    except Exception:
        pass
    try:
        rev = page.latest_revision
        u = getattr(rev, "user", None)
        if u is None and hasattr(rev, "__getitem__"):
            try:
                u = rev["user"]
            except Exception:
                u = None
        if u is not None:
            last = _canonical_username(u).lower()
    except Exception:
        pass
    if not last:
        try:
            last = _canonical_username(page.userName).lower()
        except Exception:
            return False
    return last == b


def peek_skip_build_reason(
    site: pywikibot.Site,
    title: str,
    bot_user: str,
    force_overwrite: bool,
) -> str | None:
    """
    If this returns non-None, save_bot_page would skip without needing built wikitext
    (human-owned page, or __NOPQBOT__). Skips expensive sprite uploads during import.
    """
    if force_overwrite:
        return None
    page = pywikibot.Page(site, title)
    if not page.exists():
        return None
    try:
        text = page.text
    except Exception:
        return None
    if "__NOPQBOT__" in text:
        return "skipped_nopqbot"
    try:
        if not _last_editors_match(bot_user, page):
            return "skipped_human"
    except Exception:
        return None
    return None


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
        if not force_overwrite and not _last_editors_match(bot_user, page):
            return "skipped_human"
        if (not force_overwrite) and page.text.strip() == text.strip():
            return "unchanged"
    summary = f"PQ bot datadump {version} ({kind})"
    page.text = text
    page.save(summary=summary, minor=False)
    return "saved"
