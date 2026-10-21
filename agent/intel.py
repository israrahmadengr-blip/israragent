"""Prospect-intel engine (v3, added 2026-10-21 — the same system as Israr's
main outreach stack, ported to this agent).

Turns one lead's site audit into:
  - evidence-labelled pain points (VERIFIED / LIKELY / UNVERIFIED), each
    scored 0-100 with the weighted model
    (Evidence 25% / Impact 25% / Service Fit 20% / Severity 15% /
     Outreach 10% / Urgency 5%),
  - a 0-100 scorecard + Overall Opportunity score,
  - a HOT / WARM / COLD classification,
  - an evidence-based outreach hook for the top pain point.

Honesty rules (inherited from the main system, non-negotiable):
  - A check the audit could not complete is "Unknown" and produces NO
    pain point — unknowns are never guessed into findings.
  - Ad presence comes only from ads_check's tri-state result; "Unknown"
    is never treated as "not running ads".
  - No invented metrics (ROAS/CPA/CTR), ever.
"""
from __future__ import annotations

SEV_DIM = {"critical": 100, "high": 80, "medium": 55, "low": 30}
CONF_DIM = {"VERIFIED": 100, "LIKELY": 60, "UNVERIFIED": 25}
CONF_RANK = {"VERIFIED": 0, "LIKELY": 1, "UNVERIFIED": 2}


def _weighted(evidence, impact, fit, severity, outreach, urgency):
    return round(0.25 * evidence + 0.25 * impact + 0.20 * fit +
                 0.15 * severity + 0.10 * outreach + 0.05 * urgency)


def _pain(pid, category, title, evidence, confidence, severity, impact,
          service, dims):
    ev, sev = CONF_DIM[confidence], SEV_DIM[severity]
    return {
        "id": pid, "category": category, "title": title,
        "evidence": evidence, "confidence": confidence,
        "severity": severity, "impact": impact, "service": service,
        "score": _weighted(ev, dims[0], dims[1], sev, dims[2], dims[3]),
    }


