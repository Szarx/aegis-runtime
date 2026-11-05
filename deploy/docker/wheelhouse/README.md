# Optional dependency cache

Normally the Collector image installs pinned packages from PyPI. This directory may contain SHA-256-verified Linux x86_64 / Python 3.12 or universal wheels for an offline build; wheel files are ignored by Git.

If any wheels are supplied, the build installs entirely from this cache and fails if the pinned set is incomplete. An empty directory uses the normal online install path. Windows-only binary wheels cannot be used in the Linux image.

The SPEC-002 validation used official PyPI files and saved source URLs / hashes in the resource dependency receipts. Cache files are development artifacts, not source code or a published package bundle.

SPEC-004 updates the complete pinned set to 39 packages, including the optional OpenAI SDK used in development validation. Its Linux receipt is [spec004-python-linux.json](../../../resources/downloads/spec004-python-linux.json); the SPEC-002 historical receipt is preserved.

SPEC-006 uses 59 pinned packages, adding the optional LangGraph development integration while preserving the previous 39 versions. Current Linux receipt: [spec006-python-linux.json](../../../resources/downloads/spec006-python-linux.json). Historical receipts remain unchanged.

SPEC-014 keeps the existing59 versions and adds3 optional SQLite packages, for62 pins. Current receipt: [spec014-python-linux.json](../../../resources/downloads/spec014-python-linux.json). SPEC-006 receipts remain historical.
