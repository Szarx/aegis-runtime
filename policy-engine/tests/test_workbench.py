import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from aegis_policy import Policy,Rule
from aegis_policy.workbench import MAX_BYTES,check_cases,explain,fingerprint,load_cases,load_policy,write_report

ROOT=Path(__file__).resolve().parents[2]
EXAMPLE=ROOT/'examples/policy-workbench'


class PolicyWorkbench(unittest.TestCase):
    def setUp(self):
        self.policy=load_policy(EXAMPLE/'policy.json');self.suite=load_cases(EXAMPLE/'cases.json')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.folder=Path(self.tmp.name)

    def test_ac2202_explanation_matches_existing_evaluator_and_deny_precedence(self):
        for case in self.suite['cases']:
            explanation=explain(self.policy,**{k:case[k] for k in ('subject','tool','permission')})
            self.assertEqual(explanation['decision']['reason'],case['expected']['reason'])
        result=explain(self.policy,subject='blocked',tool='lookup',permission='orders.read')
        self.assertEqual([(r['id'],r['selected']) for r in result['matched_rules']],[('deny-blocked',True),('allow-read',False)])
        reordered=Policy(self.policy.revision,tuple(reversed(self.policy.rules)))
        self.assertEqual(explain(reordered,subject='blocked',tool='lookup',permission='orders.read'),result)
        missing=explain(self.policy,subject=None,tool='lookup',permission='orders.read')
        self.assertEqual(missing['matched_rules'],[])

    def test_ac2201_fingerprint_ignores_format_and_order_but_tracks_revision_and_members(self):
        document=json.loads((EXAMPLE/'policy.json').read_text());original=fingerprint(self.policy)
        document['rules'].reverse();document['rules'][-1]['subjects'].reverse()
        self.assertEqual(fingerprint(Policy.from_dict(document)),original)
        document['revision']='new-v2';self.assertNotEqual(fingerprint(Policy.from_dict(document)),original)
        document['revision']=self.policy.revision;document['rules'][-1]['subjects'].append('new-subject')
        self.assertNotEqual(fingerprint(Policy.from_dict(document)),original)
        self.assertEqual(len(original),64)

    def test_ac2202_cases_report_mismatch_and_limited_rule_coverage(self):
        report=check_cases(self.policy,self.suite)
        self.assertEqual((report['status'],report['cases_passed'],report['cases_failed']),('passed',7,0))
        self.assertEqual(report['coverage']['not_selected_by_cases'],['allow-admin'])
        self.suite['cases'][0]['expected']=dict(effect='deny',reason='no_match',rule_id=None)
        mismatch=check_cases(self.policy,self.suite)
        self.assertEqual((mismatch['status'],mismatch['cases_failed']),('failed',1))
        self.assertEqual(mismatch['cases'][0]['decision']['effect'],'allow')
        self.assertEqual(report['cases'][0]['expected']['effect'],'allow')
        empty=check_cases(Policy('empty',()))
        self.assertEqual((empty['status'],empty['cases_total']),('passed',0))

    def test_ac2201_rejects_duplicate_keys_invalid_utf8_unknown_version_and_content(self):
        destination=self.folder/'private.json'
        for raw in (b'private-invalid-body',b'\xff',b'{"schema_version":1,"schema_version":2}',b'{"schema_version":"future","revision":"x","rules":[]}'):
            destination.write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'^invalid or unreadable policy file$'):load_policy(destination)
        destination.write_bytes(b'x'*(MAX_BYTES+1))
        with self.assertRaises(ValueError):load_policy(destination)

    def test_ac2201_strict_suite_fields_types_expected_pairing_ids_and_bounds(self):
        for mutate in (lambda d:d.update(extra=True),lambda d:d.update(schema_version='future'),lambda d:d.update(cases=[]),
            lambda d:d.update(cases=d['cases']*129),lambda d:d['cases'].append(d['cases'][0]),
            lambda d:d['cases'][0].update(subject='*'),lambda d:d['cases'][0].update(tool=None),
            lambda d:d['cases'][0]['expected'].update(effect='require_approval'),
            lambda d:d['cases'][0]['expected'].update(rule_id=None),
            lambda d:d['cases'][0].update(arguments={'private':'body'})):
            document=copy.deepcopy(self.suite);mutate(document)
            with self.subTest(document=document),self.assertRaises(ValueError):check_cases(self.policy,document)
        path=self.folder/'cases.json';path.write_text('{"schema_version":1,"schema_version":2}')
        with self.assertRaises(ValueError):load_cases(path)

    def test_ac2202_report_output_exclusive_and_close_failure_removes_partial_file(self):
        report=check_cases(self.policy,self.suite);path=self.folder/'report.json'
        write_report(path,report);original=path.read_bytes()
        with self.assertRaises(FileExistsError):write_report(path,{})
        self.assertEqual(path.read_bytes(),original);path.unlink()
        original_open=Path.open
        class CloseFailure:
            def __init__(self,stream):self.stream=stream
            def __enter__(self):return self.stream
            def __exit__(self,*args):self.stream.close();raise OSError('synthetic private close error')
        with patch.object(Path,'open',lambda p,*args,**kwargs:CloseFailure(original_open(p,*args,**kwargs))):
            with self.assertRaises(OSError):write_report(path,report)
        self.assertFalse(path.exists())

    def test_ac2202_same_effect_rule_id_order_and_no_mutation(self):
        policy=Policy('rev',(Rule('z','allow',('s',),('t',),('p',)),Rule('a','allow',('s',),('t',),('p',))))
        result=explain(policy,subject='s',tool='t',permission='p')
        self.assertEqual(result['decision']['rule_id'],'a')
        self.assertEqual([r['id'] for r in result['matched_rules']],['a','z'])
        result['matched_rules'].clear();self.assertEqual(len(policy.rules),2)
