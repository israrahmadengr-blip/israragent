import os, sys
from datetime import date, timedelta
from unittest import mock
sys.path.insert(0, os.path.dirname(__file__))

os.environ["LEADS_CSV_PATH"] = "data/test_followup.csv"
os.environ["FOLLOWUP_AFTER_DAYS"] = "4"
os.environ["MAX_FOLLOWUPS_TOTAL"] = "2"
os.environ["MAX_FOLLOWUPS_PER_DAY"] = "10"
os.environ["SECONDS_BETWEEN_SITE_FETCHES"] = "0"
os.environ["NICHES"] = "gym"
os.environ["TARGET_COUNTRIES"] = "PK"

from agent import store, config

# Build a fake existing lead contacted 5 days ago (due for follow-up), and one contacted yesterday (not due)
five_days_ago = (date.today() - timedelta(days=5)).isoformat()
yesterday = (date.today() - timedelta(days=1)).isoformat()

rows = [
    {**{k: "" for k in store.FIELDNAMES}, "business_name": "Overdue Gym", "website": "https://overdue-test.example",
     "status": store.STATUS_CONTACTED, "email_sent_date": five_days_ago, "followup_count": "0",
     "pain_summary": "no Meta Pixel", "osm_id": "node/100"},
    {**{k: "" for k in store.FIELDNAMES}, "business_name": "Fresh Gym", "website": "https://fresh-test.example",
     "status": store.STATUS_CONTACTED, "email_sent_date": yesterday, "followup_count": "0",
     "pain_summary": "no GA4", "osm_id": "node/101"},
    {**{k: "" for k in store.FIELDNAMES}, "business_name": "Maxed Out Gym", "website": "https://maxed-test.example",
     "status": store.STATUS_FOLLOWED_UP, "last_followup_date": five_days_ago, "followup_count": "2",
     "pain_summary": "no GTM", "osm_id": "node/102"},
]
store.save("data/test_followup.csv", rows)

cfg = config.load_settings()
due = store.due_for_followup(store.load("data/test_followup.csv"), cfg.followup_after_days, cfg.max_followups_total)
names_due = {r["business_name"] for r in due}
print("Due for follow-up:", names_due)
assert names_due == {"Overdue Gym"}, f"Expected only 'Overdue Gym' due, got {names_due}"
print("Follow-up scheduling logic: CORRECT (respects days-since AND max-total caps)")

# ---- Test email sending path (mocked SMTP) ----
from agent import emailer

sent_log = []
class FakeSMTP:
    def __init__(self, host, port, timeout=None): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def login(self, u, p): sent_log.append(("login", u))
    def sendmail(self, frm, to, msg): sent_log.append(("send", frm, to))

with mock.patch("smtplib.SMTP_SSL", FakeSMTP):
    result = emailer.send("test@example.com", "Subject", "Body", "me@gmail.com", "app-password-123")
    assert result is True
    assert ("login", "me@gmail.com") in sent_log
    print("Email sending path (mocked): CORRECT")

    # Test skip-when-not-configured path
    result2 = emailer.send("test@example.com", "Subject", "Body", "", "")
    assert result2 is False
    print("Email skip-when-unconfigured path: CORRECT")

print("\nALL FOLLOWUP + EMAIL TESTS PASSED")
