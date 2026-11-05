import builtins
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import Mock,patch

import ormsgpack
from aegis_runtime.durable_graph import CheckpointUnavailable,open_reviewed_checkpointer
from tests.fixtures.graph_reviewed import Transport,gate,build,config,initial
from tests.fixtures.reviewed import client


class DurableGraph(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix='aegis durable ')
        self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'本机 %.sqlite3'

    def test_ac1401_explicit_file_create_and_reopen_never_reset(self):
        with self.assertRaises(CheckpointUnavailable):
            with open_reviewed_checkpointer(self.path):pass
        self.assertFalse(self.path.exists())
        with open_reviewed_checkpointer(self.path,create=True) as saver:
            self.assertEqual(saver.conn.execute('PRAGMA journal_mode').fetchone(),('wal',))
            self.assertEqual(saver.conn.execute('PRAGMA synchronous').fetchone(),(2,))
            self.assertTrue(saver.is_setup)
        old=self.path.read_bytes()
        with self.assertRaises(CheckpointUnavailable):
            with open_reviewed_checkpointer(self.path,create=True):pass
        self.assertEqual(self.path.read_bytes(),old)
        with open_reviewed_checkpointer(self.path) as saver:self.assertTrue(saver.is_setup)

    def test_ac1401_invalid_paths_and_bounded_timeout_are_rejected(self):
        for path in (':memory:','file:test?mode=memory','',Path(self.directory.name),Path(self.directory.name)/'missing'/'db'):
            with self.assertRaises(ValueError):
                with open_reviewed_checkpointer(path,create=True):pass
        for timeout in (True,0,6,float('inf'),float('nan')):
            with self.assertRaises(ValueError):
                with open_reviewed_checkpointer(self.path,timeout=timeout):pass
        with self.assertRaises(ValueError):
            with open_reviewed_checkpointer(self.path,create=1):pass

    def test_ac1401_unknown_corrupt_or_wrong_profile_is_not_initialized(self):
        with closing(sqlite3.connect(self.path)) as connection:connection.execute('CREATE TABLE unrelated (value TEXT)')
        with self.assertRaises(CheckpointUnavailable):
            with open_reviewed_checkpointer(self.path):pass
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(),[('unrelated',)])
        corrupt=Path(self.directory.name)/'corrupt.sqlite3';corrupt.write_bytes(b'not a database')
        with self.assertRaises(CheckpointUnavailable):
            with open_reviewed_checkpointer(corrupt):pass
        self.assertEqual(corrupt.read_bytes(),b'not a database')
        valid=Path(self.directory.name)/'valid.sqlite3'
        with open_reviewed_checkpointer(valid,create=True) as saver:
            saver.conn.execute("UPDATE aegis_checkpoint_meta SET profile='{}'");saver.conn.commit()
        with self.assertRaises(CheckpointUnavailable):
            with open_reviewed_checkpointer(valid):pass

    def test_ac1401_missing_columns_and_changed_dependency_fail_without_migration(self):
        with open_reviewed_checkpointer(self.path,create=True) as saver:
            saver.conn.execute('DROP TABLE writes');saver.conn.commit()
        with self.assertRaises(CheckpointUnavailable):
            with open_reviewed_checkpointer(self.path):pass
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("SELECT name FROM sqlite_master WHERE name='writes'").fetchall(),[])
        other=Path(self.directory.name)/'version.sqlite3'
        with patch('aegis_runtime.durable_graph.version',return_value='changed'):
            with self.assertRaises(CheckpointUnavailable):
                with open_reviewed_checkpointer(other,create=True):pass
        self.assertFalse(other.exists())

    def test_ac1401_lock_wait_is_bounded_and_errors_do_not_leak_paths(self):
        with open_reviewed_checkpointer(self.path,create=True) as saver:
            saver.conn.execute('BEGIN IMMEDIATE')
            started=time.monotonic()
            with self.assertRaises(CheckpointUnavailable) as error:
                with open_reviewed_checkpointer(self.path,timeout=.03):pass
            self.assertLess(time.monotonic()-started,.8)
            self.assertEqual(str(error.exception),'local reviewed checkpoint unavailable')
            saver.conn.rollback()
        with patch('aegis_runtime.durable_graph.sqlite3.connect',side_effect=sqlite3.OperationalError('private readonly path')):
            with self.assertRaises(CheckpointUnavailable) as error:
                with open_reviewed_checkpointer(self.path):pass
            self.assertNotIn('private',str(error.exception))

    def test_ac1401_context_closes_connection_and_preserves_body_error(self):
        original=ValueError('private business failure')
        with self.assertRaises(ValueError) as error:
            with open_reviewed_checkpointer(self.path,create=True) as saver:raise original
        self.assertIs(error.exception,original)
        with self.assertRaises(sqlite3.ProgrammingError):saver.conn.execute('SELECT 1')
        with open_reviewed_checkpointer(self.path) as reopened:self.assertIsNotNone(reopened)

    def test_ac1401_missing_extra_and_serializer_cannot_import_custom_or_unpickle(self):
        native=builtins.__import__
        def missing(name,*args,**kwargs):
            if name=='langgraph.checkpoint.sqlite':raise ImportError('missing')
            return native(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=missing):
            with self.assertRaises(ImportError) as error:
                with open_reviewed_checkpointer(self.path,create=True):pass
        self.assertIn('[reviewed-langgraph-sqlite]',str(error.exception));self.assertFalse(self.path.exists())
        with open_reviewed_checkpointer(self.path,create=True) as saver:
            serializer=saver.serde;self.assertIs(saver.jsonplus_serde,serializer)
            with patch('pickle.loads',side_effect=AssertionError('must not load')) as load:
                with self.assertRaises(NotImplementedError):serializer.loads_typed(('pickle',b'forbidden'))
                load.assert_not_called()
            raw=ormsgpack.packb(ormsgpack.Ext(2,ormsgpack.packb(['forbidden_module','Danger',{'plain':1}])))
            with patch('importlib.import_module',side_effect=AssertionError('must not import')) as load:
                with self.assertLogs('langgraph.checkpoint.serde.jsonplus',level='WARNING'):
                    self.assertEqual(serializer.loads_typed(('msgpack',raw)),{'plain':1})
                load.assert_not_called()

    def test_ac1402_actual_graph_snapshot_and_sync_completion_survive_close_reopen(self):
        transport=Transport();connection=client();connection._send=Mock(side_effect=transport.send)
        calls=[];value=object()
        def write(record='synthetic'):calls.append(record);return value
        governed=gate(write,connection);cfg=config()
        with open_reviewed_checkpointer(self.path,create=True) as saver:
            graph=build(governed,saver);graph.invoke(initial(),cfg,durability='sync')
            ticket=governed.prepare(graph,cfg,summary='Synthetic persistent graph')
        transport.approve(ticket)
        with open_reviewed_checkpointer(self.path) as saver:
            fresh=gate(write,connection);graph=build(fresh,saver)
            self.assertEqual(fresh._capture(graph,cfg)[0],ticket['graph_binding'])
            native=graph.invoke
            with patch.object(graph,'invoke',wraps=native) as invoke:
                result=fresh.resume(graph,cfg,json.loads(json.dumps(ticket)))
            self.assertEqual(invoke.call_args.kwargs['durability'],'sync')
            self.assertIs(result.value,value);self.assertEqual(result.continuation,'resumed')
        with open_reviewed_checkpointer(self.path) as saver:
            final=build(gate(write,connection),saver).get_state(cfg)
            self.assertEqual(final.next,());self.assertEqual(final.values['aegis_reviewed']['action_id'],ticket['action_id'])
        self.assertEqual(calls,['synthetic'])
