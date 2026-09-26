"""Drafts Email / WhatsApp / LinkedIn / Messenger outreach from a lead + its audit.

Rules baked in (per Israr's standing instructions):
  - Never mentions past clients' names, URLs, or brands.
  - Leads with the prospect's actual pain points, not a generic pitch.
  - Ends with a subtle competitive-pressure / more-leads-and-sales hint, not a hard sell.

If a GEMINI_API_KEY is set, uses Gemini (free tier) to vary the phrasing while keeping
the same facts and rules; otherwise falls back to the plain templates below, which
always work with no extra setup.
"""
from __future__ import annotations
import re

import requests


def _domain(website: str) -> str:
    return re.sub(r"^https?://", "", website, flags=re.I).replace("www.", "", 1).split("/")[0]


def _join_natural(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return items[0] + " and " + items[1]
    return ", ".join(items[:-1]) + ", and " + items[-1]


def build_drafts(business_name: str, website: str, pain_points: list[str], cfg) -> dict:
    domain = _domain(website)
    pain_clause = _join_natural(pain_points) if pain_points else \
        "no major tracking gaps — the core setup actually looks solid"
    competitive_line = ("Right now, competitors who have this covered are likely picking up "
                         "leads and sales that could be landing with you instead.")

    email_subject = f"A quick observation about {domain}"
    email_body = (
        f"Hi [Name],\n\n"
        f"I ran a quick technical check on {domain} and noticed {pain_clause}.\n\n"
        f"For a business like {business_name}, that usually means missed leads and no clear way "
        f"to measure what's actually working from your marketing. {competitive_line}\n\n"
        f"I specialize in fixing exactly this — Google Ads, Meta Ads, tracking setup "
        f"(GA4/GTM/Pixel), and reporting so you can see real numbers instead of guessing.\n\n"
        f"Worth a quick 15-minute call to walk through what I found?\n\n"
        f"Best,\n{cfg.sender_name}\n{cfg.sender_title}\n"
        f"{cfg.sender_email} | {cfg.sender_phone} | {cfg.sender_website}"
    )
    whatsapp = (f"Hi, this is {cfg.sender_name.split(' ')[0]} — I checked {domain} and noticed "
                f"{pain_clause}. That usually means missed leads and no way to measure what's "
                f"working. Worth a quick chat?")
    linkedin = (f"Hi [Name], I was looking at {domain} and noticed {pain_clause}. I work with "
                f"businesses on exactly this (ads + tracking + reporting) — happy to share what "
                f"I found if useful, no pitch attached.")
    messenger = (f"Hi! I checked {domain} and noticed {pain_clause}. I help local businesses fix "
                 f"exactly this — happy to share a couple of quick pointers if that's useful.")

    drafts = {"email_subject": email_subject, "email_body": email_body,
              "whatsapp": whatsapp, "linkedin": linkedin, "messenger": messenger}

    if cfg.gemini_api_key:
        upgraded = _try_gemini_rewrite(business_name, domain, pain_points, cfg, drafts)
        if upgraded:
            return upgraded
    return drafts


def _try_gemini_rewrite(business_name: str, domain: str, pain_points: list[str], cfg, fallback: dict) -> dict | None:
    """Best-effort: ask Gemini to rewrite the same facts more naturally. On ANY failure
    (bad key, rate limit, malformed response) we silently keep the template version —
    outreach must never go out blank or broken because of an API hiccup."""
    prompt = (
        f"Rewrite these 4 cold-outreach messages to be more natural and varied in phrasing, "
        f"WITHOUT changing any facts, WITHOUT adding claims not present, WITHOUT mentioning any "
        f"company name other than '{business_name}' and '{cfg.sender_name}', WITHOUT adding links, "
        f"and keeping the same rough length and structure (email has a subject + body, the other "
        f"three are one short paragraph each). Prospect's site: {domain}. "
        f"Issues found: {', '.join(pain_points) if pain_points else 'none — tracking looks solid'}.\n\n"
        f"Return ONLY valid JSON with keys email_subject, email_body, whatsapp, linkedin, messenger.\n\n"
        f"Original versions:\n{fallback}"
    )
    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent",
            headers={"x-goog-api-key": cfg.gemini_api_key, "Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"responseMimeType": "application/json"}},
            timeout=30,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        import json
        parsed = json.loads(text)
        required = {"email_subject", "email_body", "whatsapp", "linkedin", "messenger"}
        if not required.issubset(parsed.keys()):
            return None
        if any("http" in str(parsed[k]).lower() for k in required):
            return None  # never trust AI output containing links in cold outreach
        return {k: str(parsed[k]).strip() for k in required}
    except Exception:
        return None
