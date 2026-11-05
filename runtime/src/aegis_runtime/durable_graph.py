"""Owned, versioned local SQLite checkpoints; optional framework imports."""

from contextlib import contextmanager
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import sqlite3

VERSIONS = {"langgraph": "1.2.15", "langgraph-checkpoint": "4.3.0", "langgraph-checkpoint-sqlite": "3.1.2"}
PROFILE = json.dumps({"format": 1, "versions": VERSIONS, "serde": "builtin-safe-only-no-pickle-v1"},
                     sort_keys=True, separators=(",", ":"))
COLUMNS = {
    "checkpoints": {"thread_id", "checkpoint_ns", "checkpoint_id", "parent_checkpoint_id", "type", "checkpoint", "metadata"},
    "writes": {"thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "task_path", "idx", "channel", "type", "value"},
}


class CheckpointUnavailable(RuntimeError):
    def __init__(self):
        super().__init__("local reviewed checkpoint unavailable")


def _open(path, create, timeout):
    if type(create) is not bool or type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 5:
        raise ValueError("invalid checkpoint configuration")
    if not isinstance(path, (str, Path)) or not str(path) or str(path) == ":memory:" or str(path).lower().startswith("file:"):
        raise ValueError("explicit local checkpoint file required")
    path = Path(path).absolute()
    if str(path).startswith(("\\\\", "//")) or not path.parent.is_dir() or path.is_dir():
        raise ValueError("explicit local checkpoint file required")
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    except ImportError:
        raise ImportError("install aegis-runtime-control[reviewed-langgraph-sqlite] to use durable reviewed graphs") from None
    connection = None
    try:
        if any(version(name) != expected for name, expected in VERSIONS.items()):
            raise CheckpointUnavailable()
        if create:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
        connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, check_same_thread=False, timeout=timeout)
        connection.execute("PRAGMA synchronous=FULL")
        if create:
            if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
                raise CheckpointUnavailable()
        elif connection.execute("PRAGMA journal_mode").fetchone() != ("wal",):
            raise CheckpointUnavailable()
        serializer = JsonPlusSerializer(pickle_fallback=False, allowed_json_modules=(), allowed_msgpack_modules=())
        saver = SqliteSaver(connection, serde=serializer)
        saver.jsonplus_serde = serializer
        if create:
            saver.setup()
            connection.execute("CREATE TABLE aegis_checkpoint_meta (id INTEGER PRIMARY KEY CHECK(id=1), profile TEXT NOT NULL)")
            connection.execute("INSERT INTO aegis_checkpoint_meta VALUES (1, ?)", (PROFILE,))
            connection.commit()
        else:
            if connection.execute("SELECT id,profile FROM aegis_checkpoint_meta").fetchall() != [(1, PROFILE)]:
                raise CheckpointUnavailable()
            for table, expected in COLUMNS.items():
                # Both table names are fixed above, never taken from a caller.
                if {row[1] for row in connection.execute("PRAGMA table_info(" + table + ")")} != expected:
                    raise CheckpointUnavailable()
            saver.is_setup = True  # Existing files must never run automatic schema setup/migration.
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
        return connection, saver
    except Exception:
        if connection is not None:
            connection.close()
        raise CheckpointUnavailable() from None


@contextmanager
def open_reviewed_checkpointer(path, *, create=False, timeout=3):
    """Create exclusively or reopen an existing owned file; never reset state."""
    connection, saver = _open(path, create, timeout)
    failed = False
    try:
        yield saver
    except BaseException:
        failed = True
        raise
    finally:
        try:
            connection.close()
        except Exception:
            if not failed:
                raise CheckpointUnavailable() from None
