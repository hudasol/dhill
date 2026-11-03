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
Limits: samples 8 to 256 (default 64; below 64 the response carries a `warnings` entry, because decisions become unreliable, see `docs/known-issues.md` item 19), days 1 to 5, duration 0.1 to 8 h, up to 8 robots. Inline profiles go in `profile_inline` (same structure as the YAML files).

## Hardening

| Control | Setting | Behaviour |
|---|---|---|
| Request body | `DHILL_MAX_BODY_BYTES`, default 262144 | Larger `/v1` bodies get 413. |
| Rate limit | `DHILL_RATE_LIMIT_PER_MIN`, default 120, 0 switches it off | Sliding one minute window per API key or address; 429 with `Retry-After`. Liveness is never limited. |
| Concurrent computations | `DHILL_MAX_CONCURRENT`, default 4 | Further `POST /v1` requests get 503 with `Retry-After`. |
| Time fields | `at` and `start` | Must look like `2026-08-05` or `2026-08-05T09:00`; otherwise 422. |
| Errors | all | An unhandled error returns `{"detail": "internal error"}`, never a stack trace. |
| Audit log | `DHILL_AUDIT_LOG` | A failing log is reported in the service log and never fails a request. |
| Headers | all | `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`; a content security policy on the dashboard; `Cache-Control: no-store` on `/v1`. |

The rate limit and the concurrency cap are held in memory in one process. Behind several workers or
several containers, enforce them at the reverse proxy as well. The OpenAPI description is committed as
`docs/openapi.json` and a test fails if it differs from the running service.

