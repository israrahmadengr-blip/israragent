"""Business types the agent searches for, and the cities it searches around.

Add your own niche any time by adding a line to NICHE_OSM_FILTERS below, and
list it in your NICHES setting (comma-separated). Coordinates are just public
facts (city centers) used to search a radius around each one.
"""
from __future__ import annotations

# niche name -> list of OpenStreetMap Overpass tag filters that describe it.
# You can add more filters per niche, or add new niches entirely.
NICHE_OSM_FILTERS: dict[str, list[str]] = {
    "gym": ['["leisure"="fitness_centre"]'],
    "dentist": ['["amenity"="dentist"]', '["healthcare"="dentist"]'],
    "real estate": ['["office"="estate_agent"]'],
    "restaurant": ['["amenity"="restaurant"]'],
    "law firm": ['["office"="lawyer"]'],
    "med spa": ['["shop"="beauty"]', '["leisure"="spa"]'],
    "chiropractor": ['["healthcare"="chiropractor"]'],
    "physiotherapist": ['["healthcare"="physiotherapist"]'],
    "hair salon": ['["shop"="hairdresser"]'],
    "car repair": ['["shop"="car_repair"]'],
    "accountant": ['["office"="accountant"]'],
    "insurance": ['["office"="insurance"]'],
    "veterinary": ['["amenity"="veterinary"]'],
    "optician": ['["shop"="optician"]'],
    "architect": ['["office"="architect"]'],
    "hotel": ['["tourism"="hotel"]'],
    "travel agency": ['["office"="travel_agent"]'],
    "furniture store": ['["shop"="furniture"]'],
    "electronics store": ['["shop"="electronics"]'],
    "clinic": ['["amenity"="clinic"]', '["healthcare"="clinic"]'],
}

# country -> list of (city name, latitude, longitude). Add more any time.
# Priority order: USA, UK, Canada, Australia, New Zealand, UAE — matches Israr's
# actual target market. TARGET_COUNTRIES in config.py controls both which of
# these are searched AND the priority order (earlier countries get searched,
# and therefore fill the daily lead quota, first).
CITIES: dict[str, list[tuple[str, float, float]]] = {
    "US": [
        ("New York", 40.7128, -74.0060), ("Los Angeles", 34.0522, -118.2437),
        ("Chicago", 41.8781, -87.6298), ("Houston", 29.7604, -95.3698),
        ("Miami", 25.7617, -80.1918), ("Austin", 30.2672, -97.7431),
        ("San Francisco", 37.7749, -122.4194), ("Dallas", 32.7767, -96.7970),
        ("Atlanta", 33.7490, -84.3880), ("Phoenix", 33.4484, -112.0740),
    ],
    "GB": [
        ("London", 51.5074, -0.1278), ("Manchester", 53.4808, -2.2426),
        ("Birmingham", 52.4862, -1.8904), ("Leeds", 53.8008, -1.5491),
        ("Glasgow", 55.8642, -4.2518), ("Bristol", 51.4545, -2.5879),
    ],
    "CA": [
        ("Toronto", 43.6532, -79.3832), ("Vancouver", 49.2827, -123.1207),
        ("Montreal", 45.5017, -73.5673), ("Calgary", 51.0447, -114.0719),
    ],
    "AU": [
        ("Sydney", -33.8688, 151.2093), ("Melbourne", -37.8136, 144.9631),
        ("Brisbane", -27.4698, 153.0251), ("Perth", -31.9505, 115.8605),
    ],
    "NZ": [
        ("Auckland", -36.8485, 174.7633), ("Wellington", -41.2865, 174.7762),
        ("Christchurch", -43.5321, 172.6362), ("Hamilton", -37.7870, 175.2793),
        ("Tauranga", -37.6878, 176.1651),
    ],
    "AE": [
        ("Dubai", 25.2048, 55.2708), ("Abu Dhabi", 24.4539, 54.3773),
        ("Sharjah", 25.3463, 55.4209),
    ],
}


def filters_for(niche: str) -> list[str]:
    return NICHE_OSM_FILTERS.get(niche.strip().lower(), [])


def cities_for(countries: list[str]) -> list[tuple[str, str, float, float]]:
    """Returns (country, city, lat, lon) tuples for the given country codes."""
    out = []
    for cc in countries:
        for city, lat, lon in CITIES.get(cc.upper(), []):
            out.append((cc.upper(), city, lat, lon))
    return out
