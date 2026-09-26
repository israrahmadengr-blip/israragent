"""Exercises the full daily pipeline with fake OSM/website responses — no real
network calls. Run with: python3 test_pipeline.py
"""
import os
import sys
import json
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

os.environ["NICHES"] = "gym,dentist"
os.environ["TARGET_COUNTRIES"] = "US"
os.environ["MAX_NEW_LEADS_PER_DAY"] = "10"
os.environ["MAX_EMAILS_PER_DAY"] = "10"
os.environ["LEADS_CSV_PATH"] = "data/test_leads.csv"
os.environ["CRM_IMPORT_CSV_PATH"] = "data/test_crm_import_pipeline.csv"
os.environ["SECONDS_BETWEEN_SITE_FETCHES"] = "0"

from agent import store  # noqa: E402

# start clean
if os.path.exists("data/test_leads.csv"):
    os.remove("data/test_leads.csv")

FAKE_OVERPASS_RESPONSES = {
    "gym": [
        {"type": "node", "id": 1, "tags": {"name": "Iron Peak Fitness", "website": "https://ironpeak-test.example"}},
        {"type": "node", "id": 2, "tags": {"name": "No Website Gym"}},  # should be skipped (no website)
    ],
    "dentist": [
        {"type": "node", "id": 3, "tags": {"name": "Bright Smile Dental", "website": "https://brightsmile-test.example", "phone": "+92 51 1112222"}},
    ],
}

FAKE_HTML = {
    "https://ironpeak-test.example": "<html><body>Plain site, nothing installed. <a href='mailto:info@ironpeak-test.example'>Email us</a></body></html>",
    "https://brightsmile-test.example": (
        "<html><head><script>fbq('init','123456789');</script>"
        "<script src='https://www.googletagmanager.com/gtm.js?id=GTM-ABCD1'></script></head>"
        "<body>No email listed here.</body></html>"
    ),
}
FAKE_ROBOTS = {
    "https://ironpeak-test.example/robots.txt": "User-agent: GPTBot\nDisallow: /\n",
    "https://brightsmile-test.example/robots.txt": "User-agent: *\nDisallow: /admin\n",
}


class FakeResponse:
    def __init__(self, text="", status_code=200, url=""):
        self.text = text
        self.status_code = status_code
        self.url = url or ""

    def json(self):
        return json.loads(self.text)


def fake_post(url, data=None, timeout=None, headers=None):
    query = data.get("data", "") if data else ""
    if "gym" in os.environ.get("_CURRENT_NICHE", ""):
        pass
    # crude: figure out which niche by matching tag filter text embedded in query
    if 'leisure"="fitness_centre' in query:
        elements = FAKE_OVERPASS_RESPONSES["gym"]
    elif 'amenity"="dentist' in query or 'healthcare"="dentist' in query:
        elements = FAKE_OVERPASS_RESPONSES["dentist"]
    else:
        elements = []
    return FakeResponse(text=json.dumps({"elements": elements}), status_code=200)


def fake_get(url, timeout=None, headers=None, allow_redirects=None):
    if url.endswith("/robots.txt"):
        return FakeResponse(text=FAKE_ROBOTS.get(url, ""), status_code=200, url=url)
    html = FAKE_HTML.get(url)
    if html is None:
        return FakeResponse(text="", status_code=404, url=url)
    return FakeResponse(text=html, status_code=200, url=url)


with mock.patch("requests.post", side_effect=fake_post), \
     mock.patch("requests.get", side_effect=fake_get):
    from agent import __main__ as main_mod
    stats = main_mod.run_once()

print("\n=== STATS ===")
print(stats)

rows = store.load("data/test_leads.csv")
print(f"\n=== {len(rows)} LEADS SAVED ===")
for r in rows:
    print(f"\n--- {r['business_name']} ({r['website']}) ---")
    print("Email:", r["email"] or "(none found)")
    print("Google Ads:", r["google_ads_tag"], "| Meta Pixel:", r["meta_pixel"],
          "| GA4:", r["ga4"], "| GTM:", r["gtm"], "| HTTPS:", r["https"],
          "| AI crawlers blocked:", r["ai_crawlers_blocked"])
    print("Pain summary:", r["pain_summary"])
    print("Status:", r["status"], "| Email sent date:", r["email_sent_date"])
    print("WhatsApp draft:", r["whatsapp_draft"])
    assert " i " not in r["whatsapp_draft"].lower()[:3], "Capitalization bug!"

# Checks
assert len(rows) == 2, f"expected 2 leads (one skipped for no website), got {len(rows)}"
names = {r["business_name"] for r in rows}
assert "No Website Gym" not in names, "Lead with no website should have been skipped!"
iron = next(r for r in rows if r["business_name"] == "Iron Peak Fitness")
assert iron["email"] == "info@ironpeak-test.example", f"Expected email extracted, got {iron['email']!r}"
assert iron["ai_crawlers_blocked"] == "Yes", "GPTBot block should have been detected"
bright = next(r for r in rows if r["business_name"] == "Bright Smile Dental")
assert bright["meta_pixel"] == "Yes" and bright["gtm"] == "Yes", "Bright Smile tags should be detected"
assert bright["google_ads_tag"] == "No", "Bright Smile has no Google Ads tag in fake HTML"

print("\nALL PIPELINE CHECKS PASSED")
