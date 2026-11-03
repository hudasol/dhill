"""WCAG 2.1 contrast check for the Dhill theme (`src/dhill/web/theme.css`).

Text pairs must reach 4.5:1 (AA, normal text). Graphical objects, focus rings and the edges of form controls
must reach 3:1 (AA, non text). The script prints every pair and exits with status 1 if any fails.
Run: python scripts/check_contrast.py [path/to/theme.css]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[1] / "src" / "dhill" / "web" / "theme.css"

# (foreground token, background token or hex, minimum ratio, what it is)
PAIRS = [
    ("ink", "pearl", 4.5, "body text on page"),
    ("ink", "#ffffff", 4.5, "body text on cards"),
    ("ink", "sakura-50", 4.5, "body text on form panel"),
    ("ink", "sakura-100", 4.5, "body text on tinted rows"),
    ("mute", "pearl", 4.5, "secondary text on page"),
    ("mute", "#ffffff", 4.5, "secondary text on cards"),
    ("mute", "sakura-50", 4.5, "secondary text on form panel"),
    ("on-rose", "rose", 4.5, "button text"),
    ("rose", "pearl", 4.5, "link text on page"),
    ("go", "pearl", 4.5, "GO label on page"),
    ("go", "#ffffff", 4.5, "GO label on cards"),
    ("derate", "pearl", 4.5, "DERATE label on page"),
    ("derate", "#ffffff", 4.5, "DERATE label on cards"),
    ("park", "pearl", 4.5, "PARK label on page"),
    ("park", "#ffffff", 4.5, "PARK label on cards"),
    ("go-fill", "pearl", 3.0, "GO bar"),
    ("derate-fill", "pearl", 3.0, "DERATE bar"),
    ("park-fill", "pearl", 3.0, "PARK marker"),
    ("focus", "pearl", 3.0, "focus ring"),
    ("edge", "#ffffff", 3.0, "form control edge"),
    ("edge", "pearl", 3.0, "form control edge on page"),
]


def load_tokens(path: Path) -> dict[str, str]:
    css = path.read_text(encoding="utf-8")
    return {
        m.group(1): m.group(2).lower()
        for m in re.finditer(r"--([\w-]+)\s*:\s*(#[0-9a-fA-F]{6})", css)
    }


def luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    rgb = [int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def check(path: Path = DEFAULT) -> list[tuple[str, str, float, float, str, bool]]:
    tok = load_tokens(path)

    def get(name: str) -> str:
        return name if name.startswith("#") else tok[name]

    out = []
    for fg, bg, need, what in PAIRS:
        r = ratio(get(fg), get(bg))
        out.append((fg, bg, r, need, what, r >= need))
    return out


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    rows = check(path)
    for fg, bg, r, need, what, ok in rows:
        print(f"{'pass' if ok else 'FAIL'}  {r:5.2f}:1 (needs {need:g})  {fg} on {bg}  {what}")
    bad = [r for r in rows if not r[5]]
    print(f"{len(rows) - len(bad)} of {len(rows)} pairs pass WCAG 2.1 AA")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
