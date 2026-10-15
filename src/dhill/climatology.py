"""Operating calendar: how often a robot's envelope allows work, from real weather history.

For each site and calendar month the module draws a stratified sample of days from the
historical record (days at fixed quantiles of the daily maximum air temperature), runs
hourly missions through the existing :class:`Envelope`, and reports the share of hours
that are GO, DERATE and PARK. It also reports how often the air temperature alone is above
a manufacturer's rated ambient limit, counted over every hour of the record.

The history is reanalysis (Open-Meteo archive, ERA5 family) and CAMS PM10, not station
data. The robot profile is whatever the caller supplies; for the bundled profiles that is
an L0 profile, so the output demonstrates the method and is not an operating authorisation.
"""

from __future__ import annotations

import csv
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx
import numpy as np

from .envelope import EngineConfig, Envelope
from .profiles.schema import Profile
from .sites import Site, get_site
from .weather.base import Weather
from .weather.openmeteo import (
    _WX_VARS,
    AIR_URL,
    ARCHIVE_URL,
    WeatherUnavailable,
    _fill,
    _get,
    _hourly,
)

#: Daily maximum quantiles used to pick representative days within a month.
DEFAULT_QUANTILES = (0.1, 0.3, 0.5, 0.7, 0.9)
#: Archive data do not change, so cached responses are kept for ten years.
ARCHIVE_TTL_S = 10 * 365 * 86400.0
#: Local daytime (UAE is UTC+4) expressed in UTC hours, used for the daytime exceedance share.
DAY_UTC_HOURS = tuple(range(4, 15))  # 08:00 to 18:00 local, inclusive of 08 and 18


def _get_retry(
    url: str,
    params: dict,
    client: httpx.Client | None,
    retries: int = 6,
    base_s: float = 2.0,
    sleep=time.sleep,
) -> dict:
    """Cached request with exponential backoff (the free API rate limits with HTTP 429)."""
    last: Exception | None = None
    for k in range(retries):
        try:
            return _get(url, params, ttl_s=ARCHIVE_TTL_S, client=client)
        except WeatherUnavailable as exc:
            last = exc
            sleep(base_s * 2**k)
    raise WeatherUnavailable(f"gave up after {retries} attempts: {last}")


def fetch_history(
    site: Site | str,
    first_year: int,
    last_year: int,
    client: httpx.Client | None = None,
    sleep=time.sleep,
) -> Weather:
    """Hourly UTC history for ``first_year..last_year``, fetched one year at a time.

    A year that cannot be retrieved is left out and named in ``notes``; weather is never
    invented to fill a gap. PM10 that cannot be retrieved for a year is set to 80 ug/m3 and
    the year is named in ``notes``.
    """
    s = get_site(site) if isinstance(site, str) else site
    parts: list[tuple[np.ndarray, dict[str, np.ndarray], np.ndarray]] = []
    notes: list[str] = []
    for y in range(first_year, last_year + 1):
        p = {
            "latitude": s.lat,
            "longitude": s.lon,
            "start_date": f"{y}-01-01",
            "end_date": f"{y}-12-31",
            "timezone": "UTC",
        }
        try:
            wx = _get_retry(
                ARCHIVE_URL, {**p, "hourly": _WX_VARS, "wind_speed_unit": "ms"}, client, sleep=sleep
            )
            t, c = _hourly(wx)
        except WeatherUnavailable as exc:
            notes.append(f"{y}: weather unavailable ({exc}); year excluded")
            continue
        pm = np.full(t.shape, np.nan)
        try:
            aq = _get_retry(AIR_URL, {**p, "hourly": "pm10,dust"}, client, sleep=sleep)
            t_a, c_a = _hourly(aq)
            pm_a = np.fmax(
                c_a.get("pm10", np.full(t_a.shape, np.nan)),
                c_a.get("dust", np.full(t_a.shape, np.nan)),
            )
            lookup = {tt: v for tt, v in zip(t_a, pm_a, strict=True)}
            pm = np.array([lookup.get(tt, np.nan) for tt in t], dtype=float)
        except WeatherUnavailable as exc:
            notes.append(f"{y}: PM10 unavailable ({exc}); 80 ug/m3 assumed")
        parts.append((t, c, pm))
    if not parts:
        raise WeatherUnavailable(f"{s.id}: no year of history could be retrieved")
    times = np.concatenate([p[0] for p in parts])
    col = {k: np.concatenate([p[1][k] for p in parts]) for k in parts[0][1]}
    pm10 = np.concatenate([p[2] for p in parts])
    n_missing = int(np.sum(~np.isfinite(pm10)))
    if n_missing:
        notes.append(f"PM10 missing for {n_missing} of {pm10.size} hours; filled with 80 ug/m3")
    return Weather(
        times_utc=times,
        t_air_c=_fill(col["temperature_2m"], 30.0),
        dew_c=_fill(col["dew_point_2m"], 15.0),
        wind10_ms=_fill(col["wind_speed_10m"], 3.0),
        pm10_ugm3=np.where(np.isfinite(pm10), pm10, 80.0),
        precip_mm_h=_fill(col["precipitation"], 0.0),
        lat=s.lat,
        lon=s.lon,
        altitude_m=s.altitude_m,
        ghi_wm2=_fill(col["shortwave_radiation"], 0.0),
        source="open-meteo-archive",
        label=s.id,
        notes=["Open-Meteo archive reanalysis, CAMS PM10 (0.4 degree grid)", *notes],
    )


