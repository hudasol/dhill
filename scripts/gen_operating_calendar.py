"""Generate the operating calendar outputs for the clearpath_jackal profile.

Writes examples/operating_calendar_clearpath_jackal.csv (month table),
examples/operating_calendar_clearpath_jackal_hours.csv (every hourly decision),
examples/operating_calendar_meta.json, docs/img/operating-calendar.png and
docs/operating-calendar.md. Every number in the document is computed here from the CSV.

Weather is read from the disk cache and downloaded where missing (see dhill.climatology).
Requires the plot extra: pip install -e ".[plot]".
"""

from __future__ import annotations

import calendar
import itertools
import json
import sys
from pathlib import Path

import numpy as np

from dhill import climatology as clim
from dhill.envelope import EngineConfig
from dhill.profiles.loader import load_profile

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "clearpath_jackal"
RATED_C = 45.0  # docs/robot-sources.md: Jackal datasheet operating ambient -20 to 45 degC
YEARS = clim.DEFAULT_YEARS
SITES = clim.DEFAULT_SITES
CFG = EngineConfig(n_mc=64, seed=7)
MONTH_CSV = ROOT / "examples" / f"operating_calendar_{PROFILE}.csv"
HOUR_CSV = ROOT / "examples" / f"operating_calendar_{PROFILE}_hours.csv"
META = ROOT / "examples" / "operating_calendar_meta.json"
IMG = ROOT / "docs" / "img" / "operating-calendar.png"
BEFORE_CSV = ROOT / "examples" / "before-fix" / f"operating_calendar_{PROFILE}.csv"
HEADLINE_KEYS = (
    ("share_go", "GO"),
    ("share_derate", "DERATE"),
    ("share_park", "PARK"),
    ("share_air_above_rated", "Air above the rated ambient (all recorded hours)"),
    ("share_not_go_air_within_rating", "Not GO although mission air stays within the rating"),
)
DOC = ROOT / "docs" / "operating-calendar.md"
MON = [calendar.month_abbr[m] for m in range(1, 13)]


def compute(offline: bool) -> dict:
    prof = load_profile(PROFILE)
    rows, above, gaps, pm_first = [], {}, [], {}
    for sid in SITES:
        try:
            rec = clim.load_site_record(sid, YEARS, offline=offline, log=print)
        except clim.WeatherUnavailable as exc:
            gaps.append(f"{sid}: {exc}")
            continue
        gaps += rec.gaps
        ok = np.isfinite(rec.pm10_ugm3)
        pm_first[sid] = str(rec.times_utc[ok][0]) if ok.any() else None
        above[sid] = clim.hours_above(rec, RATED_C)
        rows += clim.run_site(prof, rec, cfg=CFG, log=print)
    clim.write_hour_csv(rows, HOUR_CSV)
    month = clim.summarise([r.__dict__ for r in rows], above, RATED_C)
    clim.write_month_csv(month, MONTH_CSV)
    meta = {
        "profile": PROFILE,
        "profile_evidence_level": prof.evidence_level,
        "profile_assumption_fraction": round(prof.assumption_fraction(), 3),
        "rated_ambient_c": RATED_C,
        "rated_ambient_source": "docs/robot-sources.md (Clearpath Jackal datasheet, Sept 2020)",
        "years": [YEARS[0], YEARS[-1]],
        "sites": list(SITES),
        "mission": "1 h, drive mode, full scale requested, start at every local hour (UTC+4)",
        "engine": {"n_mc": CFG.n_mc, "seed": CFG.seed, "dt_s": CFG.dt_s},
        "pm10_first_cams_hour_utc": pm_first,
        "gaps": gaps,
        "weather_source": "Open-Meteo historical archive (reanalysis) and air quality API (CAMS)",
    }
    META.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def grid(month_rows: list[dict], key: str) -> tuple[list[str], np.ndarray]:
    sites = list(dict.fromkeys(r["site"] for r in month_rows))
    g = np.full((len(sites), 12), np.nan)
    for r in month_rows:
        g[sites.index(r["site"]), r["month"] - 1] = r[key]
    return sites, g


