"""Operating calendar: how many hours per site and month a profile is GO, DERATE or PARK.

Recorded weather comes from the Open-Meteo historical archive (reanalysis, hourly, UTC) and
CAMS PM10 from the Open-Meteo air quality API. Every response is cached on disk, one file per
site and year, so an interrupted download resumes where it stopped. HTTP 429 and server errors
are retried with exponential backoff. A year that cannot be downloaded is reported as a gap;
no weather is ever invented to fill it.

Method, per site and calendar month:

1. Daily maximum air temperature for every complete local day (UTC+4) in the record.
2. Representative days at the 10th, 30th, 50th, 70th and 90th percentile of daily maximum.
   Each stands for a 20 % band of days, so the five carry equal weight in the hour shares.
   The hottest and the mildest day are run as well and reported as bounds, not weighted.
3. For each representative day, 24 one hour missions (drive mode, full scale requested),
   one starting at every local hour, through the existing ``Envelope``. GO, DERATE and PARK
   follow the engine's own rule (scale 1, between 0 and 1, 0).
4. Separately, the share of every recorded hour whose air temperature exceeds the
   manufacturer's rated ambient, counted over the full record, not only the sampled days.

PM10 from CAMS is used where the API returns it (from August 2022). Earlier hours take the
median CAMS PM10 for the same site, month and local hour over the available years; those
hours are flagged ``pm10_source = cams_hourly_median`` in the output.
"""

from __future__ import annotations

import calendar as _cal
import csv
import json
import os
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import numpy as np

from .envelope import EngineConfig, Envelope
from .profiles.schema import Profile
from .sites import Site, get_site
from .weather.base import Weather
from .weather.openmeteo import AIR_URL, ARCHIVE_URL, WeatherUnavailable

DEFAULT_SITES = ("abu_dhabi", "al_ain", "dubai", "sweihan", "liwa", "fujairah")
DEFAULT_YEARS = tuple(range(2015, 2026))
LOCAL_OFFSET_H = 4  # Gulf Standard Time, no daylight saving
QUANTILES = (0.1, 0.3, 0.5, 0.7, 0.9)
WX_VARS = "temperature_2m,dew_point_2m,wind_speed_10m,shortwave_radiation,precipitation"
PM_FIRST_YEAR = 2022  # CAMS through the air quality API is null before August 2022
ACTIONS = ("GO", "DERATE", "PARK")


# ---------------------------------------------------------------------- download and cache
def cache_dir(root: Path | None = None) -> Path:
    """``<root>/climatology``; root defaults to ``$DHILL_CACHE_DIR`` or ``~/.cache/dhill``."""
    root = root or Path(os.environ.get("DHILL_CACHE_DIR", Path.home() / ".cache" / "dhill"))
    d = Path(root) / "climatology"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_json_cached(
    url: str,
    params: dict,
    path: Path,
    client: httpx.Client | None = None,
    max_tries: int = 7,
    base_wait_s: float = 10.0,
    sleep: Callable[[float], None] = time.sleep,
    offline: bool = False,
) -> dict:
    """Return the cached response at ``path`` or download it with exponential backoff.

    The file is written atomically, so a partial download never poisons the cache.
    Raises ``WeatherUnavailable`` when the response cannot be obtained.
    """
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if offline:
        raise WeatherUnavailable(f"not cached and offline: {path.name}")
    own = client is None
    client = client or httpx.Client(timeout=90.0)
    last = "no attempt"
    try:
        for attempt in range(max_tries):
            try:
                r = client.get(url, params=params)
            except httpx.HTTPError as exc:
                last = str(exc)
                sleep(base_wait_s * 2**attempt)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                last = f"HTTP {r.status_code}"
                sleep(base_wait_s * 2**attempt)
                continue
            if r.status_code >= 400:
                raise WeatherUnavailable(f"{url}: HTTP {r.status_code} {r.text[:200]}")
            data = r.json()
            if data.get("error"):
                raise WeatherUnavailable(f"{url}: {data.get('reason', 'error')}")
            tmp = path.with_suffix(".part")
            tmp.write_text(json.dumps(data), encoding="utf-8")
            tmp.replace(path)
            return data
    finally:
        if own:
            client.close()
    raise WeatherUnavailable(f"{url}: gave up after {max_tries} tries ({last})")


def _archive_params(s: Site, year: int) -> dict:
    return {
        "latitude": s.lat,
        "longitude": s.lon,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "timezone": "UTC",
        "hourly": WX_VARS,
        "wind_speed_unit": "ms",
    }


