"""Benchmark for the timing claim in README and requirement NFR-02 (known issue 13).

Times a 72 hour hourly timeline (1 h missions, 64 Monte Carlo samples, medium UGV, synthetic
Abu Dhabi summer weather) several times after one warm up run and prints the median and range.
Timing depends on the machine and its load; it is not a unit test.

Run: python scripts/benchmark_timeline.py [repeats]
"""

from __future__ import annotations

import platform
import statistics
import sys
import time

from dhill.envelope import EngineConfig, Envelope
from dhill.profiles.loader import load_profile
from dhill.weather import synthetic_weather

REQUIREMENT_S = 10.0  # NFR-02 in plan.md


def run_once() -> float:
    w = synthetic_weather("abu_dhabi", "summer_clear", days=3)
    env = Envelope(load_profile("ugv_medium_inspection"), w, EngineConfig(n_mc=64))
    t0 = time.perf_counter()
    env.timeline(1.0, "drive", 60.0)
    return time.perf_counter() - t0


def main() -> int:
    repeats = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    run_once()  # warm up
    times = [run_once() for _ in range(repeats)]
    med = statistics.median(times)
    print(f"72 h hourly timeline, 64 samples: median {med:.2f} s over {repeats} runs")
    print(f"range {min(times):.2f} to {max(times):.2f} s; NFR-02 limit {REQUIREMENT_S:g} s")
    print(f"python {platform.python_version()}, {platform.system()} {platform.machine()}")
    return 0 if med < REQUIREMENT_S else 1


if __name__ == "__main__":
    raise SystemExit(main())
