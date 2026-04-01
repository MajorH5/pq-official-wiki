from __future__ import annotations

import os
from contextvars import ContextVar

import pywikibot

from pq_wiki.import_log import get_import_logger

# Per-run override (e.g. CLI --edit-summary, ingest ?edit_summary=); thread-safe for ingest workers.
_edit_summary_ctx: ContextVar[str | None] = ContextVar("pq_edit_summary", default=None)

# Human adds this to wikitext to allow the next import to overwrite even when the latest
# revision is not by the bot. Bot output does not include it (one-shot per run unless re-added).
# __NOPQBOT__ still blocks saves if both appear.
ALLOW_PQ_BOT_OVERWRITE_MAGIC = "__PQBOT_OVERWRITE__"


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

    Human-touched pages are skipped unless the page contains ``__PQBOT_OVERWRITE__``
    (opt-in for the next bot save). ``__NOPQBOT__`` always wins over that tag.
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
            if ALLOW_PQ_BOT_OVERWRITE_MAGIC not in text:
                return "skipped_human"
    except Exception:
        return None
    return None


def _norm_wikitext(s: str) -> str:
    """Compare like MediaWiki storage: normalize newlines and trim ends."""
    return s.replace("\r\n", "\n").replace("\r", "\n").strip()


def _verbose_save_logs() -> bool:
    return os.environ.get("PQ_IMPORT_VERBOSE_SAVE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def push_edit_summary_override(template: str | None):
    """
    Per-import edit summary template. None = clear override (use env / default).
    Returns a token for reset_edit_summary_override.
    """
    return _edit_summary_ctx.set(template)


def reset_edit_summary_override(token) -> None:
    _edit_summary_ctx.reset(token)


def resolve_edit_summary(version: str, kind: str) -> str:
    """
    Wiki revision summary for bot saves.

    - If a per-run override was set (push_edit_summary_override), use it.
    - Else if PQ_EDIT_SUMMARY is set, use it.
    - Else default: PQ bot datadump {version} ({kind})

    Placeholders in the template: {version}, {kind}
    """
    ctx = _edit_summary_ctx.get()
    if ctx is not None:
        raw = ctx
    else:
        raw = os.environ.get("PQ_EDIT_SUMMARY", "").strip()
    if not raw:
        return f"PQ bot datadump {version} ({kind})"
    return raw.replace("{version}", str(version)).replace("{kind}", str(kind))


def save_bot_page(
    site: pywikibot.Site,
    title: str,
    text: str,
    version: str,
    bot_user: str,
    kind: str,
    force_overwrite: bool = False,
) -> str:
    log = get_import_logger()
    page = pywikibot.Page(site, title)
    old_rev: int | None = None
    old_len: int | None = None
    if page.exists():
        try:
            page.get()
            old_len = len(page.text)
            old_rev = page.latest_revision_id
        except Exception:
            pass
        if "__NOPQBOT__" in page.text:
            return "skipped_nopqbot"
        if (
            not force_overwrite
            and not _last_editors_match(bot_user, page)
            and ALLOW_PQ_BOT_OVERWRITE_MAGIC not in page.text
        ):
            return "skipped_human"
        if (not force_overwrite) and _norm_wikitext(page.text) == _norm_wikitext(text):
            log.debug(
                "wiki_save unchanged title=%r bytes=%s rev=%s",
                title,
                old_len,
                old_rev,
            )
            return "unchanged"
    summary = resolve_edit_summary(version, kind)
    page.text = text
    page.save(summary=summary, minor=False)
    new_rev: int | None = None
    try:
        page.get(force=True)
        new_rev = page.latest_revision_id
    except Exception as e:
        log.warning("wiki_save could not refresh page after save title=%r: %s", title, e)
    new_len = len(text)
    line = (
        "wiki_save title=%r kind=%s old_rev=%s new_rev=%s old_bytes=%s new_bytes=%s"
        % (title, kind, old_rev, new_rev, old_len, new_len)
    )
    if _verbose_save_logs():
        log.info(line)
    else:
        log.debug(line)
    # Same revision + same byte length => MediaWiki treated this as a no-op (nothing actually
    # changed vs current revision). Not an error. Warn only if we expected different content.
    if old_rev is not None and new_rev is not None and new_rev == old_rev:
        if old_len != new_len:
            log.warning(
                "wiki_save revision id did not advance despite different size: %r "
                "(old_bytes=%s new_bytes=%s)",
                title,
                old_len,
                new_len,
            )
        else:
            log.debug(
                "wiki_save no new revision (wikitext matches current revision after save): %r",
                title,
            )
    return "saved"
