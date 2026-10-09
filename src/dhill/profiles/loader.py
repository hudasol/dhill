"""Load robot profiles from YAML and list the built-in set."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from .schema import Profile

_BUILTIN_PKG = "dhill.profiles.builtin"


def _flatten_parameters(sections: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Turn ``{section: {name: value | {value, source, note}}}`` into dotted keys.

    A section may set ``_source`` (and optionally ``_note``) as the default
    provenance for bare numbers in that section, and ``_rel_sigma`` a default
    relative uncertainty.
    """
    flat: dict[str, dict[str, Any]] = {}
    for section, body in sections.items():
        if not isinstance(body, dict):
            raise ValueError(f"parameter section '{section}' must be a mapping")
        default_source = body.get("_source", "assumption")
        default_note = body.get("_note")
        default_rel = body.get("_rel_sigma")
        for name, raw in body.items():
            if name.startswith("_"):
                continue
            key = f"{section}.{name}"
            base: dict[str, Any] = {"source": default_source, "note": default_note}
            if default_rel is not None:
                base["rel_sigma"] = default_rel
            spec = {**base, **raw} if isinstance(raw, dict) else {**base, "value": raw}
            flat[key] = spec
    return flat


def profile_from_dict(data: dict[str, Any]) -> Profile:
    """Build and validate a profile from parsed YAML."""
    body = dict(data)
    body["parameters"] = _flatten_parameters(body.get("parameters", {}))
    return Profile.model_validate(body)


def load_profile_file(path: str | Path) -> Profile:
    """Load a profile from a YAML file."""
    with open(path, encoding="utf-8") as fh:
        return profile_from_dict(yaml.safe_load(fh))


def builtin_profile_ids() -> list[str]:
    files = resources.files(_BUILTIN_PKG)
    return sorted(p.name[: -len(".yaml")] for p in files.iterdir() if p.name.endswith(".yaml"))


def load_builtin(profile_id: str) -> Profile:
    """Load a built-in profile by id."""
    files = resources.files(_BUILTIN_PKG)
    target = files.joinpath(f"{profile_id}.yaml")
    if not target.is_file():
        raise KeyError(f"unknown profile '{profile_id}'; available: {builtin_profile_ids()}")
    return profile_from_dict(yaml.safe_load(target.read_text(encoding="utf-8")))


def load_profile(ref: str | Path) -> Profile:
    """Load by built-in id or by file path."""
    s = str(ref)
    if s.endswith((".yaml", ".yml")) or Path(s).exists():
        return load_profile_file(s)
    return load_builtin(s)
