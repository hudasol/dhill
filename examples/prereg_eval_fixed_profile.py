"""Rerun of the preregistered evaluation after the Jackal profile fix (addendum, 16 October 2026).

Runs exactly the design of docs/preregistration-v0.6.md again (same seeds, cases, policies and code
path, via examples/prereg_eval.py), writes examples/prereg_results_fixed_profile.json and renders
docs/prereg-results-addendum-fixed-profile.md with a before and after table computed from the two
JSON files. The original preregistration, results JSON and results document are not modified.

SYNTHETIC hidden robots and weather draws, as in the original run.
Run: python examples/prereg_eval_fixed_profile.py [--render-only]
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
import prereg_eval as pe  # noqa: E402

BEFORE = ROOT / "examples" / "prereg_results.json"
AFTER = ROOT / "examples" / "prereg_results_fixed_profile.json"
DOC = ROOT / "docs" / "prereg-results-addendum-fixed-profile.md"
PROFILES = ROOT / "src" / "dhill" / "profiles" / "builtin"


def profile_hash(pid: str) -> str:
    return hashlib.sha256((PROFILES / f"{pid}.yaml").read_bytes()).hexdigest()[:12]


def result_cell(h: dict, hid: str) -> str:
    v = h[hid]
    if hid in ("H1", "H2", "H3"):
        return f"{v['k']} of {v['n']} ({pe.pct(v['share'])})"
    if hid == "H4":
        return f"{v['mean']:+.2f} h ({v['ci'][0]:+.2f} to {v['ci'][1]:+.2f})"
    if hid == "H5":
        return f"{v['coverage']:.4f}"
    e, s = v["policies"]["envelope"], v["policies"]["shortest"]
    return (
        f"P(viol) {pe.pct(e['p_violation_mean'])} vs {pe.pct(s['p_violation_mean'])}; "
        f"finish {e['finish_mean']:.1f} vs {s['finish_mean']:.1f} min"
    )


def render(before: dict, after: dict) -> str:
    hb, ha = before["hypotheses"], after["hypotheses"]
    verdict = {True: "HIT", False: "MISS"}
    same_raw = before["raw"] == after["raw"]
    changed = [k for k in hb if hb[k]["hit"] != ha[k]["hit"]]
    lines = [
        "# Preregistered evaluation v0.6: addendum after the Jackal profile fix",
        "",
        "Dated 16 October 2026. Rendered by `examples/prereg_eval_fixed_profile.py` from",
        "`examples/prereg_results.json` (before) and `examples/prereg_results_fixed_profile.json` (after).",
        "`tests/test_prereg_addendum.py` fails if this document differs from what the code renders.",
        "`docs/preregistration-v0.6.md` and `docs/prereg-results.md` are unchanged; hypotheses and criteria",
        "are exactly those preregistered. **SYNTHETIC world**, as in the original run.",
        "",
        "## Why a rerun",
        "",
        "Branch `fix/jackal-rated-ambient` changed three assumed conductances of `clearpath_jackal` so the",
        "profile is consistent with its rated 45 degC ambient. The evaluation was rerun on the fixed profile",
        "with the same seeds, cases, policies and code.",
        "",
        f"The preregistered evaluation uses only `{pe.BASE.id}` (preregistration, Fixed design), whose",
        f"profile file is unchanged by the fix (sha256 prefix `{profile_hash(pe.BASE.id)}`). The Jackal",
        "profile does not enter any of H1 to H6.",
        "",
        "## Before and after",
        "",
        "| ID | Before | After | Verdict before | Verdict after |",
        "|---|---|---|---|---|",
    ]
    for k in hb:
        lines.append(
            f"| {k} | {result_cell(hb, k)} | {result_cell(ha, k)} | "
            f"{verdict[hb[k]['hit']]} | {verdict[ha[k]['hit']]} |"
        )
    n_b = sum(bool(v["hit"]) for v in hb.values())
    n_a = sum(bool(v["hit"]) for v in ha.values())
    lines += [
        "",
        f"Hits before: {n_b} of {len(hb)}. Hits after: {n_a} of {len(ha)}.",
        f"Raw per run results identical before and after: {'yes' if same_raw else 'no'}.",
        "",
        "## What changed and why",
        "",
    ]
    if not changed and same_raw:
        lines += [
            "Nothing changed. Every hit and miss of `docs/prereg-results.md` stands, and every number is",
            "identical, because the evaluation never used the Jackal profile. The earlier statement that the",
            "preregistered result described the unfixed Jackal profile was wrong; it described the medium",
            "UGV, and so does this rerun.",
        ]
    elif not changed:
        lines += [
            "No verdict changed. Some raw numbers differ; see the two JSON files for the runs concerned.",
        ]
    else:
        lines += [f"Verdicts changed for: {', '.join(changed)}. See the table above."]
    return "\n".join(lines) + "\n"


def main() -> int:
    before = json.loads(BEFORE.read_text(encoding="utf-8"))
    if "--render-only" in sys.argv:
        after = json.loads(AFTER.read_text(encoding="utf-8"))
    else:
        raw = pe.evaluate()
        after = {"design": "docs/preregistration-v0.6.md", **pe.analyse(raw), "raw": raw}
        AFTER.write_text(json.dumps(after, indent=1), encoding="utf-8")
        after = json.loads(AFTER.read_text(encoding="utf-8"))
    DOC.write_text(render(before, after), encoding="utf-8")
    print(DOC.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
