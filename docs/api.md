# REST API

Start with `dhill serve` or `docker compose up`. Interactive documentation at `/docs`; schema at `/openapi.json`. Set `DHILL_API_KEY` to require `X-API-Key` on `/v1` routes; `DHILL_AUDIT_LOG` to append a JSONL record per decision.

| Method and path | Purpose |
|---|---|
| `GET /healthz` | Liveness |
| `GET /v1/version`, `/v1/profiles`, `/v1/sites`, `/v1/scenarios` | Listings |
| `POST /v1/envelope` | Decision for one window (`at`, `duration_h`, `mode`) |
| `POST /v1/forecast` | Decision timeline (`step_min`) |
| `POST /v1/schedule` | Fleet plan versus fixed shift baseline |

Example:
```
curl -s localhost:8080/v1/envelope -H 'content-type: application/json' \
  -d '{"site":"sweihan","scenario":"heatwave","at":"2026-08-05T09:00","duration_h":1}'
```
Limits: samples 8 to 256, days 1 to 5, duration 0.1 to 8 h, up to 8 robots. Inline profiles go in `profile_inline` (same structure as the YAML files).
