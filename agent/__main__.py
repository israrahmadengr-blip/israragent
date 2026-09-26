"""israrads-agent — daily pipeline.

Each run: find new leads (OpenStreetMap, free) -> audit each site's tracking
setup -> draft Email/WhatsApp/LinkedIn/Messenger outreach -> save to
data/leads.csv -> send the email if Gmail is configured -> draft any due
follow-ups. Run with:  python -m agent
"""
from __future__ import annotations
import sys
import time

from . import config, niches, osm_source, site_audit, writer, store, emailer, crm_export


def log(msg: str) -> None:
    print(f"[israrads-agent] {msg}", flush=True)


def run_once() -> dict:
    cfg = config.load_settings()
    rows = store.load(cfg.leads_csv_path)
    seen_ids = store.existing_osm_ids(rows)

    stats = {"raw_found": 0, "new_leads": 0, "emails_sent": 0, "followups_drafted": 0, "errors": []}

    targets = niches.cities_for(cfg.target_countries)
    if not targets:
        stats["errors"].append(f"No cities configured for TARGET_COUNTRIES={cfg.target_countries}")
        return _finish(cfg, rows, stats)

    new_leads_this_run = 0
    for niche in cfg.niches:
        tag_filters = niches.filters_for(niche)
        if not tag_filters:
            stats["errors"].append(f"Unknown niche '{niche}' — skipped (add it to agent/niches.py)")
            continue
        for country, city, lat, lon in targets:
            if new_leads_this_run >= cfg.max_new_leads_per_day:
                break
            try:
                places = osm_source.search(lat, lon, cfg.search_radius_m, tag_filters)
            except osm_source.OverpassError as e:
                stats["errors"].append(f"{niche} near {city}: {e}")
                continue
            stats["raw_found"] += len(places)

            for place in places:
                if new_leads_this_run >= cfg.max_new_leads_per_day:
                    break
                if place["osm_id"] in seen_ids:
                    continue

                audit_result = site_audit.audit(place["website"], timeout=cfg.request_timeout)
                pains = site_audit.pain_points(audit_result)
                drafts = writer.build_drafts(place["name"], place["website"], pains, cfg)
                drafts["pain_summary"] = "; ".join(pains) if pains else "No major gaps found"

                row = store.new_row(place["name"], niche, country, city, place["website"],
                                     place["phone"], audit_result, drafts, place["osm_id"])
                rows.append(row)
                seen_ids.add(place["osm_id"])
                new_leads_this_run += 1

                if row["email"] and stats["emails_sent"] < cfg.max_emails_per_day:
                    try:
                        sent = emailer.send(row["email"], row["email_subject"], row["email_draft"],
                                             cfg.gmail_address, cfg.gmail_app_password)
                        if sent:
                            row["status"] = store.STATUS_CONTACTED
                            row["email_sent_date"] = row["date_found"]
                            stats["emails_sent"] += 1
                    except Exception as e:  # noqa: BLE001 - never let one bad send kill the run
                        stats["errors"].append(f"Email to {row['email']}: {e}")

                time.sleep(cfg.seconds_between_site_fetches)

    stats["new_leads"] = new_leads_this_run

    # ---- follow-ups for leads that went quiet ----
    due = store.due_for_followup(rows, cfg.followup_after_days, cfg.max_followups_total)
    for row in due[: cfg.max_followups_per_day]:
        pains = row.get("pain_summary", "").split("; ")
        drafts = writer.build_drafts(row["business_name"], row["website"], pains, cfg)
        row["email_draft"] = ("Following up on my earlier note — " + drafts["email_body"].split("\n\n", 1)[-1])
        row["whatsapp_draft"] = "Just following up — " + drafts["whatsapp"]
        row["followup_count"] = str(int(row.get("followup_count") or 0) + 1)
        from datetime import date
        row["last_followup_date"] = date.today().isoformat()
        row["status"] = store.STATUS_FOLLOWED_UP
        stats["followups_drafted"] += 1

    return _finish(cfg, rows, stats)


def _finish(cfg, rows, stats) -> dict:
    to_sync = store.unsynced_for_crm(rows)
    crm_export.write_crm_csv(cfg.crm_import_csv_path, to_sync)
    store.mark_crm_synced(to_sync)  # mutates the same row dicts referenced in `rows`
    store.save(cfg.leads_csv_path, rows)
    stats["crm_synced"] = len(to_sync)
    log(f"Raw found: {stats['raw_found']} | New leads: {stats['new_leads']} | "
        f"Emails sent: {stats['emails_sent']} | Follow-ups drafted: {stats['followups_drafted']} | "
        f"New in crm_import.csv: {stats['crm_synced']}")
    for err in stats["errors"]:
        log(f"NOTE: {err}")
    return stats


def selftest() -> int:
    """Checks the pieces work without doing a real run (no network calls that matter)."""
    cfg = config.load_settings()
    log(f"Config OK. Niches: {cfg.niches} | Countries: {cfg.target_countries}")
    log(f"Gmail sending: {'configured' if cfg.gmail_address else 'not configured (drafts only)'}")
    log(f"Gemini writing: {'configured' if cfg.gemini_api_key else 'not configured (using templates)'}")
    targets = niches.cities_for(cfg.target_countries)
    log(f"City targets resolved: {len(targets)}")
    if not targets:
        log("PROBLEM: no cities for your TARGET_COUNTRIES — check agent/niches.py")
        return 1
    for n in cfg.niches:
        if not niches.filters_for(n):
            log(f"PROBLEM: niche '{n}' has no OSM filters defined in agent/niches.py")
            return 1
    log("Selftest passed.")
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if mode == "selftest":
        sys.exit(selftest())
    else:
        run_once()
