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
    "notes", "osm_id", "crm_synced", "contact_name", "contact_role",
    "email_confidence", "platform", "score", "ads_running", "source",
]

STATUS_NEW = "Ready for Outreach"
STATUS_CONTACTED = "Contacted"
STATUS_FOLLOWED_UP = "Followed Up"
STATUS_DONE = "Won - Client"
STATUS_LOST = "Lost"
STATUS_CLOSED = "Closed"


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
            audit_result: dict, drafts: dict, osm_id: str, contact: dict | None = None,
            score: str = "", ads_running: str = "Unknown", source: str = "") -> dict:
    contact = contact or {}
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
        "contact_name": contact.get("contact_name", ""), "contact_role": contact.get("contact_role", ""),
        "email_confidence": contact.get("email_confidence", ""),
        "platform": audit_result.get("platform", "Unknown"),
        "score": str(score), "ads_running": ads_running, "source": source,
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


def existing_domains(rows: list[dict]) -> set[str]:
    from urllib.parse import urlparse
    out = set()
    for r in rows:
        site = (r.get("website") or "").strip()
        if site:
            host = urlparse(site if "://" in site else "https://" + site).netloc.lower()
            out.add(host[4:] if host.startswith("www.") else host)
    return out


def load_blocklist(path: str) -> set[str]:
    """Domains never to contact (e.g. already emailed by Israr's main outreach
    system — synced from its dedup list). CSV with a 'domain' column."""
    import csv as _csv
    if not os.path.isfile(path):
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        return {(row.get("domain") or "").strip().lower() for row in _csv.DictReader(f)
                if (row.get("domain") or "").strip()}


def followup_stage_due(rows: list[dict], days_list: list[int]) -> list[dict]:
    """FU cadence (Israr's system): stage N is due when the lead's age since
    first email reaches days_list[N-1] and exactly N-1 follow-ups were sent.
    Defaults [4, 8, 14]: FU1 day 4, FU2 day 8, FU3 breakup day 14."""
    today = date.today()
    out = []
    for r in rows:
        if r.get("status") not in (STATUS_CONTACTED, STATUS_FOLLOWED_UP):
            continue
        try:
            count = int(r.get("followup_count") or 0)
        except ValueError:
            count = 0
        if count >= len(days_list):
            continue
        sent = r.get("email_sent_date")
        if not sent:
            continue
        try:
            sent_date = datetime.strptime(sent, "%Y-%m-%d").date()
        except ValueError:
            continue
        if (today - sent_date).days >= days_list[count]:
            out.append(r)
    return out
