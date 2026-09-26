"""The CRM lives as a plain CSV file in this repo (data/leads.csv). Each daily
run reads it, adds new leads, updates follow-up status, and the GitHub Actions
workflow commits the updated file back — no database or hosting needed.
"""
from __future__ import annotations
import csv
import os
from datetime import date, datetime

FIELDNAMES = [
    "date_found", "business_name", "niche", "country", "city", "website", "phone", "email",
    "google_ads_tag", "meta_pixel", "ga4", "gtm", "https", "ai_crawlers_blocked",
    "pain_summary", "email_subject", "email_draft", "whatsapp_draft", "linkedin_draft",
    "messenger_draft", "status", "email_sent_date", "followup_count", "last_followup_date",
    "notes", "osm_id", "crm_synced",
]

STATUS_NEW = "Ready for Outreach"
STATUS_CONTACTED = "Contacted"
STATUS_FOLLOWED_UP = "Followed Up"
STATUS_DONE = "Won - Client"
STATUS_LOST = "Lost"


def load(path: str) -> list[dict]:
    if not os.path.isfile(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in FIELDNAMES})


def existing_osm_ids(rows: list[dict]) -> set[str]:
    return {r["osm_id"] for r in rows if r.get("osm_id")}


def new_row(business_name: str, niche: str, country: str, city: str, website: str, phone: str,
            audit_result: dict, drafts: dict, osm_id: str) -> dict:
    return {
        "date_found": date.today().isoformat(),
        "business_name": business_name, "niche": niche, "country": country, "city": city,
        "website": website, "phone": phone, "email": audit_result.get("email", ""),
        "google_ads_tag": audit_result.get("google_ads_tag", "Unknown"),
        "meta_pixel": audit_result.get("meta_pixel", "Unknown"),
        "ga4": audit_result.get("ga4", "Unknown"), "gtm": audit_result.get("gtm", "Unknown"),
        "https": "Yes" if audit_result.get("https") else "No",
        "ai_crawlers_blocked": audit_result.get("ai_crawlers_blocked", "Unknown"),
        "pain_summary": drafts.get("pain_summary", ""),
        "email_subject": drafts["email_subject"], "email_draft": drafts["email_body"],
        "whatsapp_draft": drafts["whatsapp"], "linkedin_draft": drafts["linkedin"],
        "messenger_draft": drafts["messenger"],
        "status": STATUS_NEW, "email_sent_date": "", "followup_count": "0",
        "last_followup_date": "", "notes": "", "osm_id": osm_id, "crm_synced": "No",
    }


def unsynced_for_crm(rows: list[dict]) -> list[dict]:
    """Leads not yet exported to crm_import.csv. Old rows saved before this field
    existed have no 'crm_synced' key at all, which counts as unsynced too."""
    return [r for r in rows if r.get("crm_synced") != "Yes"]


def mark_crm_synced(rows: list[dict]) -> None:
    """Mutates the given rows in place — pass the SAME row objects that are
    about to be saved, so the flag actually persists to leads.csv."""
    for r in rows:
        r["crm_synced"] = "Yes"


def due_for_followup(rows: list[dict], after_days: int, max_total: int) -> list[dict]:
    today = date.today()
    out = []
    for r in rows:
        if r.get("status") not in (STATUS_CONTACTED, STATUS_FOLLOWED_UP):
            continue
        try:
            count = int(r.get("followup_count") or 0)
        except ValueError:
            count = 0
        if count >= max_total:
            continue
        last = r.get("last_followup_date") or r.get("email_sent_date")
        if not last:
            continue
        try:
            last_date = datetime.strptime(last, "%Y-%m-%d").date()
        except ValueError:
            continue
        if (today - last_date).days >= after_days:
            out.append(r)
    return out