def _air_params(s: Site, year: int) -> dict:
    return {
        "latitude": s.lat,
        "longitude": s.lon,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "timezone": "UTC",
        "hourly": "pm10,dust",
    }


@dataclass
class SiteRecord:
    """Hourly recorded weather for one site over the requested years (UTC)."""

    site: Site
    times_utc: np.ndarray
    t_air_c: np.ndarray
    dew_c: np.ndarray
    wind10_ms: np.ndarray
    ghi_wm2: np.ndarray
    precip_mm_h: np.ndarray
    pm10_ugm3: np.ndarray  # NaN where CAMS returned nothing
    gaps: list[str] = field(default_factory=list)

    @property
    def local_times(self) -> np.ndarray:
        return self.times_utc + np.timedelta64(LOCAL_OFFSET_H, "h")


def _col(h: dict, key: str, n: int) -> np.ndarray:
    vals = h.get(key)
    if vals is None:
        return np.full(n, np.nan)
    return np.array([np.nan if v is None else v for v in vals], dtype=float)


def parse_archive(data: dict) -> dict[str, np.ndarray]:
    h = data.get("hourly") or {}
    if "time" not in h:
        raise WeatherUnavailable("archive response has no hourly block")
    t = np.array(h["time"], dtype="datetime64[s]")
    n = t.size
    return {
        "time": t,
        "t_air_c": _col(h, "temperature_2m", n),
        "dew_c": _col(h, "dew_point_2m", n),
        "wind10_ms": _col(h, "wind_speed_10m", n),
        "ghi_wm2": _col(h, "shortwave_radiation", n),
        "precip_mm_h": _col(h, "precipitation", n),
    }


def parse_air(data: dict) -> tuple[np.ndarray, np.ndarray]:
    h = data.get("hourly") or {}
    if "time" not in h:
        raise WeatherUnavailable("air quality response has no hourly block")
    t = np.array(h["time"], dtype="datetime64[s]")
    pm = np.fmax(_col(h, "pm10", t.size), _col(h, "dust", t.size))
    return t, pm


def load_site_record(
    site: Site | str,
    years: Iterable[int] = DEFAULT_YEARS,
    client: httpx.Client | None = None,
    offline: bool = False,
    pause_s: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] | None = None,
    cache_root: Path | None = None,
) -> SiteRecord:
    """Assemble the hourly record for one site, downloading missing years (resumable)."""
    s = get_site(site) if isinstance(site, str) else site
    root = cache_dir(cache_root)
    parts: list[dict[str, np.ndarray]] = []
    pm_t: list[np.ndarray] = []
    pm_v: list[np.ndarray] = []
    gaps: list[str] = []
    for y in years:
        p = root / f"archive_{s.id}_{y}.json"
        fresh = not p.exists()
        try:
            parts.append(
                parse_archive(
                    get_json_cached(
                        ARCHIVE_URL, _archive_params(s, y), p, client, sleep=sleep, offline=offline
                    )
                )
            )
            if log and fresh:
                log(f"downloaded archive {s.id} {y}")
        except WeatherUnavailable as exc:
            gaps.append(f"{s.id} {y}: weather not available ({exc})")
            continue
        if fresh and not offline:
            sleep(pause_s)
        if y < PM_FIRST_YEAR:
            continue
        p = root / f"air_{s.id}_{y}.json"
        fresh = not p.exists()
        try:
            t, pm = parse_air(
                get_json_cached(AIR_URL, _air_params(s, y), p, client, sleep=sleep, offline=offline)
            )
            pm_t.append(t)
            pm_v.append(pm)
        except WeatherUnavailable as exc:
            gaps.append(f"{s.id} {y}: PM10 not available ({exc})")
        if fresh and not offline:
            sleep(pause_s)
    if not parts:
        raise WeatherUnavailable(f"no weather for {s.id}: " + "; ".join(gaps))
    cat = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    pm10 = np.full(cat["time"].size, np.nan)
    if pm_t:
        lookup = dict(zip(np.concatenate(pm_t), np.concatenate(pm_v), strict=True))
        pm10 = np.array([lookup.get(t, np.nan) for t in cat["time"]], dtype=float)
    return SiteRecord(
        site=s,
        times_utc=cat["time"],
        t_air_c=cat["t_air_c"],
        dew_c=cat["dew_c"],
        wind10_ms=cat["wind10_ms"],
        ghi_wm2=cat["ghi_wm2"],
        precip_mm_h=cat["precip_mm_h"],
        pm10_ugm3=pm10,
        gaps=gaps,
    )


