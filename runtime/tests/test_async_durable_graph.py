import asyncio
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import aiosqlite

from aegis_runtime.async_durable_graph import configure_async_reviewed_checkpointer
from aegis_runtime.durable_graph import CheckpointUnavailable,open_reviewed_checkpointer
from tests.fixtures.async_reviewed import Transport,client
from tests.fixtures.async_graph import gate,build,config,initial


class AsyncDurableGraph(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix='aegis async ');self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'本机 %.sqlite3'
        # Startup initialization is synchronous and precedes native async I/O.
        with open_reviewed_checkpointer(self.path,create=True):pass

    async def test_ac1503_native_saver_reopen_sync_format_and_host_ownership(self):
        transport=Transport();calls=[]
        async def write(value=1):calls.append(value);return value
        async with client(transport) as connection:
            async with aiosqlite.connect(self.path.as_uri()+'?mode=rw',uri=True) as database:
                worker=database._thread
                saver=await configure_async_reviewed_checkpointer(database)
                self.assertIs(saver.serde,saver.jsonplus_serde);self.assertTrue(saver.is_setup)
                governed=gate(write,connection);graph=build(governed,saver)
                await graph.ainvoke(initial(),config(),durability='sync')
                ticket=await governed.prepare(graph,config(),summary='Synthetic async SQLite')
                self.assertTrue(worker.is_alive())
            worker.join(timeout=2);self.assertFalse(worker.is_alive())
            transport.approve(ticket['action_id'])
            async with aiosqlite.connect(self.path.as_uri()+'?mode=rw',uri=True) as database:
                saver=await configure_async_reviewed_checkpointer(database)
                fresh=gate(write,connection);graph=build(fresh,saver)
                self.assertEqual((await fresh._capture(graph,config()))[0],ticket['graph_binding'])
                result=await fresh.resume(graph,config(),ticket)
                self.assertEqual(result.continuation,'resumed')
                async with database.execute('PRAGMA synchronous') as cursor:self.assertEqual(await cursor.fetchone(),(2,))
                with self.assertRaises(NotImplementedError):saver.serde.loads_typed(('pickle',b'forbidden'))
        with open_reviewed_checkpointer(self.path) as saver:
            final=build(gate(write,connection),saver).get_state(config())
            self.assertEqual(final.next,());self.assertEqual(final.values['aegis_reviewed']['action_id'],ticket['action_id'])
        self.assertEqual(calls,[1])

    async def test_ac1503_unowned_wrong_format_attached_and_transaction_fail_closed(self):
        for timeout in (True,0,6,float('nan')):
            with self.assertRaises(ValueError):await configure_async_reviewed_checkpointer(None,timeout=timeout)
        for kind in ('memory','unknown','attached','transaction','version','columns'):
            async with aiosqlite.connect(':memory:' if kind=='memory' else self.path) as database:
                if kind=='unknown':await database.execute("UPDATE aegis_checkpoint_meta SET profile='{}'");await database.commit()
                if kind=='attached':await database.execute("ATTACH DATABASE ':memory:' AS extra")
                if kind=='transaction':await database.execute('BEGIN')
                if kind=='columns':await database.execute('DROP TABLE writes');await database.commit()
                with patch('aegis_runtime.async_durable_graph.version',return_value='changed') if kind=='version' else patch('aegis_runtime.async_durable_graph.version',wraps=__import__('importlib.metadata',fromlist=['version']).version):
                    with self.assertRaisesRegex(CheckpointUnavailable,'^local reviewed checkpoint unavailable$'):
                        await configure_async_reviewed_checkpointer(database)
                self.assertTrue(database._thread.is_alive())
            # Restore the metadata for the remaining independent cases.
            if kind=='unknown':
                from aegis_runtime.durable_graph import PROFILE
                async with aiosqlite.connect(self.path) as database:
                    await database.execute('UPDATE aegis_checkpoint_meta SET profile=?',(PROFILE,));await database.commit()

    async def test_ac1503_cancel_queued_sql_preserves_signal_and_host_drains_worker(self):
        entered=threading.Event();release=threading.Event();seen=[]
        async with aiosqlite.connect(self.path) as database:
            worker=database._thread
            await database.create_function('hold',0,lambda: (entered.set(),release.wait(3),1)[2])
            queued=asyncio.create_task(database.execute('SELECT hold()'))
            while not entered.is_set():await asyncio.sleep(.001)
            async def configure():
                try:await configure_async_reviewed_checkpointer(database)
                except asyncio.CancelledError as error:seen.append(error);raise
            task=asyncio.create_task(configure());await asyncio.sleep(.01);task.cancel('queued SQL')
            try:
                with self.assertRaises(asyncio.CancelledError) as error:await task
                self.assertIs(error.exception,seen[0]);self.assertTrue(worker.is_alive())
            finally:release.set();cursor=await queued;await cursor.close()
        worker.join(timeout=2);self.assertFalse(worker.is_alive())

    async def test_ac1503_total_configuration_deadline_and_host_cleanup(self):
        entered=threading.Event();release=threading.Event()
        async with aiosqlite.connect(self.path) as database:
            worker=database._thread
            await database.create_function('hold',0,lambda: (entered.set(),release.wait(3),1)[2])
            queued=asyncio.create_task(database.execute('SELECT hold()'))
            while not entered.is_set():await asyncio.sleep(.001)
            try:
                with self.assertRaises(CheckpointUnavailable):
                    await asyncio.wait_for(configure_async_reviewed_checkpointer(database,timeout=.02),.5)
            finally:release.set();cursor=await queued;await cursor.close()
        worker.join(timeout=2);self.assertFalse(worker.is_alive())
        # execute() can return the first row before fetchall() starts a slow
        # second row. Cursor cleanup must not extend the configuration timeout.
        entered.clear();release.clear()
        async with aiosqlite.connect(self.path) as database:
            await database.execute('ALTER TABLE aegis_checkpoint_meta RENAME TO original_meta')
            await database.execute('CREATE VIEW aegis_checkpoint_meta AS SELECT id,profile FROM original_meta UNION ALL SELECT 2,hold()')
            await database.commit()
        async with aiosqlite.connect(self.path) as database:
            worker=database._thread
            await database.create_function('hold',0,lambda: (entered.set(),release.wait(2),'invalid')[2])
            started=time.monotonic()
            try:
                with self.assertRaises(CheckpointUnavailable):await configure_async_reviewed_checkpointer(database,timeout=.2)
                self.assertTrue(entered.is_set());self.assertLess(time.monotonic()-started,.9)
            finally:release.set()
        worker.join(timeout=2);self.assertFalse(worker.is_alive())
