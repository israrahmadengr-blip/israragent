# israragent — israrads Lead Agent (v2)

Automated lead finder + outreach drafter for israrads.com. Runs daily on
GitHub Actions (free tier). **Everything is free — no paid APIs, no paid data.**

## What it hunts (retargeted 2026-10-21)
ONLINE businesses only — **e-commerce / D2C stores** and **lead-gen /
high-ticket service businesses** in US, UK, Canada, Australia, NZ, UAE.
It does NOT find local map-pin businesses and does NOT sell local SEO.

## How each daily run works
1. **Discover** (`agent/discover.py`) — candidates from `data/targets.csv`
   (domains queued by Israr) + public web search (`agent/verticals.py`
   rotating niche queries for stores and service businesses).
2. **Audit** (`agent/site_audit.py`) — platform fingerprint (Shopify /
   WooCommerce / Wix / Squarespace / WordPress), real-store and booking
   signals, and the tracking checks: GA4, GTM, Meta Pixel, Google Ads tag,
   HTTPS, AI-crawler blocks.
3. **Enrich** (`agent/enrich.py`) — decision-maker (founder/owner/CEO) name,
   role and email from the business's own About/Team/Contact pages. Emails are
   labelled `found`, `pattern-guessed` or `generic` — never faked as verified.
4. **Ad check** (`agent/ads_check.py`) — Meta Ad Library verification,
   tri-state (Yes / No / Unknown). Unknown is never treated as "not running".
5. **Score** (`agent/scoring.py`) — 1–5 from verified signals only: running
   ads +2, tracking gaps +1, named decision-maker +1, growth signals +1.
6. **Draft + send** — personalized outreach (Email/WhatsApp/LinkedIn/
   Messenger); when Gmail is configured, the best-scoring leads are emailed
   first, up to the daily cap.
7. **Follow-ups** (`agent/writer.py` + `store.followup_stage_due`) — FU1 day 4
   (bump), FU2 day 8 (fresh audit angle), FU3 day 14 (breakup), then the lead
   is auto-closed. Sent automatically when Gmail is configured.
8. **Export** — new leads are written to `data/crm_import.csv` in the exact
   23-column format the israrads CRM imports, and committed back to the repo.

## Guardrails
- `data/blocklist.csv` — domains never contacted. Seeded with the 730 domains
  already emailed by Israr's main outreach system, so the two machines never
  double-email the same brand. Dedup also runs against `data/leads.csv` by
  domain.
- Daily caps on new leads, emails and follow-ups (see `agent/config.py`).
- The pre-retarget local-business leads are preserved in
  `data/leads_local_business_archive.csv`; `agent/osm_source.py` and
  `agent/niches.py` are the retired v1 finder and are no longer used.

## Configuration
All settings are environment variables (GitHub Actions secrets/variables) —
see `agent/config.py`. Key ones: `VERTICALS` (ecommerce,services),
`TARGET_COUNTRIES`, `MAX_NEW_LEADS_PER_DAY`, `MAX_EMAILS_PER_DAY`,
`FOLLOWUP_DAYS` (4,8,14), `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD` (sending),
`GEMINI_API_KEY` (optional, free tier, for draft rephrasing).

## Tests
`python3 test_pipeline.py`, `python3 test_followups.py`, `python3 test_crm_sync.py`
— all run offline against fakes.
