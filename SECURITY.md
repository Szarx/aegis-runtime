# Security reporting and scope

This is a private development snapshot. No public security reporting channel or production support policy has been established. Share suspected issues with the repository owner through an existing private channel; exclude credentials and real agent payloads. A reporting channel must be selected before making the repository public.

Runtime controls cover explicitly wrapped tools in a trusted host process. They do not provide process isolation, external user authentication, tenant separation, tamper-proof audit, or distributed exactly-once effects. Telemetry can fail independently of authorization. Reviewed claims remain consumed when results are unknown; do not replay business work to repair a trace or checkpoint.

Do not commit model keys, approval keys, environment files, checkpoints or real traces. Local Compose credentials and test tokens are synthetic development defaults. See [architecture](ARCHITECTURE.md) and [GitHub preparation](docs/github-readiness.md) for verified scope and release boundaries.