def _slice(w: Weather, i0: int, i1: int) -> Weather:
    """Sub-record ``[i0, i1)`` as a new Weather."""
    return Weather(
        times_utc=w.times_utc[i0:i1],
        t_air_c=w.t_air_c[i0:i1],
        dew_c=w.dew_c[i0:i1],
        wind10_ms=w.wind10_ms[i0:i1],
        pm10_ugm3=w.pm10_ugm3[i0:i1],
        precip_mm_h=w.precip_mm_h[i0:i1],
        lat=w.lat,
        lon=w.lon,
        altitude_m=w.altitude_m,
        ghi_wm2=None if w.ghi_wm2 is None else w.ghi_wm2[i0:i1],
        source=w.source,
        label=w.label,
        notes=list(w.notes),
    )


def _day_starts(w: Weather) -> np.ndarray:
    """Indices of 00:00 UTC samples that have at least three hours before and 27 after."""
    hours = (w.times_utc.astype("datetime64[h]").astype(int)) % 24
    idx = np.where(hours == 0)[0]
    return idx[(idx >= 3) & (idx + 27 < w.n)]


def representative_days(
    w: Weather, month: int, quantiles: tuple[float, ...] = DEFAULT_QUANTILES
) -> list[int]:
    """Sample-start indices of days in ``month`` at quantiles of the daily maximum air temperature.

    The days are chosen over the whole record, so a quantile of 0.9 is a hot day for the
    month in any year, not a specific year.
    """
    starts = _day_starts(w)
    months = w.times_utc[starts].astype("datetime64[M]").astype(int) % 12 + 1
    cand = starts[months == month]
    if cand.size == 0:
        return []
    dmax = np.array([w.t_air_c[i : i + 24].max() for i in cand])
    order = np.argsort(dmax, kind="stable")
    picks = []
    for q in quantiles:
        k = order[int(round(q * (cand.size - 1)))]
        if cand[k] not in picks:
            picks.append(int(cand[k]))
    return picks


@dataclass
class MonthResult:
    site: str
    month: int
    days_sampled: int
    hours_sampled: int
    go: float
    derate: float
    park: float
    mean_scale: float
    air_above_rated: float  # share of all hours in the month, over the record
    air_above_rated_day: float  # same, local daytime only
    air_above_40: float
    hottest_day_max_c: float
    hours_in_record: int


@dataclass
class Calendar:
    profile_id: str
    evidence_level: str
    mode: str
    rated_max_c: float
    first_year: int
    last_year: int
    n_mc: int
    quantiles: tuple[float, ...]
    sigma_scale: float = 1.0
    rows: list[MonthResult] = field(default_factory=list)
    notes: dict[str, list[str]] = field(default_factory=dict)

    def by_site(self, site: str) -> list[MonthResult]:
        return sorted((r for r in self.rows if r.site == site), key=lambda r: r.month)

    def sites(self) -> list[str]:
        return sorted({r.site for r in self.rows})


