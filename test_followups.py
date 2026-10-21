"""Follow-up cadence tests (v2): FU1 day 4 / FU2 day 8 / FU3 breakup day 14,
measured from the first email; stage = follow-ups already sent. Plus the
emailer paths. Run with: python3 test_followups.py
"""
import os
import sys
from datetime import date, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
os.environ["LEADS_CSV_PATH"] = "data/test_followup.csv"

from agent import store  # noqa: E402


def row(name, days_ago, count, status=store.STATUS_CONTACTED):
    base = {k: "" for k in store.FIELDNAMES}
    base.update({"business_name": name, "website": f"https://{name}.example",
                 "status": status,
                 "email_sent_date": (date.today() - timedelta(days=days_ago)).isoformat(),
                 "followup_count": str(count), "pain_summary": "no Meta Pixel"})
    return base


rows = [
    row("fu1due", 5, 0),          # day 5, none sent -> FU1 due
    row("notyet", 2, 0),          # day 2 -> not due
    row("fu2due", 9, 1),          # day 9, FU1 sent -> FU2 due
    row("fu3due", 15, 2),         # day 15, FU1+FU2 sent -> FU3 (breakup) due
    row("exhausted", 30, 3),      # all 3 sent -> closed by main loop, never due
    row("fresh", 1, 0),
]
due = store.followup_stage_due(rows, [4, 8, 14])
names = {r["business_name"] for r in due}
print("Due:", names)
assert names == {"fu1due", "fu2due", "fu3due"}, names
print("Stage cadence CORRECT: thresholds 4/8/14 from first email, stage-aware")

# legacy wrapper compatibility (old signature still behaves)
legacy = store.due_for_followup(rows, 4, 2)
assert "fu1due" in {r["business_name"] for r in legacy}
print("Legacy due_for_followup wrapper: OK")

# ---- emailer paths (mocked SMTP) ----
from agent import emailer  # noqa: E402
sent_log = []


class FakeSMTP:
    def __init__(self, host, port, timeout=None): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def login(self, u, p): sent_log.append(("login", u))
    def sendmail(self, frm, to, msg): sent_log.append(("send", frm, to))


with mock.patch("smtplib.SMTP_SSL", FakeSMTP):
    assert emailer.send("t@example.com", "S", "B", "me@gmail.com", "app-pass") is True
    assert ("login", "me@gmail.com") in sent_log
    assert emailer.send("t@example.com", "S", "B", "", "") is False
print("Emailer paths: CORRECT")
print("\nALL FOLLOWUP + EMAIL TESTS PASSED")
