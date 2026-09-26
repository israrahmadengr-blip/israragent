import os, sys, csv
sys.path.insert(0, os.path.dirname(__file__))
os.environ["LEADS_CSV_PATH"] = "data/test_crm_sync.csv"

from agent import store, crm_export

CRM_CRM_HTML = "/mnt/user-data/outputs/israrads-crm.html"

# ---- 1. Field-for-field match against the actual deployed CRM file ----
if os.path.isfile(CRM_CRM_HTML):
    with open(CRM_CRM_HTML, encoding="utf-8") as f:
        html = f.read()
    import re
    m = re.search(r'var CSV_FIELDS = \[(.*?)\];', html, re.S)
    assert m, "Could not find CSV_FIELDS in the deployed CRM file"
    live_fields = [x.strip().strip('"') for x in m.group(1).replace("\n", "").split(",")]
    assert live_fields == crm_export.CRM_FIELDS, (
        f"MISMATCH!\nLive CRM fields:   {live_fields}\nAgent CRM_FIELDS: {crm_export.CRM_FIELDS}"
    )
    print("CRM_FIELDS matches the actual deployed israrads-crm.html exactly:", live_fields)
    # also check the exact valid values agent might emit are accepted by the CRM
    assert "Local Business Directory" in html, "SOURCE_LIST in CRM no longer has 'Local Business Directory'"
    assert '"New Lead"' in html and '"Contacted"' in html and '"Won - Client"' in html and '"Lost"' in html
    print("All status values the agent emits exist in the CRM's STATUS_LIST")
else:
    print("SKIPPED live-file check (israrads-crm.html not found in this environment)")

# ---- 2. Status mapping correctness ----
sample_leads = [
    {"business_name": "A", "status": "Ready for Outreach", "pain_summary": "no GA4"},
    {"business_name": "B", "status": "Contacted", "pain_summary": "no GA4; no GTM"},
    {"business_name": "C", "status": "Followed Up", "pain_summary": "no GA4; no GTM; no HTTPS"},
    {"business_name": "D", "status": "Won - Client", "pain_summary": "No major gaps found"},
    {"business_name": "E", "status": "Lost", "pain_summary": ""},
    {"business_name": "F", "status": "", "pain_summary": ""},  # unexpected/blank status
]
for lead in sample_leads:
    row = crm_export.to_crm_row(lead)
    print(f"{lead['business_name']}: agent status '{lead['status']}' -> CRM status '{row['status']}', priority '{row['priority']}'")

expected = {"A": "New Lead", "B": "Contacted", "C": "Contacted", "D": "Won - Client", "E": "Lost", "F": "New Lead"}
for lead in sample_leads:
    row = crm_export.to_crm_row(lead)
    assert row["status"] == expected[lead["business_name"]], f"Status mapping wrong for {lead['business_name']}"
print("All status mappings correct, including the blank/unexpected fallback")

# priority: D has "No major gaps found" -> Low; C has 3 pain points -> High; A has 1 -> Medium
assert crm_export.to_crm_row(sample_leads[0])["priority"] == "Medium"
assert crm_export.to_crm_row(sample_leads[2])["priority"] == "High"
assert crm_export.to_crm_row(sample_leads[3])["priority"] == "Low"
print("Priority-from-pain-count logic correct")

# ---- 3. No-duplicate-on-repeated-export behavior ----
if os.path.exists("data/test_crm_sync.csv"):
    os.remove("data/test_crm_sync.csv")
if os.path.exists("data/test_crm_import.csv"):
    os.remove("data/test_crm_import.csv")

rows = [store.new_row("Gym One", "gym", "US", "Miami", "https://gym1.example", "", {}, {
    "email_subject": "s", "email_body": "b", "whatsapp": "w", "linkedin": "l", "messenger": "m", "pain_summary": "no GA4"
}, "node/1")]
store.save("data/test_crm_sync.csv", rows)

# --- run 1: export should include the 1 lead ---
loaded = store.load("data/test_crm_sync.csv")
to_sync_1 = store.unsynced_for_crm(loaded)
assert len(to_sync_1) == 1, f"Expected 1 unsynced lead on first run, got {len(to_sync_1)}"
crm_export.write_crm_csv("data/test_crm_import.csv", to_sync_1)
store.mark_crm_synced(to_sync_1)
store.save("data/test_crm_sync.csv", loaded)
print("Run 1: exported 1 new lead to crm_import.csv, marked synced")

# --- run 2 (simulating tomorrow, no new leads found): should export ZERO ---
loaded_again = store.load("data/test_crm_sync.csv")
to_sync_2 = store.unsynced_for_crm(loaded_again)
assert len(to_sync_2) == 0, f"Expected 0 unsynced leads on second run (already synced), got {len(to_sync_2)}"
print("Run 2: correctly exported 0 leads (already synced) — NO DUPLICATE RISK")

# --- run 3: add one more new lead, only the NEW one should be in the export ---
rows2 = store.load("data/test_crm_sync.csv")
rows2.append(store.new_row("Gym Two", "gym", "US", "Austin", "https://gym2.example", "", {}, {
    "email_subject": "s2", "email_body": "b2", "whatsapp": "w2", "linkedin": "l2", "messenger": "m2", "pain_summary": "no GTM"
}, "node/2"))
store.save("data/test_crm_sync.csv", rows2)
loaded_3 = store.load("data/test_crm_sync.csv")
to_sync_3 = store.unsynced_for_crm(loaded_3)
assert len(to_sync_3) == 1 and to_sync_3[0]["business_name"] == "Gym Two", \
    f"Expected only 'Gym Two' unsynced, got {[r['business_name'] for r in to_sync_3]}"
print("Run 3: correctly exported only the 1 genuinely new lead, not the already-synced one")

# ---- 4. Backward compatibility: old-format row with no crm_synced column at all ----
old_style_row = {"business_name": "Legacy Lead", "status": "Contacted"}  # no crm_synced key
assert old_style_row not in store.unsynced_for_crm([]) # sanity
result = store.unsynced_for_crm([old_style_row])
assert len(result) == 1, "A row with no crm_synced key at all should be treated as unsynced"
print("Backward compatibility: pre-existing rows without crm_synced are correctly treated as unsynced")

os.remove("data/test_crm_sync.csv")
os.remove("data/test_crm_import.csv")

print("\nALL CRM SYNC TESTS PASSED")
