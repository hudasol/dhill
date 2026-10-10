#!/usr/bin/env bash
# Create and push annotated tags for each release commit listed in CHANGELOG.md.
set -euo pipefail
tag() { git tag -a "$1" "$2" -m "$3" 2>/dev/null || echo "tag $1 exists"; }
tag v0.0.1 00f7153 "Project plan and README"
tag v0.1.0 1e75158 "Core physics and profiles"
tag v0.2.0 06b57fc "Envelope engine, planner, calibration, CLI"
tag v0.3.0 0a59a22 "API, dashboard, ROS 2 recorder, Docker, CI"
tag v0.4.0 "${1:-0e1dcb7}" "Docs, results, release tooling"
git push origin v0.0.1 v0.1.0 v0.2.0 v0.3.0 v0.4.0
