"""WikiSEO {{#seo:}} helpers — og/twitter previews (Discord, X, etc.)."""

from __future__ import annotations

import re

import pywikibot


def first_wiki_filename_from_file_wikitext(wikitext: str) -> str | None:
    """Extract first ``File:`` name from ``[[File:Name|...]]`` fragments."""
    if not wikitext:
        return None
    m = re.search(r"\[\[File:([^|]+)\|", wikitext)
    if not m:
        return None
    return m.group(1).strip()


def _site_server_url(site: pywikibot.Site) -> str:
    try:
        s = site.siteinfo("server") or ""
    except Exception:
        s = ""
    return str(s).rstrip("/")


def public_url_for_wiki_image(site: pywikibot.Site, wiki_filename: str | None) -> str | None:
    """Direct URL to an uploaded file (for ``og:image``). Returns None if missing."""
    if not wiki_filename:
        return None
    try:
        fp = pywikibot.FilePage(site, f"File:{wiki_filename}")
        if fp.exists():
            return fp.get_file_url()
    except Exception:
        pass
    return None


def default_preview_image_url(site: pywikibot.Site) -> str:
    """Static ``/images/default-preview.png`` under the wiki server URL."""
    return f"{_site_server_url(site)}/images/default-preview.png"


def _wiki_sitename(site: pywikibot.Site) -> str:
    try:
        s = site.siteinfo("sitename")
        if s:
            return str(s).strip()
    except Exception:
        pass
    return "Pixel Quest Wiki"


def plain_text_for_seo(s: str) -> str:
    """Strip simple wikitext noise for meta descriptions."""
    t = re.sub(r"''+", "", s or "")
    return re.sub(r"\s+", " ", t).strip()


def _seo_safe_value(s: str, max_len: int) -> str:
    """One line; strip chars that break parser-function params."""
    s = re.sub(r"\s+", " ", (s or "").strip())
    s = s.replace("|", " ")
    s = s.replace("=", " ")
    s = s.replace("{", " ")
    s = s.replace("}", " ")
    if len(s) > max_len:
        s = s[: max_len - 1].rstrip() + "…"
    return s


def wiki_seo_block(
    site: pywikibot.Site,
    *,
    page_title: str,
    description: str,
    wiki_image_filename: str | None,
    image_alt: str,
) -> str:
    """
    Appended at the **bottom** of bot-generated wikitext.
    Uses full image URL (uploaded file or ``default-preview.png``).

    Browser title: ``{page title} - {sitename}``. ``title_mode=replace`` avoids WikiSEO
    ``append`` duplicating the article name (e.g. ``Foo - Foo``).
    """
    base_title = _seo_safe_value(page_title, 120)
    sitename = _wiki_sitename(site)
    full_title = _seo_safe_value(f"{page_title} - {sitename}", 200)
    desc = _seo_safe_value(description, 300)
    if not desc:
        desc = "Pixel Quest Wiki"
    alt = _seo_safe_value(image_alt, 200)
    if not alt:
        alt = base_title or "Pixel Quest Wiki"

    img_url = public_url_for_wiki_image(site, wiki_image_filename) or default_preview_image_url(site)

    # One block; newlines are fine inside {{#seo:}} for readability.
    return (
        "{{#seo:\n"
        f" |title={full_title}\n"
        " |title_mode=replace\n"
        f" |description={desc}\n"
        f" |image={img_url}\n"
        f" |image_alt={alt}\n"
        " |twitter_card=summary_large_image\n"
        "}}"
    )
