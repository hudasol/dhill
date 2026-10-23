# Release checklist for v0.6.0

For the owner, on her own machine. Run the steps in order; each command is meant to be copied as is (Git Bash
or a Unix shell; on Windows PowerShell use `py` for `python`).

## Status on 18 October 2026

| Step | Status |
|---|---|
| 1 Merge what is ready | Done: #9 to #15 merged; #2 to #7 closed as superseded by #9; no pull request open |
| 2 Clean clone check | Done: install, CLI commands and tests passed from a fresh clone |
| 3 Version and changelog | Done: version 0.6.0, `CHANGELOG.md` entry |
| 4 Tags | Done: v0.6.0 pushed; v0.0.1 to v0.5.0 were already on GitHub |
| 5 Licence decision | Done: Apache-2.0 (ADR 0002 accepted, 23 October 2026) |
| 6 Literature exports | Open: needs institutional access |

## 1. Merge what is ready

Open pull requests at the time of writing: #14 (preregistered evaluation v0.7 of the Jackal) and the third
overnight report. Pull requests #2 to #7 are superseded by #9 (each of their heads is contained in it) and can
be closed without merging. Branches `alt/*` are duplicates from a parallel session.

## 2. Check main from a clean clone

The quick start was checked this way on 18 October 2026 (149 tests, `dhill list sites`, `dhill decide`,
`dhill timeline` all worked).

```bash
git clone https://github.com/hudasol/dhill.git dhill-release
cd dhill-release
python -m venv .venv
. .venv/Scripts/activate   # Windows Git Bash; use .venv/bin/activate on Linux or macOS
pip install -e ".[dev]"
ruff check . && ruff format --check .
python -m pytest -q -p no:warnings
dhill decide --site sweihan --scenario heatwave --at 2026-08-05T09:00
```

## 3. Bump the version and record the release

Edit `version = "0.5.0"` in `pyproject.toml` and `__version__ = "0.5.0"` in `src/dhill/__init__.py` to `0.6.0`,
add a `v0.6.0` row to `CHANGELOG.md` (summary: operating calendar on recorded weather, route simulation,
preregistered evaluations v0.6 and v0.7, Jackal profile fix, engine contract, evidence checks), then:

```bash
git add pyproject.toml src/dhill/__init__.py CHANGELOG.md
git commit -m "Release v0.6.0"
git push origin main
```

## 4. Tag

The earlier tags in `scripts/tag-releases.sh` (v0.0.1 to v0.5.0) are already on GitHub; rerunning the script is harmless. The new one:

```bash
bash scripts/tag-releases.sh
git tag -a v0.6.0 -m "Operating calendar, route simulation, preregistered evaluations, Jackal profile fix"
git push origin v0.6.0
git ls-remote --tags origin
```

## 5. Licence decision (ADR 0002)

Decided on 23 October 2026: Apache License 2.0 (`LICENSE`, `NOTICE`, `license = "Apache-2.0"` in
`pyproject.toml`); the reasoning is in `docs/adr/0002-licensing.md`.

## 6. Literature exports (from `docs/literature-search-protocol.md`)

Needs institutional access; not done in the unattended sessions.

1. Run the seven query strings of the protocol on IEEE Xplore, Scopus and Web of Science, adapting the syntax
   per database; also Google Scholar, arXiv, Google Patents and WIPO Patentscope.
2. For each database and query export the result list (CSV or RIS) and save it under `docs/literature/` with
   the database, query number and date in the file name.
3. Record date, database, query and hit count for each run in `docs/literature-log.md`.
4. Screen in two stages (title and abstract, then full text) and record inclusion or exclusion reasons.
5. Update the nearest works table and state in one sentence each what Dhill does differently; if a near
   duplicate exists, say so in the README.
6. Resolve the open Moore et al. 2012 citation (venue and authors) while doing so (`docs/known-issues.md` item 10).

## 7. After the release

- Check that GitHub Actions passes on the release commit.
- The Open-Meteo cache used by the calendar is only on the laptop that ran it (`~/.cache/dhill/climatology`);
  rerunning `python scripts/gen_operating_calendar.py` elsewhere downloads again (rate limited, resumable).