def plot(month_rows: list[dict]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    blue = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#6da7ec", "#256abf", "#0d366b"])
    orange = LinearSegmentedColormap.from_list(
        "orange", ["#fbe5d9", "#f3a47f", "#d95926", "#7a2a0b"]
    )
    panels = [
        ("share_go", "Share of hours GO (envelope, L0 profile)", blue),
        ("share_park", "Share of hours PARK (envelope, L0 profile)", blue),
        ("share_air_above_rated", f"Share of hours with air above {RATED_C:g} degC", orange),
    ]
    fig, axes = plt.subplots(3, 1, figsize=(10, 9.6), constrained_layout=True)
    fig.patch.set_facecolor("#fcfcfb")
    for ax, (key, title, cmap) in zip(axes, panels, strict=True):
        sites, g = grid(month_rows, key)
        vmax = 1.0 if key != "share_air_above_rated" else max(0.1, float(np.nanmax(g)))
        ax.imshow(g, cmap=cmap, vmin=0, vmax=vmax, aspect="auto")
        for i in range(g.shape[0]):
            for j in range(12):
                v = g[i, j]
                if np.isfinite(v):
                    ink = "#ffffff" if v / vmax > 0.55 else "#0b0b0b"
                    ax.text(j, i, f"{100 * v:.0f}", ha="center", va="center", fontsize=8, color=ink)
        ax.set_xticks(range(12), MON, fontsize=9, color="#52514e")
        ax.set_yticks(range(len(sites)), sites, fontsize=9, color="#52514e")
        scale_note = "" if vmax == 1.0 else f" (colour scale 0 to {100 * vmax:.0f})"
        ax.set_title(title + ", percent" + scale_note, fontsize=10, loc="left", color="#0b0b0b")
        ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
    fig.suptitle(
        "Operating calendar, clearpath_jackal (L0, method demonstration), "
        f"recorded weather {YEARS[0]} to {YEARS[-1]}",
        fontsize=11,
        color="#0b0b0b",
    )
    IMG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMG, dpi=130, facecolor=fig.get_facecolor())


def prof_limit(comp: str) -> str:
    lim = load_profile(PROFILE).limits.get(comp)
    if lim is None:
        return "not defined"
    return f"{lim.limit_c:g} degC hard, {lim.margin_k:g} K margin, source {lim.source}"


def before_after(month_rows: list[dict]) -> list[str]:
    """Headline shares on the unfixed profile (kept CSV) and on the current one."""
    before = clim.headline(clim.read_month_csv(BEFORE_CSV))
    after = clim.headline(month_rows)
    out = [
        "| Share of hours | Before the fix | After the fix |",
        "|---|---:|---:|",
    ]
    for key, label in HEADLINE_KEYS:
        out.append(f"| {label} | {pct(before[key])} | {pct(after[key])} |")
    return out


def pct(x: float, nd: int = 1) -> str:
    return f"{100 * x:.{nd}f} %"


def table(month_rows: list[dict], key: str) -> list[str]:
    sites, g = grid(month_rows, key)
    out = ["| Site | " + " | ".join(MON) + " |", "|---|" + "---:|" * 12]
    for i, s in enumerate(sites):
        cells = [f"{100 * v:.0f}" if np.isfinite(v) else "n/a" for v in g[i]]
        out.append(f"| {s} | " + " | ".join(cells) + " |")
    return out


BANDS = [-50, 15, 20, 25, 30, 35, 40, 45, 60]


