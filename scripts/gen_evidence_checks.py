"""Two cheap checks on the operating calendar (known issues 6 and 7).

1. PM10 fill: rerun the calendar with days chosen only from the period where CAMS PM10 exists
   (from the first complete local day with CAMS values, August 2022, to December 2025) and compare
   the headline with the full 2015 to 2025 calendar.
2. Sampling error: for one site and one year, run every day through the envelope and compare the
   month shares with the five representative day estimate drawn from the same year.

Recorded weather from the disk cache (see dhill.climatology); the profile is clearpath_jackal (L0).
Writes examples/evidence_checks.json and renders docs/evidence-checks.md from it.
Run: python scripts/gen_evidence_checks.py [--render-only]
"""

from __future__ import annotations

import calendar
import json
import sys
from pathlib import Path

import numpy as np

from dhill import climatology as clim
from dhill.envelope import EngineConfig
from dhill.profiles.loader import load_profile

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "clearpath_jackal"
RATED_C = 45.0
CFG = EngineConfig(n_mc=64, seed=7)
SAMPLING_SITE = "al_ain"
SAMPLING_YEAR = 2024
FULL_CSV = ROOT / "examples" / f"operating_calendar_{PROFILE}.csv"
OUT = ROOT / "examples" / "evidence_checks.json"
DOC = ROOT / "docs" / "evidence-checks.md"
MON = [calendar.month_abbr[m] for m in range(1, 13)]
KEYS = ("share_go", "share_derate", "share_park")


def first_full_cams_day(rec: clim.SiteRecord) -> str:
    """First local date on which every hour has a CAMS PM10 value."""
    lt = rec.local_times
    days = lt.astype("datetime64[D]")
    ok = np.isfinite(rec.pm10_ugm3)
    for d in np.unique(days[ok]):
        sel = days == d
        if sel.sum() == 24 and ok[sel].all():
            return str(d)
    raise clim.WeatherUnavailable(f"{rec.site.id}: no complete CAMS day")


def cams_period() -> dict:
    prof = load_profile(PROFILE)
    rows, above, first = [], {}, {}
    for sid in clim.DEFAULT_SITES:
        rec = clim.load_site_record(sid, clim.DEFAULT_YEARS, offline=True)
        first[sid] = first_full_cams_day(rec)
        above[sid] = clim.hours_above(rec, RATED_C)
        rows += clim.run_site(prof, rec, cfg=CFG, first_day=first[sid], log=print)
    month = clim.summarise([r.__dict__ for r in rows], above, RATED_C)
    return {"first_day": first, "month": month, "headline": clim.headline(month)}


def sampling() -> dict:
    prof = load_profile(PROFILE)
    rec = clim.load_site_record(SAMPLING_SITE, (SAMPLING_YEAR,), offline=True)
    win = {"first_day": f"{SAMPLING_YEAR}-01-01", "last_day": f"{SAMPLING_YEAR}-12-31"}
    above = {SAMPLING_SITE: clim.hours_above(rec, RATED_C)}
    out = {}
    for name, every in (("sampled", False), ("every_day", True)):
        rows = clim.run_site(prof, rec, cfg=CFG, every_day=every, log=print, **win)
        month = clim.summarise([r.__dict__ for r in rows], above, RATED_C)
        out[name] = {"month": month, "headline": clim.headline(month), "days": len(rows) // 24}
    return out


def pct(x: float, nd: int = 1) -> str:
    return f"{100 * x:.{nd}f} %"


def pp(x: float) -> str:
    return f"{100 * x:+.1f}"


def render(res: dict) -> str:
    full = clim.headline(clim.read_month_csv(FULL_CSV))
    cams = res["cams_period"]["headline"]
    s, e = res["sampling"]["sampled"], res["sampling"]["every_day"]
    L = [
        "# Evidence checks on the operating calendar",
        "",
        "Rendered by `scripts/gen_evidence_checks.py` from `examples/evidence_checks.json`;",
        "`tests/test_evidence_checks.py` fails if this document differs from that rendering. Recorded",
        f"Open-Meteo weather, profile `{PROFILE}` (L0), engine seed {CFG.seed}, {CFG.n_mc} Monte Carlo samples.",
        "",
        "## 1. Does the PM10 fill change the calendar? (known issue 6)",
        "",
        "Days were chosen only from the period with recorded CAMS PM10 (first complete local day per site:",
        ", ".join(f"{k} {v}" for k, v in res["cams_period"]["first_day"].items())
        + "; to 2025-12-31).",
        "The full calendar chooses days from 2015 to 2025 and fills PM10 before August 2022 with CAMS",
        "hourly medians. The two runs differ in PM10 and also in which days are selected, so the",
        "difference is an upper bound on the effect of the fill.",
        "",
        "| Share of hours | Full period, with fill | CAMS period only | Difference (points) |",
        "|---|---:|---:|---:|",
    ]
    for k, label in zip(KEYS, ("GO", "DERATE", "PARK"), strict=True):
        L.append(f"| {label} | {pct(full[k])} | {pct(cams[k])} | {pp(cams[k] - full[k])} |")
    fill_cams = float(np.mean([r["pm10_fill_share"] for r in res["cams_period"]["month"]]))
    L += [
        "",
        f"Weighted sampled days using the PM10 fill in the CAMS period run: {pct(fill_cams)}.",
        "",
        "## 2. How large is the sampling error? (known issue 7)",
        "",
        f"Site `{SAMPLING_SITE}`, year {SAMPLING_YEAR}: every complete local day of the year in the record ({e['days']} days; 1 January starts in the",
        "previous UTC year, which this check does not load) against the",
        "calendar method (five representative days per month, 10th to 90th percentile of daily maximum,",
        "equal weight) applied to the same year. The sampled run also computes the hottest and mildest",
        f"day per month ({s['days']} days in all), which carry no weight.",
        "",
        "| Share of hours, year | Every day | Five sampled days per month | Sampling error (points) |",
        "|---|---:|---:|---:|",
    ]
    for k, label in zip(KEYS, ("GO", "DERATE", "PARK"), strict=True):
        L.append(
            f"| {label} | {pct(e['headline'][k])} | {pct(s['headline'][k])} | "
            f"{pp(s['headline'][k] - e['headline'][k])} |"
        )
    L += [
        "",
        "Per month, sampled minus every day, percentage points:",
        "",
        "| Month | GO | DERATE | PARK |",
        "|---|---:|---:|---:|",
    ]
    errs = []
    for ms, me in zip(s["month"], e["month"], strict=True):
        d = [ms[k] - me[k] for k in KEYS]
        errs += [abs(x) for x in d]
        L.append(f"| {MON[ms['month'] - 1]} | " + " | ".join(pp(x) for x in d) + " |")
    L += [
        "",
        f"Largest monthly error: {100 * max(errs):.1f} points; mean absolute monthly error:",
        f"{100 * float(np.mean(errs)):.1f} points.",
        "",
        "## Limits",
        "",
        "- One site and one year for the sampling check; other sites and years may differ.",
        "- Both checks inherit every limit of `docs/operating-calendar.md`, including the L0 profile.",
        "",
    ]
    return "\n".join(L)


def main() -> int:
    if "--render-only" in sys.argv:
        res = json.loads(OUT.read_text(encoding="utf-8"))
    else:
        res = {"cams_period": cams_period(), "sampling": sampling()}
        OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
        res = json.loads(OUT.read_text(encoding="utf-8"))
    DOC.write_text(render(res), encoding="utf-8")
    print(DOC.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
