"""Command-line interface: ``dhill <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .envelope import EngineConfig, Envelope, sample_count_warning
from .profiles.loader import builtin_profile_ids, load_profile
from .sites import SITES, site_ids
from .weather import (
    SCENARIOS,
    WeatherUnavailable,
    fetch_weather,
    load_weather_csv,
    synthetic_weather,
)
from .weather.base import Weather

GLYPH = {"GO": "GO    ", "DERATE": "DERATE", "PARK": "PARK  "}


def get_weather(args) -> Weather:
    if getattr(args, "weather_csv", None):
        s = SITES[args.site]
        return load_weather_csv(args.weather_csv, s.lat, s.lon, s.altitude_m)
    if args.source == "synthetic":
        return synthetic_weather(
            args.site, args.scenario, start=args.start or "2026-08-05T00:00", days=args.days
        )
    try:
        return fetch_weather(args.site, forecast_days=args.days)
    except WeatherUnavailable as exc:
        print(
            f"warning: live forecast unavailable ({exc}); using synthetic '{args.scenario}'",
            file=sys.stderr,
        )
        return synthetic_weather(
            args.site, args.scenario, start=args.start or "2026-08-05T00:00", days=args.days
        )


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--profile", default="ugv_medium_inspection", help="built-in id or YAML path")
    p.add_argument("--site", default="abu_dhabi", choices=site_ids())
    p.add_argument("--source", default="synthetic", choices=["synthetic", "live"])
    p.add_argument("--scenario", default="summer_clear", choices=sorted(SCENARIOS))
    p.add_argument("--weather-csv")
    p.add_argument("--start", help="UTC start of synthetic weather (default 2026-08-05T00:00)")
    p.add_argument("--days", type=int, default=2)
    p.add_argument("--mode", default="drive")
    p.add_argument("--duration-h", type=float, default=1.0)
    p.add_argument(
        "--samples", type=int, default=64, help="Monte Carlo samples (64 or more for results)"
    )
    p.add_argument("--json", action="store_true")


def _engine(args) -> Envelope:
    return Envelope(
        load_profile(args.profile),
        get_weather(args),
        EngineConfig(n_mc=args.samples),
        site=args.site,
    )


def cmd_decide(args) -> int:
    env = _engine(args)
    d = env.decide(args.at, args.duration_h, args.mode)
    if args.json:
        print(d.model_dump_json(indent=2))
        return 0
    print(
        f"{d.action}  scale {d.scale:.2f}  speed {d.speed_ms:.2f} m/s   [{d.evidence_level}]  start {d.start_utc}"
    )
    for r in d.reasons:
        print(f"  - {r}")
    print("  component        risk peak   limit  headroom   P(exceed hard limit)")
    for c in d.components:
        print(
            f"  {c.component:<14} {c.risk_peak_c:>8.1f}  {c.limit_c:>6.0f}  {c.headroom_k:>+7.1f} K"
        )
    print(f"  min SoC (low quantile) {d.risk_min_soc:.2f}  reserve {d.soc_reserve:.2f}")
    if d.next_full_scale_start_utc:
        print(f"  next full-scale window: {d.next_full_scale_start_utc}")
    print(f"  {d.caveat}")
    return 0


def cmd_timeline(args) -> int:
    env = _engine(args)
    tl = env.timeline(args.duration_h, args.mode, args.step_min)
    if args.json:
        print(tl.model_dump_json(indent=2))
        return 0
    print(
        f"{tl.profile_id} @ {tl.site}  ({tl.weather_source}, {tl.evidence_level})  {tl.duration_h:g} h missions"
    )
    for s in tl.slots:
        bar = "#" * int(round(s.scale * 20))
        print(
            f"{s.start_utc[5:16]}  {GLYPH[s.action]} {s.scale:4.2f} {bar:<20} {s.limiting_component}"
        )
    print(f"productive hours (scale-weighted): {tl.productive_hours:.1f}")
    return 0


def cmd_plan(args) -> int:
    from .planner import PlannerSpec, compare

    ids = args.robots or [args.profile]
    w = get_weather(args)
    tls = {}
    for rid in ids:
        env = Envelope(load_profile(rid), w, EngineConfig(n_mc=args.samples), site=args.site)
        tls[rid] = env.timeline(args.duration_h, args.mode, args.step_min)
    spec = PlannerSpec(
        block_h=args.duration_h,
        rest_h=args.rest_h,
        max_concurrent=args.max_concurrent,
        demand_work_h=args.demand_h,
    )
    cmp = compare(tls, spec, local_offset_h=args.utc_offset_h)
    if args.json:
        print(cmp.model_dump_json(indent=2))
        return 0
    print(
        f"Dhill plan: {cmp.dhill.completed_work_h:.1f} h of {args.demand_h:g} h demand, 0 predicted limit breaches ({cmp.dhill.status})"
    )
    for b in cmp.dhill.blocks:
        print(f"  {b.start_utc[5:16]}  {b.robot:<26} scale {b.scale:.2f}")
    if cmp.ageing_blind is not None:
        print(
            f"Battery ageing: {cmp.dhill.age_equiv_h:.1f} h (25 degC equivalent) vs "
            f"{cmp.ageing_blind.age_equiv_h:.1f} h if ageing is ignored"
        )
    print(
        f"Fixed 08:00-17:00 shift at full speed: {cmp.naive.completed_work_h:.1f} h usable, "
        f"{cmp.naive_at_risk_blocks} of {cmp.naive_total_blocks} blocks would breach a limit"
    )
    return 0


def cmd_calibrate(args) -> int:
    from .calibrate import calibrate, load_telemetry_csv

    prof = load_profile(args.profile)
    tel = load_telemetry_csv(args.telemetry)
    w = get_weather(args)
    cal, res = calibrate(prof, w, tel)
    if args.out:
        Path(args.out).write_text(json.dumps(cal.model_dump(mode="json"), indent=2))
    if args.json:
        print(res.model_dump_json(indent=2))
        return 0
    for f in res.params:
        flag = "identified" if f.identified else "NOT identified"
        print(f"{f.key:<40} {f.prior:>10.4g} -> {f.fitted:>10.4g}  (+/-{f.rel_ci95:.1%})  {flag}")
    print(
        f"RMSE train {res.rmse_train_k:.2f} K | hold-out {res.rmse_holdout_k:.2f} K | prior on hold-out {res.rmse_prior_holdout_k:.2f} K"
    )
    print(f"evidence level now {cal.evidence_level}")
    return 0


def cmd_validate(args) -> int:
    from .calibrate import load_telemetry_csv
    from .validate import render_markdown, validate

    prof = load_profile(args.profile)
    tel = load_telemetry_csv(args.telemetry)
    rep = validate(prof, get_weather(args), tel, n_mc=args.samples, note=args.note or "")
    if args.report:
        Path(args.report).write_text(render_markdown(rep, args.telemetry), encoding="utf-8")
    if args.json:
        print(rep.model_dump_json(indent=2))
    else:
        print(f"{rep.profile_id} [{rep.evidence_level}]  {rep.start_utc} to {rep.end_utc}")
        print(" node            RMSE K   peak margin K   within 95 %   result")
        for n in rep.nodes:
            res = "pass" if n.passed else "FAIL"
            print(
                f" {n.node:<15} {n.rmse_k:>6.2f}   {n.peak_margin_k:>+12.1f}   "
                f"{'yes' if n.within_q95 else 'no':>11}   {res}"
            )
        print(f"overall: {'PASS' if rep.passed else 'FAIL'}")
    return 0 if rep.passed else 3


def cmd_demo_telemetry(args) -> int:
    from .calibrate import save_telemetry_csv, synthetic_telemetry

    base = load_profile(args.profile)
    true = base.with_overrides(
        {
            "surface.alpha_clean": 0.52,
            "coupling.ua_shell_interior_w_k": 14.0,
            "shell.heat_capacity_j_k": 24000.0,
        }
    )
    w = get_weather(args)
    tel = synthetic_telemetry(true, w, args.start or "2026-08-05T01:00", hours=args.hours)
    save_telemetry_csv(tel, args.out)
    print(
        f"wrote {args.out} ({tel.n} rows); true alpha_clean=0.52, ua_shell_interior=14, shell C=24000 (hidden from the fit)"
    )
    return 0


def cmd_sensitivity(args) -> int:
    from .sensitivity import tornado

    prof = load_profile(args.profile)
    rep = tornado(prof, get_weather(args), args.at, args.duration_h, args.mode, args.scale)
    if args.json:
        print(rep.model_dump_json(indent=2))
        return 0
    print(
        f"{rep.profile_id}  {rep.start_utc}  scale {rep.scale:g}: {rep.binding_component} peaks at "
        f"{rep.nominal_peak_c:.1f} C against an allowed {rep.allowed_c:.0f} C; prior spread about +/-{rep.total_sd_k:.1f} K"
    )
    print(
        " rank  parameter                                 source      sigma  swing(K)  share  gain if measured(K)"
    )
    cum = 0.0
    for r in rep.rows[: args.top]:
        cum += r.share
        print(
            f" {r.rank:>3}   {r.key:<40} {r.source:<10} {r.sigma:>5.2f}  {r.swing_k:>7.2f}  {r.share:>5.0%}  {r.measured_gain_k:>7.2f}"
        )
    print(
        f" top {min(args.top, len(rep.rows))} parameters carry {cum:.0%} of the (additive) variance; measure those first"
    )
    return 0


def cmd_calendar(args) -> int:
    from . import climatology as clim

    prof = load_profile(args.profile)
    y0, _, y1 = args.years.partition("-")
    years = range(int(y0), int(y1 or y0) + 1)
    rows, above, gaps = [], {}, []
    for sid in args.sites:
        try:
            rec = clim.load_site_record(sid, years, offline=args.offline)
        except clim.WeatherUnavailable as exc:
            gaps.append(f"{sid}: {exc}")
            continue
        gaps += rec.gaps
        above[sid] = clim.hours_above(rec, args.rated_c)
        rows += clim.run_site(prof, rec, cfg=EngineConfig(n_mc=args.samples))
    if not rows:
        print("error: no recorded weather available; nothing computed", file=sys.stderr)
        for g in gaps:
            print(f"  gap: {g}", file=sys.stderr)
        return 2
    if args.hours_csv:
        clim.write_hour_csv(rows, args.hours_csv)
    month = clim.summarise([r.__dict__ for r in rows], above, args.rated_c)
    if args.out:
        clim.write_month_csv(month, args.out)
    head = clim.headline(month)
    print(f"{prof.id} [{prof.evidence_level}]  {args.years}  1 h drive missions, every local hour")
    print(" site            month   GO   DERATE  PARK   air>rated  not GO, air within rating")
    for r in month:
        print(
            f" {r['site']:<15} {r['month']:>5} {r['share_go']:>5.0%} {r['share_derate']:>7.0%} "
            f"{r['share_park']:>5.0%} {r['share_air_above_rated']:>9.1%} {r['share_not_go_air_within_rating']:>9.0%}"
        )
    print(
        f"all sites, year: GO {head['share_go']:.1%}, DERATE {head['share_derate']:.1%}, "
        f"PARK {head['share_park']:.1%}; air above {args.rated_c:g} degC in "
        f"{head['share_air_above_rated']:.1%} of recorded hours"
    )
    for g in gaps:
        print(f"gap: {g}")
    return 0


def cmd_list(args) -> int:
    if args.what == "profiles":
        for p in builtin_profile_ids():
            print(p)
    elif args.what == "sites":
        for s in SITES.values():
            print(f"{s.id:<24} {s.name} ({s.emirate}, {s.setting})")
    else:
        for k, v in SCENARIOS.items():
            print(f"{k:<16} {v}")
    return 0


def cmd_serve(args) -> int:
    import uvicorn

    uvicorn.run("dhill.api.app:app", host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="dhill",
        description="Heat and dust operating-envelope intelligence for outdoor robots.",
    )
    ap.add_argument("--version", action="version", version=f"dhill {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("decide", help="GO / DERATE / PARK for one mission window")
    _common(s)
    s.add_argument("--at", help="UTC start, e.g. 2026-08-05T09:00 (default: forecast start)")
    s.set_defaults(fn=cmd_decide)

    s = sub.add_parser("timeline", help="decision for every start time")
    _common(s)
    s.add_argument("--step-min", type=float, default=60.0)
    s.set_defaults(fn=cmd_timeline)

    s = sub.add_parser("plan", help="schedule a fleet and compare against a fixed shift")
    _common(s)
    s.add_argument("--robots", nargs="*", help="profile ids or paths (default: --profile)")
    s.add_argument("--step-min", type=float, default=30.0)
    s.add_argument("--rest-h", type=float, default=0.5)
    s.add_argument("--max-concurrent", type=int)
    s.add_argument("--demand-h", type=float, default=12.0)
    s.add_argument("--utc-offset-h", type=float, default=4.0)
    s.set_defaults(fn=cmd_plan)

    s = sub.add_parser("calibrate", help="fit parameters on telemetry CSV")
    _common(s)
    s.add_argument("--telemetry", required=True)
    s.add_argument("--out", help="write calibrated profile JSON")
    s.set_defaults(fn=cmd_calibrate)

    s = sub.add_parser(
        "validate", help="check a profile against held out telemetry (exit 3 on FAIL)"
    )
    _common(s)
    s.add_argument(
        "--telemetry", required=True, help="held out telemetry CSV, not used to calibrate"
    )
    s.add_argument("--report", help="write a markdown report")
    s.add_argument("--note", help="line printed at the top of the report, e.g. a SYNTHETIC label")
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser(
        "demo-telemetry", help="write synthetic telemetry from a hidden 'true' robot"
    )
    _common(s)
    s.add_argument("--hours", type=float, default=18.0)
    s.add_argument("--out", default="telemetry_demo.csv")
    s.set_defaults(fn=cmd_demo_telemetry)

    s = sub.add_parser("sensitivity", help="rank parameters by effect on the binding component")
    _common(s)
    s.add_argument("--at", required=True, help="UTC mission start, e.g. 2026-08-05T05:00")
    s.add_argument("--scale", type=float, default=1.0)
    s.add_argument("--top", type=int, default=10)
    s.set_defaults(fn=cmd_sensitivity)

    s = sub.add_parser(
        "calendar", help="share of hours GO / DERATE / PARK per site and month, recorded weather"
    )
    s.add_argument("--profile", default="clearpath_jackal", help="built-in id or YAML path")
    s.add_argument(
        "--sites",
        nargs="*",
        default=["abu_dhabi", "al_ain", "dubai", "sweihan", "liwa", "fujairah"],
    )
    s.add_argument("--years", default="2015-2025", help="inclusive range, e.g. 2015-2025")
    s.add_argument("--rated-c", type=float, default=45.0, help="manufacturer rated ambient (degC)")
    s.add_argument(
        "--samples", type=int, default=64, help="Monte Carlo samples (64 or more for results)"
    )
    s.add_argument("--out", help="write the month table CSV")
    s.add_argument("--hours-csv", help="write every hourly decision as CSV")
    s.add_argument("--offline", action="store_true", help="use the disk cache only")
    s.set_defaults(fn=cmd_calendar)

    s = sub.add_parser("list", help="list profiles, sites or scenarios")
    s.add_argument("what", choices=["profiles", "sites", "scenarios"])
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("serve", help="run the REST API and dashboard")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8080)
    s.set_defaults(fn=cmd_serve)

    args = ap.parse_args(argv)
    warning = sample_count_warning(args.samples) if hasattr(args, "samples") else None
    if warning:
        print(f"warning: {warning}", file=sys.stderr)
    try:
        return args.fn(args)
    except (KeyError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