def go_edges(rows: list[dict]) -> tuple[float, float]:
    """Upper edge of the last band where GO is the majority, and the edge above which GO never occurs."""
    major, never = float("nan"), float("nan")
    for lo, hi in itertools.pairwise(BANDS):
        sel = [r for r in rows if lo < r["air_max_c"] <= hi]
        if sel and sum(r["action"] == "GO" for r in sel) / len(sel) > 0.5:
            major = hi
    go_air = [r["air_max_c"] for r in rows if r["action"] == "GO"]
    if go_air:
        never = min(b for b in BANDS if b >= max(go_air))
    return major, never


def band_table(rows: list[dict]) -> list[str]:
    out = []
    for lo, hi in itertools.pairwise(BANDS):
        sel = [r for r in rows if lo < r["air_max_c"] <= hi]
        if not sel:
            continue
        share = {a: sum(r["action"] == a for r in sel) / len(sel) for a in clim.ACTIONS}
        label = f"up to {hi}" if lo == -50 else (f"above {lo}" if hi == 60 else f"{lo} to {hi}")
        med = float(np.median([r["tightest_headroom_k"] for r in sel]))
        out.append(
            f"| {label} | {len(sel)} | {pct(share['GO'], 0)} | {pct(share['DERATE'], 0)} | "
            f"{pct(share['PARK'], 0)} | {med:+.1f} |"
        )
    return out


