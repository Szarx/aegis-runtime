"""Validate a host-owned, already connected native async SQLite saver."""

import asyncio
from importlib.metadata import version
import math
from pathlib import Path

from .durable_graph import COLUMNS, PROFILE, VERSIONS, CheckpointUnavailable


async def configure_async_reviewed_checkpointer(connection, *, timeout=3):
    """Borrow a connection; on any failure the host must close it, not reuse it."""
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 5:
        raise ValueError("invalid checkpoint configuration")
    try:
        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    except ImportError:
        raise ImportError("install aegis-runtime-control[reviewed-langgraph-async] to use async durable reviewed graphs") from None
    try:
        async with asyncio.timeout(timeout):
            if type(connection) is not aiosqlite.Connection or connection.in_transaction:
                raise CheckpointUnavailable()
            if any(version(name) != expected for name, expected in VERSIONS.items()):
                raise CheckpointUnavailable()

            async def rows(sql):
                cursor = await connection.execute(sql)
                result = await cursor.fetchall()
                # Do not await a second queued cleanup operation after a
                # failure/cancellation: the host closes the whole connection.
                await cursor.close()
                return result

            databases = await rows("PRAGMA database_list")
            if len(databases) != 1 or databases[0][1] != "main":
                raise CheckpointUnavailable()
            path = databases[0][2]
            if not path or path.startswith(("\\\\", "//")) or not Path(path).is_file():
                raise CheckpointUnavailable()
            await rows("PRAGMA busy_timeout=" + str(max(1, int(timeout * 1000))))
            if await rows("PRAGMA journal_mode") != [("wal",)]:
                raise CheckpointUnavailable()
            await rows("PRAGMA synchronous=FULL")
            if await rows("SELECT id,profile FROM aegis_checkpoint_meta") != [(1, PROFILE)]:
                raise CheckpointUnavailable()
            for table, expected in COLUMNS.items():
                if {row[1] for row in await rows("PRAGMA table_info(" + table + ")")} != expected:
                    raise CheckpointUnavailable()
            await rows("BEGIN IMMEDIATE")
            await connection.rollback()
            serializer = JsonPlusSerializer(pickle_fallback=False, allowed_json_modules=(), allowed_msgpack_modules=())
            saver = AsyncSqliteSaver(connection, serde=serializer)
            saver.jsonplus_serde = serializer
            saver.is_setup = True
            return saver
    except Exception:
        raise CheckpointUnavailable() from None
