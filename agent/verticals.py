"""What the agent hunts now (Israr's 2026-10-21 retarget): ONLINE businesses —
e-commerce / D2C stores and lead-gen / high-ticket SERVICE businesses in
US, GB, CA, AU, NZ, AE. NOT local map-pin businesses and NOT local SEO.

Each vertical defines web-search query templates used by discover.py. Queries
rotate by day so the agent doesn't hammer the same corner of the web twice.
Everything here is free: public search-result pages + the businesses' own sites.
"""
from __future__ import annotations

ECOMMERCE_NICHES = [
    "fashion boutique", "skincare brand", "beauty products", "supplements brand",
    "pet products", "homeware", "jewellery", "fitness equipment", "baby products",
    "coffee brand", "candle brand", "activewear", "shoe store", "watch brand",
]

SERVICES_NICHES = [
    "immigration consultants", "mortgage brokers", "real estate agency",
    "travel agency", "car rental", "solar installers", "roofing company",
    "online tutoring", "wedding venue", "moving company", "aesthetic clinic",
    "business coaching", "wedding planner", "home renovation",
]

COUNTRY_TERMS = {
    "US": ("United States", ""), "GB": ("UK", ".co.uk"), "CA": ("Canada", ".ca"),
    "AU": ("Australia", ".com.au"), "NZ": ("New Zealand", ".co.nz"), "AE": ("UAE", ".ae"),
}

_ECOM_TEMPLATES = [
    '"powered by shopify" {niche} {country_term}',
    '"powered by shopify" {niche} site:{tld}' ,
    'woocommerce store {niche} {country_term}',
    '{niche} online store {country_term} "add to cart"',
]
_SERVICES_TEMPLATES = [
    '{niche} {country_term} "book a consultation"',
    '{niche} {country_term} "get a free quote"',
    '{niche} {country_term} "book online" services',
]


def niches_for(vertical: str) -> list[str]:
    return ECOMMERCE_NICHES if vertical == "ecommerce" else SERVICES_NICHES


def queries_for(vertical: str, countries: list[str], day_index: int, per_country: int = 2) -> list[tuple[str, str]]:
    """Returns [(query, country_code)] — a rotating slice so each day differs."""
    templates = _ECOM_TEMPLATES if vertical == "ecommerce" else _SERVICES_TEMPLATES
    niches = niches_for(vertical)
    out = []
    for ci, country in enumerate(countries):
        term, tld = COUNTRY_TERMS.get(country, (country, ""))
        for k in range(per_country):
            niche = niches[(day_index + ci * per_country + k) % len(niches)]
            tpl = templates[(day_index + k) % len(templates)]
            q = tpl.format(niche=niche, country_term=term, tld=(tld or ".com"))
            out.append((q, country))
    return out
