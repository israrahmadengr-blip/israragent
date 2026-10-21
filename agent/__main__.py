"""israrads-agent — daily pipeline (v2, retargeted 2026-10-21 by Israr's order).

Each run: find ONLINE businesses (e-commerce/D2C + lead-gen/high-ticket
services — never local map-pin businesses) -> audit tracking + platform ->
find the decision-maker -> verify ad presence -> score 1-5 -> draft outreach
-> save to data/leads.csv -> email the best-scoring leads first -> run the
FU1 day-4 / FU2 day-8 / FU3 day-14-breakup follow-up cadence (then close).
Everything runs on free sources only. Run with:  python -m agent
"""
from __future__ import annotations
import sys
import time
from datetime import date

from . import (ads_check, config, crm_export, discover, emailer, enrich,
               scoring, store, writer)


def log(msg: str) -> None:
    print(f"[israrads-agent] {msg}", flush=True)


def run_once() -> dict:
    cfg = config.load_settings()
    rows = store.load(cfg.leads_csv_path)
    seen_domains = store.existing_domains(rows)
    blocklist = store.load_blocklist(cfg.blocklist_csv_path)

    stats = {"raw_found": 0, "new_leads": 0, "emails_sent": 0, "followups_drafted": 0,
             "followups_sent": 0, "closed": 0, "errors": []}

    day_index = date.today().toordinal()
    candidates, search_errors = discover.discover(cfg, day_index)
    stats["errors"].extend(search_errors)
    stats["raw_found"] = len(candidates)

    new_rows = []
    for cand in candidates:
        if len(new_rows) >= cfg.max_new_leads_per_day:
            break
        domain = discover.domain_of(cand["website"])
        if domain in seen_domains or domain in blocklist:
            continue
        audit_result = site_audit_run(cand["website"], cfg)
        if not audit_result["fetched"]:
            continue
        # vertical fit: e-commerce must look like a store; services must offer booking/quote
        if cand["vertical"] == "ecommerce" and audit_result.get("is_store") != "Yes":
            continue
        if cand["vertical"] == "services" and audit_result.get("has_booking") != "Yes" \
                and audit_result.get("platform") == "Unknown":
            continue
        contact = enrich.enrich(cand["website"], audit_result.get("email", ""), cfg.request_timeout)
        if contact.get("email"):
            audit_result["email"] = contact["email"]
        ads = ads_check.check_ads(cand["business_name"], domain, cfg.request_timeout)
        score, reasons = scoring.score_lead(audit_result, contact, ads)
        pains = site_pain_points(audit_result)
        drafts = writer.build_drafts(cand["business_name"], cand["website"], pains, cfg,
                                     contact_name=contact.get("contact_name", ""))
        drafts["pain_summary"] = "; ".join(pains) if pains else "No major gaps found"
        row = store.new_row(cand["business_name"], cand["vertical"], cand["country"], "",
                            cand["website"], "", audit_result, drafts,
                            f"web:{domain}", contact=contact, score=score,
                            ads_running=ads, source=cand["source"])
        if reasons:
            row["notes"] = f"Score {score}: {reasons}"
        rows.append(row)
        new_rows.append(row)
        seen_domains.add(domain)
        time.sleep(cfg.seconds_between_site_fetches)

    stats["new_leads"] = len(new_rows)

    # ---- send: best-scoring new leads first, within the daily cap ----
    sendable = sorted((r for r in new_rows if r.get("email")),
                      key=lambda r: int(r.get("score") or 0), reverse=True)
    for row in sendable[: cfg.max_emails_per_day]:
        try:
            sent = emailer.send(row["email"], row["email_subject"], row["email_draft"],
                                cfg.gmail_address, cfg.gmail_app_password)
            if sent:
                row["status"] = store.STATUS_CONTACTED
                row["email_sent_date"] = date.today().isoformat()
                stats["emails_sent"] += 1
        except Exception as e:  # noqa: BLE001 - one bad send must not kill the run
            stats["errors"].append(f"Email to {row['email']}: {e}")

    # ---- follow-ups: FU1 d4 / FU2 d8 (fresh angle) / FU3 d14 breakup -> close ----
    due = store.followup_stage_due(rows, cfg.followup_days)
    for row in due[: cfg.max_followups_per_day]:
        stage = int(row.get("followup_count") or 0) + 1
        fresh_pain = ""
        if stage == 2:
            re_audit = site_audit_run(row["website"], cfg)
            new_pains = [p for p in site_pain_points(re_audit)
                         if p not in (row.get("pain_summary") or "")]
            fresh_pain = new_pains[0] if new_pains else ""
        pains = (row.get("pain_summary") or "").split("; ")
        subject, body = writer.build_followup(stage, row["business_name"], row["website"],
                                              pains, cfg,
                                              contact_name=row.get("contact_name", ""),
                                              fresh_pain=fresh_pain)
        sent = False
        if row.get("email"):
            try:
                sent = emailer.send(row["email"], subject, body,
                                    cfg.gmail_address, cfg.gmail_app_password)
            except Exception as e:  # noqa: BLE001
                stats["errors"].append(f"Follow-up to {row['email']}: {e}")
        row["email_subject"], row["email_draft"] = subject, body
        row["followup_count"] = str(stage)
        row["last_followup_date"] = date.today().isoformat()
        if stage >= len(cfg.followup_days):
            row["status"] = store.STATUS_CLOSED
            stats["closed"] += 1
        else:
            row["status"] = store.STATUS_FOLLOWED_UP
        if sent:
            stats["followups_sent"] += 1
        stats["followups_drafted"] += 1

    return _finish(cfg, rows, stats)


def site_audit_run(website: str, cfg) -> dict:
    from . import site_audit
    return site_audit.audit(website, timeout=cfg.request_timeout)


def site_pain_points(audit_result: dict) -> list[str]:
    from . import site_audit
    return site_audit.pain_points(audit_result)


def _finish(cfg, rows, stats) -> dict:
    to_sync = store.unsynced_for_crm(rows)
    crm_export.write_crm_csv(cfg.crm_import_csv_path, to_sync)
    store.mark_crm_synced(to_sync)
    store.save(cfg.leads_csv_path, rows)
    stats["crm_synced"] = len(to_sync)
    log(f"Raw found: {stats['raw_found']} | New leads: {stats['new_leads']} | "
        f"Emails sent: {stats['emails_sent']} | Follow-ups drafted: {stats['followups_drafted']} | "
        f"Follow-ups sent: {stats.get('followups_sent', 0)} | Closed: {stats.get('closed', 0)} | "
        f"New in crm_import.csv: {stats['crm_synced']}")
    for err in stats["errors"]:
        log(f"NOTE: {err}")
    return stats


def selftest() -> int:
    """Checks the pieces work without doing a real run."""
    cfg = config.load_settings()
    log(f"Config OK. Verticals: {cfg.verticals} | Countries: {cfg.target_countries}")
    log(f"Follow-up cadence (days): {cfg.followup_days}")
    log(f"Gmail sending: {'configured' if cfg.gmail_address else 'not configured (drafts only)'}")
    log(f"Gemini writing: {'configured' if cfg.gemini_api_key else 'not configured (using templates)'}")
    log(f"Targets file rows: {len(discover.load_targets(cfg.targets_csv_path))}")
    log(f"Blocklist domains loaded: {len(store.load_blocklist(cfg.blocklist_csv_path))}")
    log("Selftest passed.")
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if mode == "selftest":
        sys.exit(selftest())
    else:
        run_once()