def analyse(audit_result: dict, ads_running: str = "Unknown",
            vertical: str = "") -> dict:
    """audit_result: the dict from site_audit.audit(). ads_running: the
    tri-state from ads_check.check_ads(). Returns pains/scorecard/class."""
    a = audit_result
    pains = []
    if not a.get("fetched"):
        return {"pains": [], "scorecard": {}, "classification": "COLD",
                "opportunity": 0, "top_pain": None}

    no = lambda k: a.get(k) == "No"  # noqa: E731 — observed absence = VERIFIED

    if no("ga4"):
        pains.append(_pain(
            "no_ga4", "Tracking", "no GA4 analytics",
            "Homepage code contains no GA4 measurement ID (G-).",
            "VERIFIED", "high",
            "No first-party view of what website traffic does — every "
            "channel is optimised blind and no reporting baseline exists.",
            "GA4 setup + GTM implementation", (85, 95, 90, 80)))
    if no("google_ads_tag"):
        sev = "high" if ads_running == "Yes" else "medium"
        ev = ("No Google Ads tag (AW-) in homepage code, while the ad-"
              "library check shows this advertiser active."
              if ads_running == "Yes" else
              "No Google Ads tag (AW-) detected in homepage code "
              "(homepage only — this alone does not prove whether "
              "Google Ads campaigns exist).")
        pains.append(_pain(
            "no_google_ads_tag", "Google Ads Tracking",
            "no Google Ads conversion tracking", ev, "VERIFIED", sev,
            "If Google Ads is running, Smart Bidding has no website "
            "conversion signal to learn from — budget optimises toward "
            "clicks, not buyers or leads.",
            "Google Ads conversion tracking + Enhanced Conversions",
            (90 if sev == "high" else 70, 95, 90, 75)))
    if no("meta_pixel"):
        sev = "high" if ads_running == "Yes" else "medium"
        ev = ("No Meta Pixel in homepage code, while the ad-library "
              "check shows this advertiser active."
              if ads_running == "Yes" else
              "No Meta Pixel (fbq) detected in homepage code (homepage "
              "only — this alone does not prove whether Meta campaigns "
              "exist).")
        pains.append(_pain(
            "no_meta_pixel", "Meta Tracking", "no Meta Pixel", ev,
            "VERIFIED", sev,
            "Without the pixel there are no retargeting pools and no "
            "conversion optimisation for Meta campaigns.",
            "Meta Pixel implementation + event setup",
            (90 if sev == "high" else 70, 95, 90, 75)))
    if no("gtm"):
        pains.append(_pain(
            "no_gtm", "Tracking", "no Google Tag Manager",
            "No GTM container ID found in homepage code.",
            "VERIFIED", "medium",
            "Every tracking change needs a developer and a code "
            "release — slow, risky, and the usual reason fixes never ship.",
            "GTM implementation (server-side ready)", (60, 90, 80, 55)))
    if a.get("ai_crawlers_blocked") == "Yes":
        pains.append(_pain(
            "ai_blocked", "Visibility",
            "the site blocks AI search crawlers",
            "robots.txt explicitly disallows one or more of GPTBot, "
            "ClaudeBot, PerplexityBot, Google-Extended.",
            "VERIFIED", "medium",
            "More buyers now ask ChatGPT/Perplexity instead of Googling — "
            "a blocked site simply never appears in those answers.",
            "AI-visibility (GEO) fix + tracking review", (60, 70, 80, 55)))
    if not a.get("https"):
        pains.append(_pain(
            "no_https", "CRO", "no HTTPS", "The site does not serve "
            "over HTTPS.", "VERIFIED", "high",
            "Browsers flag the site 'Not secure' — paid clicks land on "
            "a warning, and checkout/form trust collapses.",
            "HTTPS + landing-page review", (80, 50, 75, 85)))
    if a.get("has_reviews") == "No":
        pains.append(_pain(
            "no_reviews", "CRO", "no reviews or testimonials visible",
            "Homepage scan found no review/testimonial/rating signals.",
            "LIKELY", "medium",
            "Cold paid traffic has no proof the offer is trusted — one "
            "of the cheapest conversion leaks to fix.",
            "Landing-page CRO review", (55, 55, 65, 45)))
    if vertical == "services" and a.get("has_booking") == "No":
        pains.append(_pain(
            "no_booking", "CRO", "no online booking/quote option visible",
            "Homepage scan found no book/quote/consultation call-to-"
            "action phrases.",
            "LIKELY", "medium",
            "Service buyers who can't start a booking or quote online "
            "in one click usually call the competitor who lets them.",
            "Landing-page CRO review", (60, 55, 70, 50)))

    pains.sort(key=lambda p: (-p["score"], CONF_RANK[p["confidence"]]))

    # ---- scorecard (triage aids, not precision measurements)
    tags = ["ga4", "gtm", "meta_pixel", "google_ads_tag"]
    present = sum(1 for k in tags if a.get(k) == "Yes")
    known = sum(1 for k in tags if a.get(k) in ("Yes", "No"))
    tracking = round(100 * present / known) if known else 0
    sc = {
        "Tracking": tracking,
        "GA4 / Analytics": 100 if a.get("ga4") == "Yes" else 10,
        "GTM": 100 if a.get("gtm") == "Yes" else 25,
        "Meta Pixel": 100 if a.get("meta_pixel") == "Yes" else 15,
        "Google Ads readiness": (100 if a.get("google_ads_tag") == "Yes"
                                 and a.get("ga4") == "Yes" else
                                 70 if a.get("google_ads_tag") == "Yes"
                                 else 15),
        "Meta Ads readiness": (100 if a.get("meta_pixel") == "Yes"
                               and a.get("gtm") == "Yes" else
                               70 if a.get("meta_pixel") == "Yes" else 20),
    }
    cro = 100
    for p in pains:
        if p["category"] == "CRO":
            cro -= {"high": 35, "medium": 20, "low": 8}[p["severity"]]
    sc["CRO"] = max(0, cro)
    verified = sum(1 for p in pains if p["confidence"] == "VERIFIED")
    sc["Reporting opportunity"] = min(100, 30 + verified * 15)
    top = pains[0]["score"] if pains else 0
    opportunity = round(0.6 * top + 0.4 * (100 - tracking)) if pains \
        else 100 - tracking
    sc["Overall Opportunity"] = opportunity

    if pains and pains[0]["score"] >= 75 and \
            pains[0]["confidence"] == "VERIFIED":
        classification = "HOT"
    elif pains and pains[0]["score"] >= 55:
        classification = "WARM"
    else:
        classification = "COLD"
    return {"pains": pains, "scorecard": sc,
            "classification": classification, "opportunity": opportunity,
            "top_pain": pains[0] if pains else None}


HOOKS = {
    "no_ga4": "I was checking {biz}'s website and couldn't detect a GA4 "
              "setup in the site code — which means there's no first-party "
              "view of what your traffic actually does once it lands.",
    "no_google_ads_tag": "I was reviewing {biz}'s setup and couldn't "
              "detect a Google Ads conversion tag on the site. If you're "
              "running paid search, that means Smart Bidding is learning "
              "from clicks rather than actual leads or sales.",
    "no_meta_pixel": "I was reviewing {biz}'s setup and couldn't detect "
              "a Meta Pixel on the site. If you're running Meta campaigns, "
              "there'd be no retargeting pool and no conversion signal "
              "coming back from the website.",
    "no_gtm": "I noticed {biz}'s site has no Tag Manager in place, so "
              "every tracking change currently needs a developer release "
              "— that's usually where measurement fixes go to die.",
    "ai_blocked": "I noticed {biz}'s site is blocking AI search crawlers "
              "like ChatGPT and Perplexity from indexing it — as more "
              "buyers ask AI tools instead of Googling, that quietly "
              "removes you from their answers.",
    "no_https": "I noticed {biz}'s site isn't serving over HTTPS, so "
              "browsers flag it 'Not secure' — for paid traffic that's "
              "a trust killer before the offer is even seen.",
    "no_reviews": "I noticed {biz}'s homepage doesn't show reviews or "
              "testimonials — for cold paid traffic arriving with no "
              "trust yet, that's usually the cheapest conversion leak "
              "to fix.",
    "no_booking": "I noticed {biz}'s site doesn't offer an obvious online "
              "booking or quote option — service buyers who can't start "
              "in one click usually call the competitor who lets them.",
}


def hook_for(pain: dict, business_name: str) -> str:
    tpl = HOOKS.get(pain.get("id", ""))
    return tpl.format(biz=business_name) if tpl else ""
