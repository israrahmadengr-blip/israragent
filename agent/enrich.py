"""Finds the DECISION-MAKER behind a candidate business, from the business's
own public pages only (About / Team / Contact + footer links). Free, no APIs.

Returns {contact_name, contact_role, email, email_confidence, linkedin} where
email_confidence is:
  "found"          — a person's email published on the site
  "pattern-guessed"— built from a found name + domain (first@ / first.last@)
  "generic"        — only a business inbox (info@, sales@...) was found
  ""               — nothing usable
Pattern-guessed is LABELLED, never presented as verified (Israr's standing rule).
"""
from __future__ import annotations
import re
from urllib.parse import urljoin, urlparse

import requests

from .site_audit import UA, _clean_email, EMAIL_RE

ROLE_RE = re.compile(
    r"(founder|co-founder|owner|ceo|director|principal|managing director)", re.I)
NAME_NEAR_ROLE = re.compile(
    r"([A-Z][a-z]+\s[A-Z][a-z]+)\s*[—\-|,•·]\s*(Founder|Co-Founder|CEO|Owner|Director|Principal)")
ROLE_NEAR_NAME = re.compile(
    r"(Founder|Co-Founder|CEO|Owner|Director|Principal)\s*[:\-—|]\s*([A-Z][a-z]+\s[A-Z][a-z]+)")
BAD_FIRST_WORDS = {"Our", "The", "Meet", "About", "Welcome", "Story", "Team"}
PAGES = ("/about", "/about-us", "/our-story", "/team", "/contact", "/contact-us")


def _fetch(url: str, timeout: int) -> str:
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": UA}, allow_redirects=True)
        return r.text if r.status_code == 200 else ""
    except requests.RequestException:
        return ""


def _find_name(html: str) -> tuple[str, str]:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    for rx in (NAME_NEAR_ROLE, ROLE_NEAR_NAME):
        m = rx.search(text)
        if m:
            name = m.group(1) if rx is NAME_NEAR_ROLE else m.group(2)
            role = m.group(2) if rx is NAME_NEAR_ROLE else m.group(1)
            if name.split()[0] not in BAD_FIRST_WORDS:
                return name.strip(), role.title()
    return "", ""


def _find_linkedin(html: str) -> str:
    m = re.search(r'href="(https?://(?:www\.)?linkedin\.com/(?:company|in)/[^"]+)"', html, re.I)
    return m.group(1) if m else ""


def _person_email(html: str, domain: str) -> str:
    for raw in EMAIL_RE.findall(html):
        ce = _clean_email(raw)
        if ce and ce.endswith("@" + domain):
            local = ce.split("@")[0]
            if local not in ("info", "sales", "support", "hello", "contact", "admin",
                             "orders", "team", "office", "enquiries", "inquiries"):
                return ce
    return ""


def enrich(website: str, site_email: str, timeout: int = 12) -> dict:
    domain = urlparse(website).netloc.lower()
    domain = domain[4:] if domain.startswith("www.") else domain
    out = {"contact_name": "", "contact_role": "", "email": site_email or "",
           "email_confidence": "generic" if site_email else "", "linkedin": ""}
    for page in PAGES:
        html = _fetch(urljoin(website.rstrip("/") + "/", page.lstrip("/")), timeout)
        if not html:
            continue
        if not out["linkedin"]:
            out["linkedin"] = _find_linkedin(html)
        pe = _person_email(html, domain)
        if pe:
            out["email"], out["email_confidence"] = pe, "found"
        if not out["contact_name"]:
            name, role = _find_name(html)
            if name:
                out["contact_name"], out["contact_role"] = name, role
        if out["contact_name"] and out["email_confidence"] == "found":
            break
    if out["contact_name"] and out["email_confidence"] != "found":
        first = out["contact_name"].split()[0].lower()
        parts = out["contact_name"].lower().split()
        guess = f"{first}@{domain}" if len(parts) < 2 else f"{parts[0]}.{parts[-1]}@{domain}"
        out["email"], out["email_confidence"] = guess, "pattern-guessed"
    return out