def record_weather(rec: SiteRecord) -> Weather:
    """The whole record as one ``Weather``; PM10 must be present for every hour."""
    if not np.isfinite(rec.pm10_ugm3).all():
        raise WeatherUnavailable(f"{rec.site.id}: PM10 missing for some hours")
    return Weather(
        times_utc=rec.times_utc,
        t_air_c=rec.t_air_c,
        dew_c=rec.dew_c,
        wind10_ms=rec.wind10_ms,
        pm10_ugm3=rec.pm10_ugm3,
        precip_mm_h=rec.precip_mm_h,
        lat=rec.site.lat,
        lon=rec.site.lon,
        altitude_m=rec.site.altitude_m,
        ghi_wm2=rec.ghi_wm2,
        source="open-meteo-archive",
        label=rec.site.id,
    )


def fixture_weather(data_dir: Path, site: str = "abu_dhabi", year: int = 2024) -> Weather:
    """Recorded weather from cached responses in ``data_dir`` (files named as in the cache)."""
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        d = cache_dir(Path(tmp))
        for f in Path(data_dir).glob(f"*_{site}_{year}.json"):
            shutil.copy(f, d / f.name)
        rec = load_site_record(site, (year,), offline=True, cache_root=Path(tmp))
    return record_weather(rec)


# ---------------------------------------------------------------------- day selection
def daily_max_by_local_day(rec: SiteRecord) -> tuple[np.ndarray, np.ndarray]:
    """Local dates with 24 valid hourly temperatures, and their maximum air temperature."""
    days = rec.local_times.astype("datetime64[D]")
    uniq, inv, counts = np.unique(days, return_inverse=True, return_counts=True)
    tmax = np.full(uniq.size, -np.inf)
    valid = np.zeros(uniq.size, dtype=int)
    ok = np.isfinite(rec.t_air_c)
    np.maximum.at(tmax, inv[ok], rec.t_air_c[ok])
    np.add.at(valid, inv, ok.astype(int))
    keep = (counts == 24) & (valid == 24)
    return uniq[keep], tmax[keep]


def month_of(days: np.ndarray) -> np.ndarray:
    return (days.astype("datetime64[M]").astype(int) % 12) + 1


def select_days(
    days: np.ndarray, tmax: np.ndarray, month: int, quantiles=QUANTILES
) -> list[tuple[str, np.datetime64, float, float]]:
    """Representative days for one calendar month.

    Returns ``(label, local_date, daily_max_c, weight)``. Quantile days use the nearest rank
    in the sorted daily maxima (ties broken by date); each carries weight ``1/len(quantiles)``.
    The mildest and hottest days follow with weight 0.
    """
    m = month_of(days) == month
    d, t = days[m], tmax[m]
    if d.size == 0:
        return []
    order = np.lexsort((d.astype(int), t))
    d, t = d[order], t[order]
    out = []
    w = 1.0 / len(quantiles)
    for q in quantiles:
        i = int(round(q * (d.size - 1)))
        out.append((f"p{round(q * 100):02d}", d[i], float(t[i]), w))
    out.append(("mildest", d[0], float(t[0]), 0.0))
    out.append(("hottest", d[-1], float(t[-1]), 0.0))
    return out


# ---------------------------------------------------------------------- envelope runs
def pm10_hourly_median(rec: SiteRecord) -> dict[tuple[int, int], float]:
    """Median CAMS PM10 per (month, local hour) over the hours where CAMS has a value."""
    lt = rec.local_times
    months = month_of(lt.astype("datetime64[D]"))
    hours = (lt.astype("datetime64[h]").astype(int)) % 24
    ok = np.isfinite(rec.pm10_ugm3)
    out: dict[tuple[int, int], float] = {}
    for mo in range(1, 13):
        for hr in range(24):
            sel = ok & (months == mo) & (hours == hr)
            if sel.any():
                out[(mo, hr)] = float(np.median(rec.pm10_ugm3[sel]))
    return out


