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

from . import intel as intel_mod


def _domain(website: str) -> str:
    return re.sub(r"^https?://", "", website, flags=re.I).replace("www.", "", 1).split("/")[0]


def _join_natural(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return items[0] + " and " + items[1]
    return ", ".join(items[:-1]) + ", and " + items[-1]


def build_drafts(business_name: str, website: str, pain_points: list[str], cfg,
                 contact_name: str = "", intel: dict | None = None) -> dict:
    domain = _domain(website)
    greeting = f"Hi {contact_name.split(' ')[0]}," if contact_name else "Hi there,"
    pain_clause = _join_natural(pain_points) if pain_points else \
        "no major tracking gaps — the core setup actually looks solid"
    competitive_line = ("Right now, competitors who have this covered are likely picking up "
                         "leads and sales that could be landing with you instead.")

    # Intel layer (v3): when the intel engine found a top pain point, the
    # drafts open with its evidence-based hook — one specific observation,
    # never the generic multi-gap list. Fallback keeps the classic opener.
    hook = ""
    if intel and intel.get("top_pain"):
        hook = intel_mod.hook_for(intel["top_pain"], business_name)
    opener = hook if hook else \
        f"I ran a quick technical check on {domain} and noticed {pain_clause}."

    email_subject = f"A quick observation about {domain}"
    email_body = (
        f"{greeting}\n\n"
        f"{opener}\n\n"
        f"For a business like {business_name}, that usually means missed leads and no clear way "
        f"to measure what's actually working from your marketing. {competitive_line}\n\n"
        f"I specialize in fixing exactly this — Google Ads, Meta Ads, tracking setup "
        f"(GA4/GTM/Pixel), and reporting so you can see real numbers instead of guessing.\n\n"
        f"Worth a quick 15-minute call to walk through what I found?\n\n"
        f"Best,\n{cfg.sender_name}\n{cfg.sender_title}\n"
        f"{cfg.sender_email} | {cfg.sender_phone} | {cfg.sender_website}"
    )
    if hook:
        whatsapp = (f"Hi, this is {cfg.sender_name.split(' ')[0]} — {hook} "
                    f"Worth a quick chat?")
        linkedin = (f"{greeting} {hook} I work with businesses on exactly this "
                    f"(ads + tracking + reporting) — happy to share what I found "
                    f"if useful, no pitch attached.")
    else:
        whatsapp = (f"Hi, this is {cfg.sender_name.split(' ')[0]} — I checked {domain} and noticed "
                    f"{pain_clause}. That usually means missed leads and no way to measure what's "
                    f"working. Worth a quick chat?")
        linkedin = (f"{greeting} I was looking at {domain} and noticed {pain_clause}. I work with "
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


def build_followup(stage: int, business_name: str, website: str, pain_points: list[str],
                   cfg, contact_name: str = "", fresh_pain: str = "") -> tuple[str, str]:
    """Israr's follow-up cadence: FU1 (day 4) short bump, FU2 (day 8) new angle
    with a fresh audit finding, FU3 (day 14) polite breakup, then close."""
    domain = _domain(website)
    greeting = f"Hi {contact_name.split(' ')[0]}," if contact_name else "Hi there,"
    sign = (f"Best,\n{cfg.sender_name}\n{cfg.sender_title}\n"
            f"{cfg.sender_email} | {cfg.sender_phone} | {cfg.sender_website}")
    pain_clause = _join_natural(pain_points) if pain_points else "the tracking gaps I flagged"
    if stage == 1:
        return (f"Re: A quick observation about {domain}",
                f"{greeting}\n\nJust floating this back to the top of your inbox — I checked "
                f"{domain} and noticed {pain_clause}. Happy to walk you through what I found "
                f"in 15 minutes, no pitch attached.\n\n{sign}")
    if stage == 2:
        new_bit = fresh_pain or pain_clause
        return (f"One more thing I spotted on {domain}",
                f"{greeting}\n\nSince my last note I took another look at {domain} and spotted "
                f"something else worth knowing: {new_bit}. This is exactly the kind of gap that "
                f"quietly costs sales every week. Worth a quick call?\n\n{sign}")
    return (f"Closing the loop — {domain}",
            f"{greeting}\n\nI've reached out a couple of times about the tracking gaps on "
            f"{domain} ({pain_clause}) and don't want to clutter your inbox, so I'll close "
            f"the loop here. If fixing this becomes a priority, you know where to find me.\n\n{sign}")
