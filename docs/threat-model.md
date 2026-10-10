# Threat model (STRIDE summary)

| Asset | Threat | Mitigation | Residual |
|---|---|---|---|
| Decision API | Unauthenticated use | Optional `X-API-Key` with constant-time compare; bind to localhost by default | Key management is the operator's job; no TLS inside the container (use a reverse proxy) |
| Decision API | Resource exhaustion | Bounded samples (8 to 256), days (1 to 5), duration, robots (8) | No rate limiting; add at the proxy |
| Profile input | Malformed or hostile profile | Pydantic validation, registry bounds, YAML `safe_load`, inline profile as data only | Large payloads should be capped at the proxy |
| Filesystem | Path traversal via profile id | Built-in ids restricted to alphanumerics, `-`, `_`; API never accepts paths | None known |
| Weather feed | Spoofed or stale forecast | Source and notes carried in output; explicit failure on fetch error; cache TTL 30 min | Trust in the provider; use own station for high-stakes |
| Audit trail | Repudiation | JSONL audit log of every decision request | Log integrity is not protected |
| Supply chain | Vulnerable dependency | `pip-audit` and CycloneDX SBOM in CI; minimal dependencies | CI first run pending |
| Container | Privilege escalation | Non-root user, read-only filesystem, `no-new-privileges` | Host hardening out of scope |
| Wrong decision | Over-trust in an L0 model | Evidence level and caveat on every decision; conservative risk quantile | Human factors; see model card |

The largest risk is not an attacker but trust in an uncalibrated model. The design response is visibility of evidence, not hidden confidence.
