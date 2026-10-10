"""UAE site presets used for demos, tests and scenario studies.

Coordinates are approximate (to about 0.01 degree) and elevations are rounded.
They are named locations of operational interest, not endorsements of any
deployment.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Site:
    id: str
    name: str
    emirate: str
    lat: float
    lon: float
    altitude_m: float
    setting: str  # coastal | inland | desert | mountain
    note: str = ""


SITES: dict[str, Site] = {
    s.id: s
    for s in (
        Site(
            "abu_dhabi",
            "Abu Dhabi city",
            "Abu Dhabi",
            24.45,
            54.38,
            10,
            "coastal",
            "Humid coastal heat",
        ),
        Site(
            "masdar",
            "Masdar City",
            "Abu Dhabi",
            24.43,
            54.62,
            10,
            "coastal",
            "Sustainable-city testbed",
        ),
        Site("al_ain", "Al Ain", "Abu Dhabi", 24.21, 55.76, 300, "inland", "Inland oasis city"),
        Site(
            "sweihan",
            "Sweihan solar area",
            "Abu Dhabi",
            24.47,
            55.33,
            200,
            "desert",
            "Large PV plant region; 50 C readings reported in 2026",
        ),
        Site(
            "madinat_zayed",
            "Madinat Zayed / Al Dhafra",
            "Abu Dhabi",
            23.66,
            53.70,
            100,
            "desert",
            "Western region; high PM10 episodes",
        ),
        Site(
            "liwa",
            "Liwa Oasis",
            "Abu Dhabi",
            23.13,
            53.77,
            120,
            "desert",
            "Edge of the Empty Quarter",
        ),
        Site("dubai", "Dubai", "Dubai", 25.20, 55.27, 10, "coastal", "Humid coastal heat"),
        Site(
            "al_maktoum_solar_park",
            "Mohammed bin Rashid Al Maktoum Solar Park",
            "Dubai",
            24.76,
            55.37,
            150,
            "desert",
            "PV robot cleaning region",
        ),
        Site("sharjah", "Sharjah", "Sharjah", 25.35, 55.40, 10, "coastal"),
        Site("ras_al_khaimah", "Ras Al Khaimah", "Ras Al Khaimah", 25.79, 55.94, 10, "coastal"),
        Site(
            "fujairah",
            "Fujairah",
            "Fujairah",
            25.12,
            56.33,
            10,
            "coastal",
            "East coast, Gulf of Oman",
        ),
        Site(
            "jebel_jais_foothills",
            "Jebel Jais foothills",
            "Ras Al Khaimah",
            25.95,
            56.12,
            600,
            "mountain",
        ),
    )
}


def get_site(site_id: str) -> Site:
    try:
        return SITES[site_id]
    except KeyError:
        raise KeyError(f"unknown site '{site_id}'; available: {sorted(SITES)}") from None


def site_ids() -> list[str]:
    return sorted(SITES)
