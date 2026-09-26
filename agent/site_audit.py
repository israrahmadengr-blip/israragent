"""Fetches a prospect's homepage (politely) and checks for:
  - Google Ads conversion tag, Meta Pixel, GA4, Google Tag Manager, HTTPS
    (the same checks as the israrads Prospect Audit Tool)
  - a contact email (mailto: links, or a plain email address on the page)
  - whether the site's robots.txt blocks the major AI answer-engine crawlers
    (GPTBot, ClaudeBot, PerplexityBot, Google-Extended) — increasingly a real
    visibility gap as more people search via ChatGPT/Perplexity/AI Overviews
    instead of classic Google search.

Every check that can't be verified is reported as "Unknown", never guessed.
"""
from __future__ import annotations
import re
import urllib.robotparser
from urllib.parse import urlparse

import requests

UA = "Mozilla/5.0 (compatible; israrads-agent/1.0; +https://israrads.com)"

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
FREE_MAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "live.com"}
JUNK_LOCAL_PARTS = {"noreply", "no-reply", "donotreply", "webmaster", "postmaster", "abuse"}

AI_BOTS = ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended"]


def _clean_email(addr: str) -> str:
    addr = addr.strip().strip(".,;:<>()[]\"'").lower()
    if not EMAIL_RE.fullmatch(addr):
        return ""
    local, _, domain = addr.rpartition("@")
    if domain in FREE_MAIL_DOMAINS or local in JUNK_LOCAL_PARTS:
        return ""  # not necessarily wrong, just not a great cold-outreach contact
    return addr


def _extract_email(html: str) -> str:
    mailtos = re.findall(r'href=["\']mailto:([^"\'?]+)', html, re.I)
    for m in mailtos:
        ce = _clean_email(m)
        if ce:
            return ce
    for m in EMAIL_RE.findall(html):
        ce = _clean_email(m)
        if ce:
            return ce
    return ""


def _check_ai_crawlers_blocked(base_url: str, timeout: int) -> str:
    """Returns 'Yes' if any major AI crawler is explicitly disallowed, 'No' if none are,
    'Unknown' if robots.txt couldn't be read."""
    try:
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        resp = requests.get(robots_url, timeout=timeout, headers={"User-Agent": UA})
        if resp.status_code != 200:
            return "Unknown"
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(resp.text.splitlines())
        for bot in AI_BOTS:
            if not rp.can_fetch(bot, base_url):
                return "Yes"
        return "No"
    except requests.RequestException:
        return "Unknown"


def audit(website: str, timeout: int = 12) -> dict:
    result = {
        "fetched": False, "https": website.lower().startswith("https://"),
        "ga4": "Unknown", "gtm": "Unknown", "meta_pixel": "Unknown", "google_ads_tag": "Unknown",
        "ai_crawlers_blocked": "Unknown", "email": "",
    }
    try:
        resp = requests.get(website, timeout=timeout, headers={"User-Agent": UA}, allow_redirects=True)
        if resp.status_code >= 400:
            return result
        html = resp.text
        result["fetched"] = True
        result["https"] = resp.url.lower().startswith("https://")
        result["ga4"] = "Yes" if re.search(r"\bG-[A-Z0-9]{6,10}\b", html) else "No"
        result["gtm"] = "Yes" if re.search(r"GTM-[A-Z0-9]{4,}", html) else "No"
        result["meta_pixel"] = "Yes" if (re.search(r"fbq\(\s*['\"]init['\"]", html)
                                          or "connect.facebook.net" in html) else "No"
        result["google_ads_tag"] = "Yes" if (re.search(r"AW-\d{9,12}", html)
                                              or "googleadservices.com/pagead/conversion" in html) else "No"
        result["email"] = _extract_email(html)
        result["ai_crawlers_blocked"] = _check_ai_crawlers_blocked(resp.url, timeout)
    except requests.RequestException:
        pass  # site blocked the request or timed out — leave everything "Unknown"
    return result


def pain_points(audit_result: dict) -> list[str]:
    if not audit_result["fetched"]:
        return ["site could not be automatically checked — verify tracking manually"]
    points = []
    if audit_result["google_ads_tag"] == "No":
        points.append("no Google Ads conversion tracking")
    if audit_result["meta_pixel"] == "No":
        points.append("no Meta Pixel")
    if audit_result["ga4"] == "No":
        points.append("no GA4 analytics")
    if audit_result["gtm"] == "No":
        points.append("no Google Tag Manager")
    if not audit_result["https"]:
        points.append("no HTTPS")
    if audit_result["ai_crawlers_blocked"] == "Yes":
        points.append("the site is blocking AI search crawlers like ChatGPT and Perplexity from indexing it")
    return points
