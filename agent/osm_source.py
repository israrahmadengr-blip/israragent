"""Finds businesses with a website listed on OpenStreetMap, via the free public
Overpass API. No account, no API key, no billing — anyone can query this.

OpenStreetMap data is community-maintained, so coverage varies by city and niche;
that's a real limitation (see README), not a bug.
"""
from __future__ import annotations
import requests

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


class OverpassError(Exception):
    pass


def _build_query(lat: float, lon: float, radius_m: int, tag_filters: list[str], limit: int) -> str:
    parts = []
    for tag_filter in tag_filters:
        for website_key in ("website", "contact:website"):
            parts.append(f'nwr{tag_filter}["{website_key}"](around:{radius_m},{lat},{lon});')
    body = "".join(parts)
    return f"[out:json][timeout:50];({body});out center tags {limit};"


def _first_tag(tags: dict, *keys: str) -> str:
    for k in keys:
        v = tags.get(k)
        if v and str(v).strip():
            return str(v).strip().split(";")[0].strip()
    return ""


def search(lat: float, lon: float, radius_m: int, tag_filters: list[str], limit: int = 60,
           timeout: int = 40) -> list[dict]:
    """Returns a list of {name, website, phone, osm_id} dicts. Empty list on failure —
    callers should treat that as 'try again another day', not a crash."""
    if not tag_filters:
        return []
    query = _build_query(lat, lon, radius_m, tag_filters, limit)
    last_error = None
    for endpoint in ENDPOINTS:
        try:
            resp = requests.post(endpoint, data={"data": query}, timeout=timeout,
                                  headers={"User-Agent": "israrads-agent/1.0 (+https://israrads.com)"})
            if resp.status_code != 200:
                last_error = f"HTTP {resp.status_code} from {endpoint}"
                continue
            data = resp.json()
            out = []
            for el in data.get("elements", []):
                tags = el.get("tags") or {}
                name = _first_tag(tags, "name", "brand", "operator")
                website = _first_tag(tags, "website", "contact:website")
                phone = _first_tag(tags, "phone", "contact:phone")
                if not name or not website:
                    continue
                if not website.lower().startswith(("http://", "https://")):
                    website = "https://" + website
                out.append({"name": name, "website": website, "phone": phone,
                            "osm_id": f"{el.get('type','')}/{el.get('id','')}"})
            return out
        except (requests.RequestException, ValueError) as e:
            last_error = str(e)
            continue
    raise OverpassError(last_error or "all Overpass endpoints failed")
