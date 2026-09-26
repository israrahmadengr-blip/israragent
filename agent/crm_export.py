"""Produces data/crm_import.csv — the SAME 23 columns, in the SAME order, that
the israrads CRM's "Import CSV" button expects. Drop this file straight into
the CRM (sidebar -> Import CSV) and every lead lands in the right fields.

Why this is a separate file from data/leads.csv (rather than one shared file):
leads.csv also carries columns the agent itself needs (osm_id for de-duplication,
followup_count, per-channel drafts) that the CRM doesn't use and shouldn't have
to know about. This file is the clean, CRM-shaped view of the same data.
"""
from __future__ import annotations
import csv
import os

# Must exactly match CSV_FIELDS in israrads-crm.html's <script> section.
CRM_FIELDS = [
    "company", "contactPerson", "role", "email", "phone", "website", "linkedin",
    "country", "niche", "location", "googleAds", "metaAds", "tracking", "problem",
    "painPoint", "source", "channel", "status", "priority", "dealValue",
    "lastContact", "nextFollowUp", "notes",
]

STATUS_MAP = {
    "Ready for Outreach": "New Lead",
    "Contacted": "Contacted",
    "Followed Up": "Contacted",
    "Won - Client": "Won - Client",
    "Lost": "Lost",
}


def _yesno(value: str) -> str:
    return value if value in ("Yes", "No") else ""  # CRM's own import defaults "" to "No"


def _priority_from_pain_count(pain_summary: str) -> str:
    if not pain_summary or pain_summary == "No major gaps found":
        return "Low"
    count = pain_summary.count(";") + 1
    return "High" if count >= 3 else "Medium"


def to_crm_row(lead: dict) -> dict:
    pain_summary = lead.get("pain_summary", "")
    return {
        "company": lead.get("business_name", ""),
        "contactPerson": "",
        "role": "",
        "email": lead.get("email", ""),
        "phone": lead.get("phone", ""),
        "website": lead.get("website", ""),
        "linkedin": "",
        "country": lead.get("country", ""),
        "niche": lead.get("niche", ""),
        "location": lead.get("city", ""),
        "googleAds": _yesno(lead.get("google_ads_tag", "")),
        "metaAds": _yesno(lead.get("meta_pixel", "")),
        "tracking": pain_summary,
        "problem": pain_summary.split(";")[0].strip() if pain_summary else "",
        "painPoint": f"Site check found: {pain_summary}." if pain_summary else "",
        "source": "Local Business Directory",
        "channel": "Email" if lead.get("email") else "",
        "status": STATUS_MAP.get(lead.get("status", ""), "New Lead"),
        "priority": _priority_from_pain_count(pain_summary),
        "dealValue": "",
        "lastContact": lead.get("email_sent_date") or lead.get("last_followup_date") or "",
        "nextFollowUp": "",  # left for Israr to set inside the CRM once he starts working the lead
        "notes": (f"Found via AI Lead Agent (OpenStreetMap) on {lead.get('date_found','')}. "
                  f"AI crawlers blocked: {lead.get('ai_crawlers_blocked','Unknown')}."),
    }


def write_crm_csv(path: str, leads: list[dict]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CRM_FIELDS)
        writer.writeheader()
        for lead in leads:
            writer.writerow(to_crm_row(lead))