def day_weather(
    rec: SiteRecord, local_date: np.datetime64, pm_median: dict[tuple[int, int], float]
) -> tuple[Weather, float]:
    """Recorded weather from 3 h before local midnight to 2 h after the next one.

    Returns the weather and the fraction of its hours whose PM10 is a CAMS hourly median fill.
    """
    t0 = np.datetime64(local_date, "s") - np.timedelta64(LOCAL_OFFSET_H + 3, "h")
    t1 = np.datetime64(local_date, "s") + np.timedelta64(24 - LOCAL_OFFSET_H + 2, "h")
    sel = (rec.times_utc >= t0) & (rec.times_utc <= t1)
    times = rec.times_utc[sel]
    if times.size < 29:
        raise WeatherUnavailable(f"incomplete record around {local_date}")
    pm = rec.pm10_ugm3[sel].copy()
    filled = ~np.isfinite(pm)
    if filled.any():
        lt = times + np.timedelta64(LOCAL_OFFSET_H, "h")
        mo = month_of(lt.astype("datetime64[D]"))
        hr = lt.astype("datetime64[h]").astype(int) % 24
        for i in np.where(filled)[0]:
            key = (int(mo[i]), int(hr[i]))
            if key not in pm_median:
                raise WeatherUnavailable(f"no CAMS PM10 for {rec.site.id} month {key[0]}")
            pm[i] = pm_median[key]
    w = Weather(
        times_utc=times,
        t_air_c=rec.t_air_c[sel],
        dew_c=rec.dew_c[sel],
        wind10_ms=rec.wind10_ms[sel],
        pm10_ugm3=pm,
        precip_mm_h=rec.precip_mm_h[sel],
        lat=rec.site.lat,
        lon=rec.site.lon,
        altitude_m=rec.site.altitude_m,
        ghi_wm2=rec.ghi_wm2[sel],
        source="open-meteo-archive",
        label=rec.site.id,
    )
    return w, float(filled.mean())


@dataclass
class HourRow:
    site: str
    month: int
    day_label: str
    local_date: str
    daily_max_c: float
    weight: float
    local_hour: int
    action: str
    scale: float
    tightest_component: str
    tightest_headroom_k: float
    air_max_c: float
    pm10_source: str


def run_day(
    profile: Profile,
    w: Weather,
    local_date: np.datetime64,
    cfg: EngineConfig | None = None,
    duration_h: float = 1.0,
    mode: str = "drive",
) -> list[dict]:
    """Decision for a mission starting at every local hour of one day."""
    env = Envelope(profile, w, cfg or EngineConfig(), site=w.label)
    t_local0 = np.datetime64(local_date, "s") - np.timedelta64(LOCAL_OFFSET_H, "h")
    starts = np.array([env.index_of(t_local0 + np.timedelta64(h, "h")) for h in range(24)], dtype=int)
    scales, _ = env.best_scale(starts, duration_h, mode)
    full = env.scan(starts, np.ones((24, 1)), duration_h, mode)
    head = full["headroom"][:, 0, :]
    comps = full["comps"]
    n = env.steps_for(duration_h)
    air = env.forcing.t_air_k - 273.15
    rows = []
    for h, s in enumerate(starts):
        sc = float(scales[h])
        action = "GO" if sc >= 0.999 else ("DERATE" if sc > 0 else "PARK")
        j = int(np.argmin(head[h]))
        rows.append(
            {
                "local_hour": h,
                "action": action,
                "scale": round(sc, 3),
                "tightest_component": comps[j],
                "tightest_headroom_k": round(float(head[h, j]), 2),
                "air_max_c": round(float(air[s : s + n + 1].max()), 2),
            }
        )
    return rows


def run_site(
    profile: Profile,
    rec: SiteRecord,
    months: Iterable[int] = range(1, 13),
    cfg: EngineConfig | None = None,
    log: Callable[[str], None] | None = None,
) -> list[HourRow]:
    days, tmax = daily_max_by_local_day(rec)
    pm_med = pm10_hourly_median(rec)
    out: list[HourRow] = []
    for mo in months:
        for label, d, tm, wgt in select_days(days, tmax, mo):
            w, fill = day_weather(rec, d, pm_med)
            src = "cams" if fill == 0 else ("cams_hourly_median" if fill == 1 else "mixed")
            for r in run_day(profile, w, d, cfg):
                out.append(
                    HourRow(
                        site=rec.site.id,
                        month=mo,
                        day_label=label,
                        local_date=str(d),
                        daily_max_c=round(tm, 2),
                        weight=wgt,
                        pm10_source=src,
                        **r,
                    )
                )
        if log:
            log(f"{rec.site.id} month {mo} done")
    return out


# ---------------------------------------------------------------------- record statistics
def hours_above(rec: SiteRecord, threshold_c: float) -> dict[int, tuple[int, int]]:
    """Per month: (hours with air temperature above threshold, valid hours) over the record."""
    mo = month_of(rec.local_times.astype("datetime64[D]"))
    ok = np.isfinite(rec.t_air_c)
    out = {}
    for m in range(1, 13):
        sel = ok & (mo == m)
        out[m] = (int(np.sum(rec.t_air_c[sel] > threshold_c)), int(sel.sum()))
    return out


