"""Command-line interface: ``dhill <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .envelope import EngineConfig, Envelope
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
    p.add_argument("--samples", type=int, default=64, help="Monte Carlo samples")
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
    print("  component        risk peak   limit  headroom")
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
        "demo-telemetry", help="write synthetic telemetry from a hidden 'true' robot"
    )
    _common(s)
    s.add_argument("--hours", type=float, default=18.0)
    s.add_argument("--out", default="telemetry_demo.csv")
    s.set_defaults(fn=cmd_demo_telemetry)

    s = sub.add_parser("list", help="list profiles, sites or scenarios")
    s.add_argument("what", choices=["profiles", "sites", "scenarios"])
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("serve", help="run the REST API and dashboard")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8080)
    s.set_defaults(fn=cmd_serve)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except (KeyError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
