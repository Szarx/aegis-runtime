import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from aegis_policy import Policy,Rule
from scripts.replay_security import replay_bundle
from scripts.security_export import filters,read_bundle,verify_bundle,write_bundle
from tests.contract.test_security_export import row

ROOT=Path(__file__).resolve().parents[2]


def candidate(revision='v1'):
    return Policy(revision,(Rule('allow','allow',('reader',),('lookup',),('orders.read',)),))


def replay_rows():
    rows=[row(i) for i in range(1,7)]
    rows[1].update(effect='allow',reason='explicit_allow',rule_id='allow',outcome='completed',status='UNSET')
    rows[2].update(effect='allow',reason='explicit_allow',rule_id='write',permission='orders.write',outcome='error')
    rows[3].update(permission='orders.write')
    rows[4].update(effect='allow',reason='explicit_allow',rule_id='write',permission='orders.write',outcome='cancelled')
    rows[5].update(subject=None,reason='identity_missing',rule_id=None)
    return rows


class EventReplay(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.folder=Path(self.tmp.name)
        self.bundle=self.folder/'bundle'
    def write(self,rows):
        now=time.time_ns();return write_bundle(self.bundle,rows,filters({},now),now)

    def test_ac2401_read_bundle_returns_verified_snapshot_and_replay_reads_each_file_once(self):
        expected=self.write([row()]);manifest,rows=read_bundle(self.bundle)
        self.assertEqual(manifest,expected);self.assertEqual(verify_bundle(self.bundle),manifest)
        opened=[];original=Path.open
        def recording(path,*args,**kwargs):
            if args and args[0]=='rb':opened.append(path.name)
            return original(path,*args,**kwargs)
        with patch.object(Path,'open',recording):report=replay_bundle(self.bundle,candidate())
        self.assertEqual(sorted(opened),['events.csv','events.jsonl','manifest.json'])
        (self.bundle/'events.jsonl').write_text('changed-after-snapshot')
        self.assertEqual(rows,[row()]);self.assertEqual(report['events'][0]['event'],row())
        with self.assertRaises(ValueError):read_bundle(self.bundle)

    def test_ac2402_four_categories_preserve_outcomes_precision_and_same_action_attempts(self):
        self.write(replay_rows());report=replay_bundle(self.bundle,candidate())
        self.assertEqual(report['counts'],dict(widened=1,narrowed=2,decision_changed=1,unchanged=2))
        self.assertEqual(report['recorded_outcomes'],dict(cancelled=1,completed=1,denied=3,error=1))
        self.assertEqual(len(report['events']),6);self.assertEqual(len({r['event']['action_id'] for r in report['events']}),1)
        self.assertEqual(report['events'][0]['event']['start_time_unix_nano'],1790000000000000001)
        self.assertEqual(report['events'][2]['event']['outcome'],'error');self.assertEqual(report['events'][2]['candidate_decision']['effect'],'deny')

    def test_ac2402_empty_bundle_and_revision_only_change_require_review(self):
        allowed=replay_rows()[1];self.write([allowed])
        self.assertEqual(replay_bundle(self.bundle,candidate())['status'],'unchanged_for_received_events')
        report=replay_bundle(self.bundle,candidate('new-revision'))
        self.assertEqual(report['counts']['unchanged'],1);self.assertEqual(report['revision_differences'],1);self.assertEqual(report['status'],'review_required')
        empty=self.folder/'empty';now=time.time_ns();write_bundle(empty,[],filters({},now),now)
        self.assertEqual(replay_bundle(empty,candidate())['status'],'review_required')

    def test_ac2402_missing_configuration_and_historical_evaluation_fault_remain_untrusted_records(self):
        rows=[row(i) for i in range(1,5)]
        rows[0].update(reason='policy_unavailable',policy_revision=None,rule_id=None)
        rows[1].update(reason='policy_error',rule_id=None)
        rows[2].update(reason='permission_missing',permission=None,rule_id=None)
        rows[3].update(reason='identity_missing',subject=None,rule_id=None)
        self.write(rows);report=replay_bundle(self.bundle,candidate())
        self.assertEqual(report['counts'],dict(widened=2,narrowed=0,decision_changed=0,unchanged=2))
        self.assertEqual(report['revision_differences'],1);self.assertIsNone(report['events'][0]['event']['policy_revision'])

    def test_ac2401_corruption_and_event_limits_fail_before_policy_evaluation(self):
        self.write(replay_rows())
        with patch.object(Policy,'evaluate',side_effect=AssertionError('must not evaluate')):
            for limit in (0,True,10001,5):
                with self.subTest(limit=limit),self.assertRaises(ValueError):replay_bundle(self.bundle,candidate(),max_events=limit)
            (self.bundle/'events.csv').write_text('synthetic-private-corruption')
            with self.assertRaises(ValueError):replay_bundle(self.bundle,candidate())

    def test_ac2401_actual_cli_exit_codes_output_protection_and_error_privacy(self):
        self.write([row()]);policy=self.folder/'policy.json';policy.write_text(json.dumps(dict(schema_version='aegis.policy.v1',revision='v1',rules=[dict(id='allow',effect='allow',subjects=['reader'],tools=['lookup'],permissions=['orders.read'])])))
        output=self.folder/'report.json'
        def cli(code,report):
            result=subprocess.run([sys.executable,'scripts/replay_security.py',str(self.bundle),'--policy',str(policy),'--output',str(report)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=15)
            self.assertEqual(result.returncode,code,result.stdout+result.stderr);return result
        summary=json.loads(cli(1,output).stdout);self.assertEqual(summary['counts']['widened'],1)
        original=output.read_bytes();cli(2,output);self.assertEqual(output.read_bytes(),original)
        self.bundle=self.folder/'same';self.write([replay_rows()[1]])
        self.assertEqual(json.loads(cli(0,self.folder/'same-report.json').stdout)['status'],'unchanged_for_received_events')
        policy.write_text('private-invalid-policy')
        failure=self.folder/'failed.json';result=cli(2,failure)
        self.assertEqual(result.stdout,'');self.assertNotIn('private-invalid',result.stderr);self.assertFalse(failure.exists())

    def test_ac2402_zero_only_describes_received_events_not_unseen_configuration(self):
        self.write([replay_rows()[1]])
        policy=Policy('v1',candidate().rules+(Rule('unseen','allow',('new-agent',),('new-tool',),('new.permission',)),))
        report=replay_bundle(self.bundle,policy)
        self.assertEqual(report['status'],'unchanged_for_received_events')
        self.assertIn('received telemetry',report['notice']);self.assertIn('approval',report['notice'])

    def test_ac2402_replay_leaves_source_bytes_unchanged_and_uses_independent_snapshots(self):
        self.write(replay_rows());before={path.name:path.read_bytes() for path in self.bundle.iterdir()}
        report=replay_bundle(self.bundle,candidate());report['events'][0]['event']['subject']='changed-output'
        self.assertEqual(before,{path.name:path.read_bytes() for path in self.bundle.iterdir()})
        self.assertEqual(replay_bundle(self.bundle,candidate())['events'][0]['event']['subject'],'reader')
