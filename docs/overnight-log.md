# Overnight log

Working memory for the unattended session of 15 October 2026. One line per finished or abandoned step,
local time (UTC+4).

- 14:35 Repository was not present in the session folder; cloned https://github.com/hudasol/dhill.
- 14:36 Branch profile/clearpath-jackal is not merged into main; all work branches from it.
- 14:39 Baseline: `pip install -e ".[dev]"` in a local virtual environment; 110 tests pass; ruff check and ruff format clean.
- 14:41 Open-Meteo archive and air quality endpoints reachable. CAMS PM10 through the air quality API returns null before 2022-08; earlier hours need a stated fill.
- 14:42 Task branches are stacked (each starts from the previous task branch) because nothing is merged yet; each pull request targets the branch below it.
- 14:58 Task 1 done: climatology module, dhill calendar CLI, 12 tests on trimmed real fixtures, calendar for six sites 2015 to 2025 with no download gaps. Finding: the L0 Jackal profile returns GO only below about 20 degC air (compute die binds in every non GO hour), which contradicts the 45 degC datasheet rating; documented as a profile problem, not a robot property.
