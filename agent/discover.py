"""Finds candidate ONLINE businesses — no map pins, no local-SEO targets.

Two free sources, in priority order:
  1. data/targets.csv — domains queued by Israr (or pasted from research).
     Columns: website,business_name,vertical,country
  2. Public web search (DuckDuckGo HTML + Bing) using verticals.py queries.
     Best-effort: if a search engine blocks the datacenter IP the run simply
     relies on the targets file and reports it — never crashes.

Returns candidate dicts: {business_name, website, vertical, country, source}.
Dedup by domain happens in __main__ against leads.csv + data/blocklist.csv.
"""
from __future__ import annotations
import csv
import os
import re
from urllib.parse import urlparse, parse_qs, unquote

import requests

from . import verticals

UA = "Mozilla/5.0 (compatible; israrads-agent/2.0; +https://israrads.com)"

BLOCKED_HOSTS = (
    "amazon.", "ebay.", "etsy.com", "facebook.com", "instagram.com", "linkedin.com",
    "youtube.com", "twitter.com", "x.com", "pinterest.", "tiktok.com", "yelp.",
    "trustpilot.", "tripadvisor.", "google.", "bing.com", "duckduckgo.com",
    "shopify.com", "wordpress.com", "wix.com", "squarespace.com", "crunchbase.com",
    "wikipedia.org", "reddit.com", "quora.com", "alibaba.", "aliexpress.",
)


def domain_of(url: str) -> str:
    host = urlparse(url if "://" in url else "https://" + url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _is_candidate_host(host: str) -> bool:
    return bool(host) and "." in host and not any(b in host for b in BLOCKED_HOSTS)


def load_targets(path: str) -> list[dict]:
    if not os.path.isfile(path):
        return []
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            site = (row.get("website") or "").strip()
            if not site:
                continue
            if "://" not in site:
                site = "https://" + site
            out.append({
                "business_name": (row.get("business_name") or "").strip() or domain_of(site),
                "website": site,
                "vertical": (row.get("vertical") or "ecommerce").strip().lower(),
                "country": (row.get("country") or "").strip().upper(),
                "source": "targets-file",
            })
    return out


def _ddg_search(query: str, timeout: int) -> list[str]:
    resp = requests.post("https://html.duckduckgo.com/html/",
                         data={"q": query}, timeout=timeout, headers={"User-Agent": UA})
    if resp.status_code != 200:
        return []
    urls = []
    for m in re.findall(r'class="result__a"[^>]*href="([^"]+)"', resp.text):
        qs = parse_qs(urlparse(m).query)
        target = qs.get("uddg", [m])[0]
        urls.append(unquote(target))
    return urls


def _bing_search(query: str, timeout: int) -> list[str]:
    resp = requests.get("https://www.bing.com/search", params={"q": query},
                        timeout=timeout, headers={"User-Agent": UA})
    if resp.status_code != 200:
        return []
    urls = re.findall(r'<h2[^>]*>\s*<a[^>]*href="(https?://[^"]+)"', resp.text)
    return urls


def search_candidates(cfg, day_index: int) -> tuple[list[dict], list[str]]:
    """Best-effort search discovery. Returns (candidates, errors)."""
    errors, out, seen = [], [], set()
    for vertical in cfg.verticals:
        for query, country in verticals.queries_for(vertical, cfg.target_countries, day_index):
            urls = []
            for engine in (_ddg_search, _bing_search):
                try:
                    urls = engine(query, cfg.request_timeout)
                    if urls:
                        break
                except requests.RequestException as e:
                    errors.append(f"search '{query}': {e}")
            for url in urls:
                host = domain_of(url)
                if not _is_candidate_host(host) or host in seen:
                    continue
                seen.add(host)
                out.append({
                    "business_name": host.split(".")[0].replace("-", " ").title(),
                    "website": f"https://{host}",
                    "vertical": vertical, "country": country,
                    "source": "web-search",
                })
    return out, errors


def discover(cfg, day_index: int) -> tuple[list[dict], list[str]]:
    targets = load_targets(cfg.targets_csv_path)
    found, errors = search_candidates(cfg, day_index)
    return targets + found, errors