# ---------------------------------------------------------------------- outputs
HOUR_FIELDS = list(HourRow.__dataclass_fields__)
MONTH_FIELDS = [
    "site",
    "month",
    "share_go",
    "share_derate",
    "share_park",
    "mean_scale",
    "hottest_day_share_go",
    "mildest_day_share_go",
    "air_above_rated_hours",
    "record_hours",
    "share_air_above_rated",
    "share_not_go_air_within_rating",
    "pm10_fill_share",
]


def write_hour_csv(rows: list[HourRow], path: str | Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=HOUR_FIELDS)
        wr.writeheader()
        for r in rows:
            wr.writerow(r.__dict__)


def read_hour_csv(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k in ("month", "local_hour"):
            r[k] = int(r[k])
        for k in ("daily_max_c", "weight", "scale", "tightest_headroom_k", "air_max_c"):
            r[k] = float(r[k])
    return rows


def summarise(
    hour_rows: list[dict], above: dict[str, dict[int, tuple[int, int]]], rated_c: float
) -> list[dict]:
    """Month table from the hourly decisions and the record counts above the rating."""
    out = []
    sites = list(dict.fromkeys(r["site"] for r in hour_rows))
    for s in sites:
        for m in range(1, 13):
            rows = [r for r in hour_rows if r["site"] == s and r["month"] == m]
            if not rows:
                continue
            wsum = sum(r["weight"] for r in rows)
            share = {a: sum(r["weight"] for r in rows if r["action"] == a) / wsum for a in ACTIONS}
            weighted = [r for r in rows if r["weight"] > 0]
            within = [r for r in weighted if r["air_max_c"] <= rated_c]
            not_go_within = sum(r["weight"] for r in within if r["action"] != "GO") / wsum

            def go_share(label: str, rows=rows) -> float:
                sel = [r for r in rows if r["day_label"] == label]
                return sum(r["action"] == "GO" for r in sel) / len(sel) if sel else float("nan")

            n_above, n_rec = above.get(s, {}).get(m, (0, 0))
            out.append(
                {
                    "site": s,
                    "month": m,
                    "share_go": round(share["GO"], 4),
                    "share_derate": round(share["DERATE"], 4),
                    "share_park": round(share["PARK"], 4),
                    "mean_scale": round(sum(r["weight"] * r["scale"] for r in rows) / wsum, 4),
                    "hottest_day_share_go": round(go_share("hottest"), 4),
                    "mildest_day_share_go": round(go_share("mildest"), 4),
                    "air_above_rated_hours": n_above,
                    "record_hours": n_rec,
                    "share_air_above_rated": round(n_above / n_rec, 4) if n_rec else float("nan"),
                    "share_not_go_air_within_rating": round(not_go_within, 4),
                    "pm10_fill_share": round(
                        sum(r["pm10_source"] != "cams" for r in weighted) / len(weighted), 4
                    ),
                }
            )
    return out


def write_month_csv(rows: list[dict], path: str | Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=MONTH_FIELDS)
        wr.writeheader()
        wr.writerows(rows)


def read_month_csv(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k in MONTH_FIELDS[1:]:
            r[k] = (
                int(r[k])
                if k in ("month", "air_above_rated_hours", "record_hours")
                else float(r[k])
            )
    return rows


def headline(month_rows: list[dict], year: int = 2023) -> dict[str, float]:
    """Year shares across all sites, months weighted by their number of days.

    ``year`` only sets the month lengths (2023 is not a leap year). Air temperature shares
    use the full record hour counts directly.
    """
    days = {m: _cal.monthrange(year, m)[1] for m in range(1, 13)}
    tot = sum(days[r["month"]] for r in month_rows)
    out = {
        f"share_{k}": sum(days[r["month"]] * r[f"share_{k}"] for r in month_rows) / tot
        for k in ("go", "derate", "park")
    }
    out["share_not_go_air_within_rating"] = (
        sum(days[r["month"]] * r["share_not_go_air_within_rating"] for r in month_rows) / tot
    )
    above = sum(r["air_above_rated_hours"] for r in month_rows)
    rec = sum(r["record_hours"] for r in month_rows)
    out["share_air_above_rated"] = above / rec if rec else float("nan")
    out["sites"] = len({r["site"] for r in month_rows})
    return out