def render(month_rows: list[dict], hours: list[dict], meta: dict) -> str:
    h = clim.headline(month_rows)
    weighted = [r for r in hours if r["weight"] > 0]
    not_go = [r for r in weighted if r["action"] != "GO"]
    comp: dict[str, float] = {}
    for r in not_go:
        comp[r["tightest_component"]] = comp.get(r["tightest_component"], 0.0) + 1
    comp_share = {k: v / len(not_go) for k, v in sorted(comp.items(), key=lambda kv: -kv[1])}
    top_comp, top_share = next(iter(comp_share.items())) if comp_share else ("none", 0.0)
    jan = [r for r in month_rows if r["month"] == 1]
    jul = [r for r in month_rows if r["month"] == 7]
    go_jan = float(np.mean([r["share_go"] for r in jan])) if jan else float("nan")
    go_jul = float(np.mean([r["share_go"] for r in jul])) if jul else float("nan")
    worst = max(month_rows, key=lambda r: r["share_air_above_rated"])
    best_go = max(month_rows, key=lambda r: r["share_go"])
    night = [r for r in weighted if r["local_hour"] in (0, 1, 2, 3, 4, 5)]
    night_go = sum(r["action"] == "GO" for r in night) / len(night) if night else float("nan")
    go_major, go_never = go_edges(weighted)
    fill = float(np.mean([r["pm10_fill_share"] for r in month_rows]))
    gaps = meta["gaps"]
    pm_first = meta["pm10_first_cams_hour_utc"]
    pm_first_txt = ", ".join(f"{k} {v[:10] if v else 'none'}" for k, v in pm_first.items())
    L = [
        "# Operating calendar: clearpath_jackal at six UAE sites",
        "",
        "Generated by `scripts/gen_operating_calendar.py`. Every number in this document is computed by",
        f"that script from `examples/{MONTH_CSV.name}` (month table) and `examples/{HOUR_CSV.name}`",
        "(every hourly decision). A test (`tests/test_climatology.py`) checks that the headline below",
        "equals the code's result on the CSV.",
        "",
        f"**Evidence level: {meta['profile_evidence_level']}.** The profile is anchored to the manufacturer",
        f"datasheet but {pct(meta['profile_assumption_fraction'], 0)} of its parameters are assumptions",
        "(`docs/robot-sources.md`). The result is a method demonstration on recorded weather. It is not a",
        "statement about how a real Jackal behaves, and it is not an operating authorisation.",
        "",
        "## Headline",
        "",
        f"Across {h['sites']} sites and {meta['years'][0]} to {meta['years'][1]}, with months weighted by their",
        "length, the envelope for the L0 Jackal profile returns, for a 1 h drive mission started at a",
        f"given hour: **GO {pct(h['share_go'])}**, **DERATE {pct(h['share_derate'])}**, "
        f"**PARK {pct(h['share_park'])}** of hours.",
        f"The air temperature alone exceeds the manufacturer's rated {meta['rated_ambient_c']:g} degC in "
        f"**{pct(h['share_air_above_rated'])}** of all recorded hours.",
        f"In {pct(h['share_not_go_air_within_rating'])} of hours the air stays within the rating for the whole",
        "mission and the envelope still does not return GO.",
        "",
        "![Operating calendar heat map](img/operating-calendar.png)",
        "",
        "## Share of hours GO, percent",
        "",
        *table(month_rows, "share_go"),
        "",
        "## Share of hours DERATE, percent",
        "",
        *table(month_rows, "share_derate"),
        "",
        "## Share of hours PARK, percent",
        "",
        *table(month_rows, "share_park"),
        "",
        f"## Share of recorded hours with air above {meta['rated_ambient_c']:g} degC, percent",
        "",
        "Counted over every hour of the record, not only the sampled days.",
        "",
        *table(month_rows, "share_air_above_rated"),
        "",
        "## Before and after the profile fix",
        "",
        "Commit 6f38479 on branch `fix/jackal-rated-ambient` raised three assumed conductances (shell to interior 4.4 to",
        "12.0 W/K, battery 1.2 to 2.0 W/K, compute 2.0 to 4.5 W/K) so that the profile stays inside its",
        "limits at the rated ambient in shade. Before: `examples/before-fix/` (same weather, days, seeds).",
        "",
        *before_after(month_rows),
        "",
        "## Candid reading",
        "",
        "1. **The calendar is as sensitive as this to three unmeasured numbers.** The change above comes",
        "   only from the three conductances, which were chosen to match the datasheet rating, not",
        "   measured (`docs/robot-sources.md` gives a plausibility check: all three sit at the upper end of",
        "   what free convection and radiation can give). The absolute shares remain properties of the",
        "   assumptions until those conductances are measured.",
        f"2. **An ambient rating does not cover a robot in sun.** Air above {meta['rated_ambient_c']:g} degC is rare",
        f"   in this record ({pct(h['share_air_above_rated'])} of hours; at most "
        f"{pct(worst['share_air_above_rated'])} at {worst['site']} in {MON[worst['month'] - 1]}),",
        f"   yet the envelope withholds GO in {pct(1 - h['share_go'])} of hours. With the fixed profile GO is",
        f"   the majority decision only when the mission air stays at or below {go_major:g} degC, and GO never",
        f"   occurs above {go_never:g} degC. The profile is consistent with the rating in shade by",
        f"   construction; the remaining gap comes from solar load and from the {CFG.precondition_h:g} h parked soak in sun",
        "   that precedes each mission in this method. A shaded or cooled shelter between missions would",
        "   change the result and is not modelled here.",
        f"3. **The binding component is `{top_comp}`** in {pct(top_share, 0)} of hours that are not GO",
        f"   (tightest component at full scale). Its limit ({prof_limit(top_comp)}) is an assumption in the",
        "   profile; the cell datasheet value is the next number to obtain.",
        "4. **What the calendar does show.** The method runs end to end on eleven years of recorded",
        "   weather and separates hours that need derating from hours that need parking per site and",
        f"   month. The GO share is {pct(go_jan, 0)} in January and {pct(go_jul, 0)} in July on average across",
        f"   sites; the best month is {MON[best_go['month'] - 1]} at {best_go['site']} "
        f"({pct(best_go['share_go'], 0)}). Missions starting 00:00 to 05:00 local are GO in",
        f"   {pct(night_go, 0)} of sampled night hours.",
        "5. **Next step.** Measure shell to interior, battery and compute conductances and the battery",
        "   limit on a real unit (`docs/field-test-kit.md`), update the profile, rerun this script.",
        "",
        "### GO share by mission air temperature (weighted sampled hours, all sites)",
        "",
        "| Mission air max (degC) | Hours | GO | DERATE | PARK | Median headroom at full scale (K) |",
        "|---|---:|---:|---:|---:|---:|",
        *band_table(weighted),
        "",
        "## Method",
        "",
        f"- **Weather.** {meta['weather_source']}, hourly, UTC, {meta['years'][0]} to {meta['years'][1]},",
        "  one request per site and year, cached on disk. Sites and coordinates are those in",
        "  `src/dhill/sites.py`. The archive is a gridded reanalysis, not a station record.",
        "- **Representative days.** For each site and calendar month, every complete local day (UTC+4)",
        "  in the record is ranked by its daily maximum air temperature. The days at the 10th, 30th, 50th,",
        "  70th and 90th percentile (nearest rank) each stand for a 20 % band and carry equal weight",
        "  in the hour shares. The hottest and the mildest day are also run and reported as bounds",
        "  (columns `hottest_day_share_go` and `mildest_day_share_go` in the CSV); they carry no weight.",
        "- **Missions.** For each representative day, 24 missions of 1 h in drive mode, one starting at",
        "  every local hour, through the existing `Envelope` with its defaults (95 % risk quantile,",
        f"  {meta['engine']['n_mc']} Monte Carlo samples, seed {meta['engine']['seed']}, 1.5 h parked soak in sun before",
        "  each start). GO, DERATE and PARK follow the engine's rule: largest safe scale 1, between the",
        "  minimum scale and 1, or none.",
        f"- **Rated ambient.** {meta['rated_ambient_c']:g} degC from {meta['rated_ambient_source']}. The",
        "  share of hours above it is counted over the full record.",
        "- **PM10.** CAMS through the Open-Meteo air quality API returns values only from August 2022",
        f"  (first value per site: {pm_first_txt}). For hours before that, PM10 is the median CAMS value",
        "  for the same site, month and local hour over the available years, flagged",
        "  `pm10_source = cams_hourly_median` in the hourly CSV. On average "
        f"{pct(fill, 0)} of weighted sampled days use the fill.",
        "",
        "## Limits",
        "",
        "- L0 profile: the thermal parameters are assumptions; the shares above would change, possibly",
        "  a lot, once the compute heat path, conductances and absorptance are measured.",
        "- Five sampled days per month estimate the hour shares; they are not a full hourly",
        "  simulation of every day. Days with similar daily maximum can differ in humidity, wind and cloud.",
        "- Reanalysis temperature at a grid cell differs from the air next to a robot, especially in",
        "  urban heat and near the coast. The archive irradiance is an hourly mean used as an",
        "  instantaneous value, as elsewhere in the engine.",
        "- PM10 before August 2022 is a climatological fill, not the recorded value for that hour.",
        "- The robot is assumed to start each mission after a 1.5 h parked soak in full sun. A robot",
        "  kept in shade or a cooled shelter between missions would do better.",
        "- No standard is claimed or implied.",
        "",
        "## Data gaps",
        "",
    ]
    L += (
        [f"- {g}" for g in gaps]
        if gaps
        else ["- None: every requested site and year was retrieved."]
    )
    L += [
        "",
        "## Reproduce",
        "",
        "```bash",
        'pip install -e ".[dev,plot]"',
        "python scripts/gen_operating_calendar.py",
        "dhill calendar --profile clearpath_jackal --offline   # same table, from the cache",
        "```",
        "",
    ]
    return "\n".join(L)


def main() -> int:
    offline = "--offline" in sys.argv
    if "--doc-only" in sys.argv:
        meta = json.loads(META.read_text(encoding="utf-8"))
    else:
        meta = compute(offline)
    month = clim.read_month_csv(MONTH_CSV)
    hours = clim.read_hour_csv(HOUR_CSV)
    plot(month)
    DOC.write_text(render(month, hours, meta), encoding="utf-8")
    print(f"wrote {DOC.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
