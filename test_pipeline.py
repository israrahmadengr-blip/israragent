"""Exercises the v2 pipeline (retargeted: e-commerce + services, no OSM) with
fake website responses — no real network. Run with: python3 test_pipeline.py
"""
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

os.environ["TARGETS_CSV_PATH"] = "data/test_targets.csv"
os.environ["BLOCKLIST_CSV_PATH"] = "data/test_blocklist.csv"
os.environ["LEADS_CSV_PATH"] = "data/test_leads.csv"
os.environ["CRM_IMPORT_CSV_PATH"] = "data/test_crm_import_pipeline.csv"
os.environ["MAX_NEW_LEADS_PER_DAY"] = "10"
os.environ["MAX_EMAILS_PER_DAY"] = "10"
os.environ["SECONDS_BETWEEN_SITE_FETCHES"] = "0"
# Gmail intentionally unset -> drafts only

with open("data/test_targets.csv", "w") as f:
    f.write("website,business_name,vertical,country\n")
    f.write("https://velvetlane-test.example,Velvet Lane,ecommerce,GB\n")
    f.write("https://summitmove-test.example,Summit Move,services,US\n")
    f.write("https://blockedbrand.example,Blocked Brand,ecommerce,US\n")
with open("data/test_blocklist.csv", "w") as f:
    f.write("domain\nblockedbrand.example\n")

if os.path.exists("data/test_leads.csv"):
    os.remove("data/test_leads.csv")

PAGES = {
    "https://velvetlane-test.example": (
        "<html><head><script src='https://www.googletagmanager.com/gtm.js?id=GTM-XYZ12'></script></head>"
        "<body><img src='https://cdn.shopify.com/s/files/logo.png'>"
        "<a href='/products/silk-dress'>Silk Dress</a> Add to cart £85 "
        "Customer reviews ★★★★★ <a href='https://instagram.com/velvetlane'>IG</a></body></html>"),
    "https://velvetlane-test.example/about": (
        "<html><body><h2>Our Story</h2><p>Sarah Mitchell — Founder of Velvet Lane. "
        "Reach her at <a href='mailto:sarah@velvetlane-test.example'>email</a>.</p>"
        "<a href='https://www.linkedin.com/company/velvetlane'>LinkedIn</a></body></html>"),
    "https://velvetlane-test.example/contact": "<html><body>Contact us</body></html>",
    "https://summitmove-test.example": (
        "<html><body><h1>Summit Move</h1><p>Book a consultation for your move.</p>"
        "<a href='mailto:hello@summitmove-test.example'>Email</a></body></html>"),
}


class FakeResponse:
    def __init__(self, text="", status_code=200, url=""):
        self.text = text
        self.status_code = status_code
        self.url = url


def fake_get(url, **kwargs):
    if "bing.com" in url or "facebook.com/ads/library" in url:
        return FakeResponse(text="", status_code=404, url=url)
    if url.endswith("/robots.txt"):
        return FakeResponse(text="User-agent: *\nDisallow: /admin\n", status_code=200, url=url)
    html = PAGES.get(url.rstrip("/")) or PAGES.get(url)
    if html is None:
        return FakeResponse(text="", status_code=404, url=url)
    return FakeResponse(text=html, status_code=200, url=url)


def fake_post(url, **kwargs):
    return FakeResponse(text="", status_code=200, url=url)  # DDG: no results in test


with mock.patch("requests.get", side_effect=fake_get), \
     mock.patch("requests.post", side_effect=fake_post):
    from agent import __main__ as main_mod
    stats = main_mod.run_once()

print("STATS:", stats)
from agent import store  # noqa: E402
rows = store.load("data/test_leads.csv")
names = {r["business_name"] for r in rows}
print("LEADS:", names)
assert "Blocked Brand" not in names, "blocklisted domain must be skipped"
assert names == {"Velvet Lane", "Summit Move"}, f"unexpected leads: {names}"

velvet = next(r for r in rows if r["business_name"] == "Velvet Lane")
assert velvet["platform"] == "Shopify", velvet["platform"]
assert velvet["contact_name"] == "Sarah Mitchell", velvet["contact_name"]
assert velvet["email"] == "sarah@velvetlane-test.example", velvet["email"]
assert velvet["email_confidence"] == "found", velvet["email_confidence"]
assert velvet["score"] == "4", f"expected score 4, got {velvet['score']} ({velvet['notes']})"
assert velvet["email_draft"].startswith("Hi Sarah,"), velvet["email_draft"][:40]

summit = next(r for r in rows if r["business_name"] == "Summit Move")
assert summit["email"] == "hello@summitmove-test.example"
assert summit["email_confidence"] == "generic"

print("\nALL PIPELINE CHECKS PASSED (v2 retargeted)")
