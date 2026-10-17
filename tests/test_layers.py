"""Layer rules: the physics layer must not depend on the profile layer."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

PHYSICS = Path(__file__).parents[1] / "src" / "dhill" / "physics"


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            out.append("." * node.level + (node.module or ""))
        elif isinstance(node, ast.Import):
            out += [a.name for a in node.names]
    return out


def test_physics_source_imports_no_profile_code():
    offenders = [
        (f.name, mod)
        for f in sorted(PHYSICS.glob("*.py"))
        for mod in _imports(f)
        if "profiles" in mod
    ]
    assert offenders == []


def test_importing_physics_does_not_load_profiles():
    code = (
        "import sys, dhill.physics.thermal; "
        "print(any(m.startswith('dhill.profiles') for m in sys.modules))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


def test_deprecated_alias_gives_the_same_parameters():
    import numpy as np

    from dhill.physics.thermal import ThermalParams
    from dhill.profiles import load_builtin, thermal_params

    prof = load_builtin("clearpath_jackal")
    a = ThermalParams.from_profile(prof, n=8, mc=True, rng=np.random.default_rng(3))
    b = thermal_params(prof, n=8, mc=True, rng=np.random.default_rng(3))
    assert np.array_equal(a.ua_si, b.ua_si) and np.array_equal(a.d_temp_k, b.d_temp_k)
