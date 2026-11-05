"""PostgreSQL persistence; no fallback database."""

from .postgres import PostgresSpanStore, StorageError

__all__ = ["PostgresSpanStore", "StorageError"]
