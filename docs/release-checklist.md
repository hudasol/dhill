# Release checklist for v0.7.0

For the owner, on her own machine, in Windows PowerShell 5.1. Copy each block as is. v0.6.0 was tagged on
18 October 2026 by the same procedure; v1.0.0 is reserved for field data (`docs/roadmap-to-v1.md`).

## Status on 23 October 2026

| Step | Status |
|---|---|
| 1 Merge what is ready | Done: no pull request open; all work since v0.6.0 is on `main` |
| 2 Clean clone check | Owner: run the block below |
| 3 Version and changelog | Done: version 0.7.0 in `pyproject.toml` and `src/dhill/__init__.py`, `CHANGELOG.md` entry |
| 4 Tag | Owner: run the block below |
| 5 Licence decision | Done: Apache-2.0 (ADR 0002 accepted, 23 October 2026) |
| 6 Literature exports | Open: needs institutional access |

## 1. Merge what is ready

Nothing is open. Branches `alt/*` are duplicates from a parallel session; leave them.

## 2. Check main from a clean clone

```powershell
cd $HOME\Downloads
git clone https://github.com/hudasol/dhill.git dhill-release
cd dhill-release
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
ruff check .; if ($?) { ruff format --check . }; if ($?) { python -m pytest -q -p no:warnings }
dhill --version
dhill decide --site sweihan --scenario heatwave --at 2026-08-05T09:00
```

`dhill --version` must print `dhill 0.7.0`, and every check must pass. If `Activate.ps1` is blocked, run
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that window only.

## 3. Bump the version and record the release

Already done on `main` (version 0.7.0 and the `CHANGELOG.md` entry). Nothing to run.

## 4. Tag

Run in your usual clone, on an up to date `main`:

```powershell
git switch main
git pull
git log --oneline -1
git tag -a v0.7.0 -m "Field day validation command, Apache 2.0 licence, logging session quickstart, Jackal sensitivity"
git push origin v0.7.0
git ls-remote --tags origin
```

`git ls-remote` must list `refs/tags/v0.7.0`. Then copy the commit printed by `git log --oneline -1` into the
v0.7.0 row of `CHANGELOG.md`, commit with the message `Changelog: record the v0.7.0 tag commit` and push. To
publish a GitHub release as well, open https://github.com/hudasol/dhill/releases/new, choose the tag
`v0.7.0`, and paste the v0.7.0 section of `CHANGELOG.md`.

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
