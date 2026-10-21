"""Lead score 1–5 from VERIFIED signals only (same scheme as Israr's main
outreach system): verified running ads +2, broken/incomplete tracking +1,
named decision-maker contactable +1, growth signals +1. Base 1, cap 5.
Unknowns never score — an uncheckable signal earns nothing.
"""
from __future__ import annotations


def score_lead(audit: dict, enrich: dict, ads_running: str) -> tuple[int, str]:
    points, reasons = 1, []
    if ads_running == "Yes":
        points += 2
        reasons.append("verified running ads")
    gaps = sum(1 for k in ("google_ads_tag", "meta_pixel", "ga4", "gtm")
               if audit.get(k) == "No")
    if gaps >= 1:
        points += 1
        reasons.append(f"{gaps} tracking gap(s)")
    if enrich.get("contact_name") and enrich.get("email"):
        points += 1
        reasons.append(f"decision-maker: {enrich['contact_name']}")
    if audit.get("has_reviews") == "Yes" or audit.get("has_socials") == "Yes":
        points += 1
        reasons.append("active brand signals (reviews/socials)")
    return min(points, 5), "; ".join(reasons)
