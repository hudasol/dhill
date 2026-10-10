"""Generate docs/parameters.md from the parameter registry (single source of truth)."""

from pathlib import Path

from dhill.profiles.registry import PARAMS, SOURCE_SIGMA

lines = [
    "# Parameter reference",
    "",
    "Generated from `src/dhill/profiles/registry.py` by `scripts/gen_parameters_doc.py`. Do not edit by hand.",
    "",
    "Monte Carlo spread by provenance (relative one-sigma, lognormal): "
    + ", ".join(f"{k} {v:.0%}" for k, v in SOURCE_SIGMA.items())
    + ". A profile may override a spread with `rel_sigma` (for example cell counts use 0).",
    "",
    "| Key | Unit | Bounds | Optional (default) | Meaning |",
    "|---|---|---|---|---|",
]
for key, d in PARAMS.items():
    opt = f"yes ({d.default:g})" if d.optional else "no"
    lines.append(f"| `{key}` | {d.unit} | {d.lo:g} to {d.hi:g} | {opt} | {d.desc} |")
Path(__file__).resolve().parents[1].joinpath("docs/parameters.md").write_text(
    "\n".join(lines) + "\n", encoding="utf-8"
)
print(f"wrote {len(PARAMS)} parameters")
