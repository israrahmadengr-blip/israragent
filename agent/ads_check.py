"""Verified ad-presence check (Israr's standing rule since 2026-10-09: never
claim 'no ads' from page tags alone — check the ad libraries).

Free routes only. Both libraries are JavaScript apps that usually refuse
datacenter IPs, so this is best-effort and honest: it returns "Yes" only on
positive evidence, "Unknown" whenever the check could not be completed —
"Unknown" is NEVER treated as 'not running ads' anywhere downstream.
"""
from __future__ import annotations
import requests

from .site_audit import UA


def check_ads(business_name: str, domain: str, timeout: int = 12) -> str:
    # Meta Ad Library public page (no login) — often blocked; parse if served.
    try:
        r = requests.get(
            "https://www.facebook.com/ads/library/",
            params={"active_status": "active", "ad_type": "all",
                    "country": "ALL", "q": domain, "search_type": "keyword_unordered"},
            timeout=timeout, headers={"User-Agent": UA})
        if r.status_code == 200 and domain.split(".")[0] in r.text.lower() \
                and "ad_library_main" in r.text:
            return "Yes"
    except requests.RequestException:
        pass
    # Google Ads Transparency Center is a JS app with no public read endpoint;
    # without rendered evidence we stay honest:
    return "Unknown"
