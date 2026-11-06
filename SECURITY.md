# Security

Aegis is an early source preview, not a production security boundary. Security fixes target the current main branch; no supported stable release or response-time SLA is offered yet.

## Report privately

Use GitHub's [private vulnerability report](https://github.com/Szarx/aegis-runtime/security/advisories/new) for this repository. Do not post exploits, credentials, real prompts, approval arguments or customer traces in public issues. Include the affected revision, a minimal synthetic reproduction, expected/observed behavior and impact. Use GitHub Issues for ordinary non-sensitive bugs.

If a key is exposed, revoke it with its provider. Deleting a file does not remove a secret from Git history or invalidate the key.

## Trust and deployment boundaries

- Runtime controls explicitly wrapped tools in a trusted host process. It does not sandbox processes, authenticate end users, isolate tenants or prevent a host from bypassing instrumentation.
- Static trace/request/review/execution tokens separate coarse roles, not individual users. Compose binds to loopback and uses synthetic development defaults. Configure authentication, TLS and network controls before remote deployment.
- Telemetry can be delayed, dropped or forged by a host. It is not complete, tamper-proof audit evidence. Health snapshots are process-local; heartbeat loss does not prove business failure.
- A reviewed claim stays consumed when its outcome is unknown. Do not replay business work to repair telemetry or checkpoints. Cross-system exactly-once execution is not guaranteed.
- Model/tool input and output capture is disabled by default. Reviewed execution explicitly persists complete arguments; only submit data approved for disclosure and retention.

See [capabilities](docs/capabilities.md), [architecture](ARCHITECTURE.md) and [publication material policy](docs/github-readiness.md). Keep local keys, environment files, raw traces, checkpoints, logs and screenshots out of commits and reports.
