"""Unit checks for the v3 intel engine — pure dict inputs, no network.
Run with: python3 test_intel.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from agent import intel, store, writer  # noqa: E402


def audit(**over):
    base = {"fetched": True, "https": True, "ga4": "Yes", "gtm": "Yes",
            "meta_pixel": "Yes", "google_ads_tag": "Yes",
            "ai_crawlers_blocked": "No", "email": "",
            "platform": "Shopify", "is_store": "Yes",
            "has_booking": "Unknown", "has_reviews": "Yes",
            "has_socials": "Yes"}
    base.update(over)
    return base


# 1. Clean site -> no pains, COLD, no hook-driven draft change
r = intel.analyse(audit())
assert r["pains"] == [] and r["classification"] == "COLD", r
assert r["top_pain"] is None

# 2. Missing GA4 -> VERIFIED pain, scored, hook exists
r = intel.analyse(audit(ga4="No"))
assert r["top_pain"]["id"] == "no_ga4", r["top_pain"]
assert r["top_pain"]["confidence"] == "VERIFIED"
assert r["top_pain"]["score"] >= 75 and r["classification"] == "HOT", r
assert "couldn't detect a GA4" in intel.hook_for(r["top_pain"], "Acme")

# 3. Unknown checks produce NO pains (never guessed)
r = intel.analyse(audit(ga4="Unknown", gtm="Unknown",
                        meta_pixel="Unknown", google_ads_tag="Unknown"))
assert r["pains"] == [], r["pains"]

# 4. Unfetched site -> empty intel, COLD
r = intel.analyse(audit(fetched=False, ga4="No"))
assert r["pains"] == [] and r["classification"] == "COLD"

# 5. Ads verified running + missing AW tag -> severity upgrades to high
r = intel.analyse(audit(google_ads_tag="No"), ads_running="Yes")
tp = next(p for p in r["pains"] if p["id"] == "no_google_ads_tag")
assert tp["severity"] == "high", tp
r2 = intel.analyse(audit(google_ads_tag="No"), ads_running="Unknown")
tp2 = next(p for p in r2["pains"] if p["id"] == "no_google_ads_tag")
assert tp2["severity"] == "medium", tp2

# 6. AI-crawler block is its own VERIFIED pain
r = intel.analyse(audit(ai_crawlers_blocked="Yes"))
assert any(p["id"] == "ai_blocked" for p in r["pains"])

# 7. Writer uses the intel hook when a top pain exists
class Cfg:  # minimal stand-in for config.Settings
    sender_name = "Israr Ahmad"
    sender_title = "Performance Marketing"
    sender_email = "contact@israrads.com"
    sender_phone = "+92 303 5995553"
    sender_website = "israrads.com"
    gemini_api_key = ""

r = intel.analyse(audit(ga4="No"))
d = writer.build_drafts("Acme", "https://acme.example", ["no GA4 analytics"],
                        Cfg(), contact_name="Sarah Jones", intel=r)
assert d["email_body"].startswith("Hi Sarah,"), d["email_body"][:40]
assert "couldn't detect a GA4" in d["email_body"], d["email_body"]
assert "couldn't detect a GA4" in d["linkedin"]
d2 = writer.build_drafts("Acme", "https://acme.example", ["no GA4 analytics"],
                         Cfg(), contact_name="Sarah Jones")
assert "I ran a quick technical check" in d2["email_body"]  # fallback intact

# 8. Store row carries intel fields; positional callers unaffected
row = store.new_row("Acme", "ecommerce", "GB", "", "https://acme.example",
                    "", audit(), {"email_subject": "s", "email_body": "b",
                    "whatsapp": "w", "linkedin": "l", "messenger": "m"},
                    "web:acme.example", intel=r)
assert row["classification"] == "HOT", row["classification"]
assert row["top_pain"] == "no GA4 analytics"
assert row["pain_score"].isdigit() and row["opportunity_score"].isdigit()
for col in ("classification", "top_pain", "pain_score", "opportunity_score"):
    assert col in store.FIELDNAMES, col

print("ALL INTEL CHECKS PASSED (v3)")
