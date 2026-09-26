"""Reads settings from environment variables (set as GitHub Actions secrets/variables).

Every setting has a sensible default so the agent runs out of the box; you only need
to set the ones you want to change. See README.md for the full list explained.
"""
from __future__ import annotations
import os


def _get(key: str, default: str = "") -> str:
    val = os.environ.get(key, "")
    return val.strip() if val.strip() else default


def _get_int(key: str, default: int) -> int:
    try:
        return int(_get(key, str(default)))
    except ValueError:
        return default


def _get_list(key: str, default: str) -> list[str]:
    return [x.strip() for x in _get(key, default).split(",") if x.strip()]


class Settings:
    # ---- who you are (used in drafted messages) ----
    @property
    def sender_name(self) -> str: return _get("SENDER_NAME", "Israr Ahmad")
    @property
    def sender_title(self) -> str: return _get("SENDER_TITLE", "Performance Marketing — Google Ads, Meta Ads & Tracking")
    @property
    def sender_email(self) -> str: return _get("SENDER_EMAIL", "contact@israrads.com")
    @property
    def sender_phone(self) -> str: return _get("SENDER_PHONE", "+92 303 5995553")
    @property
    def sender_website(self) -> str: return _get("SENDER_WEBSITE", "israrads.com")

    # ---- what to search for ----
    @property
    def niches(self) -> list[str]:
        return _get_list("NICHES", "gym,dentist,real estate,restaurant,law firm")
    @property
    def target_countries(self) -> list[str]:
        # Order matters: earlier countries fill the daily lead quota first.
        # Default priority: USA, UK, Canada, Australia, New Zealand, UAE.
        return [c.upper() for c in _get_list("TARGET_COUNTRIES", "US,GB,CA,AU,NZ,AE")]
    @property
    def search_radius_m(self) -> int: return _get_int("SEARCH_RADIUS_M", 15000)

    # ---- daily limits (keep these low at first; raise once you trust it) ----
    @property
    def max_new_leads_per_day(self) -> int: return _get_int("MAX_NEW_LEADS_PER_DAY", 15)
    @property
    def max_emails_per_day(self) -> int: return _get_int("MAX_EMAILS_PER_DAY", 10)
    @property
    def max_followups_per_day(self) -> int: return _get_int("MAX_FOLLOWUPS_PER_DAY", 10)
    @property
    def followup_after_days(self) -> int: return _get_int("FOLLOWUP_AFTER_DAYS", 4)
    @property
    def max_followups_total(self) -> int: return _get_int("MAX_FOLLOWUPS_TOTAL", 2)

    # ---- optional: real email sending via Gmail SMTP (leave blank to skip sending) ----
    @property
    def gmail_address(self) -> str: return _get("GMAIL_ADDRESS", "")
    @property
    def gmail_app_password(self) -> str: return _get("GMAIL_APP_PASSWORD", "")

    # ---- optional: Gemini AI writing (free tier). Leave blank to use plain templates. ----
    @property
    def gemini_api_key(self) -> str: return _get("GEMINI_API_KEY", "")

    # ---- housekeeping ----
    @property
    def leads_csv_path(self) -> str: return _get("LEADS_CSV_PATH", "data/leads.csv")
    @property
    def crm_import_csv_path(self) -> str: return _get("CRM_IMPORT_CSV_PATH", "data/crm_import.csv")
    @property
    def state_json_path(self) -> str: return _get("STATE_JSON_PATH", "data/state.json")
    @property
    def request_timeout(self) -> int: return _get_int("REQUEST_TIMEOUT_SECONDS", 12)
    @property
    def seconds_between_site_fetches(self) -> float:
        try:
            return float(_get("SECONDS_BETWEEN_SITE_FETCHES", "2"))
        except ValueError:
            return 2.0


def load_settings() -> Settings:
    return Settings()