def month_result(
    profile: Profile,
    w: Weather,
    site: str,
    month: int,
    rated_max_c: float,
    mode: str,
    duration_h: float,
    cfg: EngineConfig,
    quantiles: tuple[float, ...] = DEFAULT_QUANTILES,
) -> MonthResult | None:
    picks = representative_days(w, month, quantiles)
    if not picks:
        return None
    actions: list[str] = []
    scales: list[float] = []
    for i in picks:
        sub = _slice(w, i - 3, i + 27)
        day0 = w.times_utc[i]
        env = Envelope(profile, sub, cfg, site=site)
        tl = env.timeline(
            duration_h=duration_h,
            mode=mode,
            step_min=60.0,
            first_utc=day0,
            last_utc=day0 + np.timedelta64(23, "h"),
        )
        actions += [s.action for s in tl.slots]
        scales += [s.scale for s in tl.slots]
    n = len(actions)
    mon = w.times_utc.astype("datetime64[M]").astype(int) % 12 + 1
    in_month = mon == month
    hours = w.times_utc.astype("datetime64[h]").astype(int) % 24
    day = in_month & np.isin(hours, DAY_UTC_HOURS)
    t = w.t_air_c
    return MonthResult(
        site=site,
        month=month,
        days_sampled=len(picks),
        hours_sampled=n,
        go=actions.count("GO") / n,
        derate=actions.count("DERATE") / n,
        park=actions.count("PARK") / n,
        mean_scale=float(np.mean(scales)),
        air_above_rated=float(np.mean(t[in_month] > rated_max_c)),
        air_above_rated_day=float(np.mean(t[day] > rated_max_c)),
        air_above_40=float(np.mean(t[in_month] > 40.0)),
        hottest_day_max_c=float(
            max(t[i : i + 24].max() for i in _day_starts(w) if mon[i] == month)
        ),
        hours_in_record=int(in_month.sum()),
    )


def operating_calendar(
    profile: Profile,
    histories: dict[str, Weather],
    rated_max_c: float = 45.0,
    mode: str = "drive",
    duration_h: float = 1.0,
    n_mc: int = 64,
    quantiles: tuple[float, ...] = DEFAULT_QUANTILES,
    months: tuple[int, ...] = tuple(range(1, 13)),
    seed: int = 7,
    sigma_scale: float = 1.0,
) -> Calendar:
    """Operating calendar for ``profile`` over the supplied site histories."""
    cfg = EngineConfig(n_mc=n_mc, seed=seed, sigma_scale=sigma_scale)
    any_w = next(iter(histories.values()))
    years = any_w.times_utc.astype("datetime64[Y]").astype(int) + 1970
    cal = Calendar(
        profile_id=profile.id,
        evidence_level=profile.evidence_level,
        mode=mode,
        rated_max_c=rated_max_c,
        first_year=int(years.min()),
        last_year=int(years.max()),
        n_mc=n_mc,
        quantiles=tuple(quantiles),
        sigma_scale=sigma_scale,
    )
    for site, w in histories.items():
        cal.notes[site] = list(w.notes)
        for m in months:
            r = month_result(profile, w, site, m, rated_max_c, mode, duration_h, cfg, quantiles)
            if r is not None:
                cal.rows.append(r)
    return cal


def headline(cal: Calendar, months: tuple[int, ...] = (6, 7, 8, 9)) -> dict:
    """Numbers quoted in documents, computed from the calendar (never typed by hand)."""
    out: dict = {"months": list(months), "sites": {}}
    for site in cal.sites():
        rows = [r for r in cal.by_site(site) if r.month in months]
        if not rows:
            continue
        h = np.array([r.hours_sampled for r in rows], dtype=float)
        out["sites"][site] = {
            "park": float(np.average([r.park for r in rows], weights=h)),
            "derate": float(np.average([r.derate for r in rows], weights=h)),
            "go": float(np.average([r.go for r in rows], weights=h)),
            "air_above_rated": float(
                np.average(
                    [r.air_above_rated for r in rows], weights=[r.hours_in_record for r in rows]
                )
            ),
            "air_above_rated_day": float(
                np.average(
                    [r.air_above_rated_day for r in rows], weights=[r.hours_in_record for r in rows]
                )
            ),
        }
    return out


def write_csv(cal: Calendar, path: str | Path) -> None:
    rows = [asdict(r) for r in cal.rows]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
