import copy
from dataclasses import replace
from pathlib import Path
import unittest
from aegis_policy import Policy,Rule
from aegis_policy.comparison import compare_policies
from aegis_policy.workbench import load_cases,load_policy

EXAMPLE=Path(__file__).resolve().parents[2]/'examples/policy-comparison'


class PolicyComparison(unittest.TestCase):
    def setUp(self):
        self.before=load_policy(EXAMPLE/'before.json');self.after=load_policy(EXAMPLE/'candidate.json');self.cases=load_cases(EXAMPLE/'cases.json')

    def test_ac2301_structure_and_all_four_decision_categories(self):
        report=compare_policies(self.before,self.after,self.cases)
        self.assertEqual(report['counts'],dict(widened=2,narrowed=1,decision_changed=1,unchanged=4))
        self.assertEqual(report['baseline_mismatches'],0);self.assertEqual(report['status'],'review_required')
        self.assertEqual(report['rule_changes']['added'],['allow-future','deny-write'])
        self.assertEqual(report['rule_changes']['removed'],['deny-blocked'])
        self.assertEqual(report['rule_changes']['modified_details'],[dict(id='allow-admin',fields=['effect']),dict(id='allow-read',fields=['subjects'])])
        self.assertEqual(report['after']['coverage']['not_selected_by_cases'],['allow-future'])

    def test_ac2301_identical_members_reordered_rules_do_not_require_review(self):
        reordered=Policy(self.before.revision,tuple(replace(rule,subjects=tuple(reversed(rule.subjects))) for rule in reversed(self.before.rules)))
        report=compare_policies(self.before,reordered,self.cases)
        self.assertEqual(report['status'],'unchanged');self.assertFalse(report['configuration_changed'])
        self.assertEqual(report['counts']['unchanged'],8);self.assertEqual(report['rule_changes']['modified'],[])

    def test_ac2301_same_revision_content_change_and_revision_only_both_require_review(self):
        same_revision=replace(self.after,revision=self.before.revision)
        report=compare_policies(self.before,same_revision,self.cases)
        self.assertFalse(report['revision_changed']);self.assertTrue(report['configuration_changed']);self.assertEqual(report['status'],'review_required')
        version=compare_policies(self.before,replace(self.before,revision='new-version'),self.cases)
        self.assertTrue(version['revision_changed']);self.assertEqual(version['counts']['unchanged'],8)
        self.assertEqual(version['rule_changes']['modified'],[]);self.assertEqual(version['status'],'review_required')

    def test_ac2301_unexercised_new_rule_is_not_silently_accepted(self):
        new=Policy(self.before.revision,self.before.rules+(Rule('new-uncovered','allow',('new-agent',),('new-tool',),('new.permission',)),))
        report=compare_policies(self.before,new,self.cases)
        self.assertEqual(report['counts']['unchanged'],8);self.assertEqual(report['status'],'review_required')
        self.assertIn('new-uncovered',report['after']['coverage']['not_selected_by_cases'])

    def test_ac2302_reason_and_rule_changes_under_same_effect_are_distinct(self):
        report=compare_policies(self.before,self.after,self.cases)
        row=next(case for case in report['cases'] if case['id']=='write-not-allowed')
        self.assertEqual(row['category'],'decision_changed')
        self.assertEqual((row['before']['decision']['reason'],row['after']['decision']['reason']),('no_match','explicit_deny'))
        renamed=Policy(self.before.revision,tuple(replace(rule,id='renamed-read') if rule.id=='allow-read' else rule for rule in self.before.rules))
        row=compare_policies(self.before,renamed,self.cases)['cases'][0]
        self.assertEqual(row['category'],'decision_changed');self.assertEqual(row['after']['decision']['effect'],'allow')

    def test_ac2301_invalid_baseline_expected_never_returns_unchanged(self):
        self.cases['cases'][0]['expected']=dict(effect='deny',reason='no_match',rule_id=None)
        report=compare_policies(self.before,self.before,self.cases)
        self.assertEqual(report['baseline_mismatches'],1);self.assertEqual(report['status'],'review_required')
        self.assertEqual(report['counts']['unchanged'],8);self.assertFalse(report['cases'][0]['baseline_matches_expected'])
        for value in (None,{},dict(schema_version='future',cases=[])):
            with self.assertRaises(ValueError):compare_policies(self.before,self.after,value)

    def test_ac2302_comparison_does_not_mutate_or_retain_case_input(self):
        original=copy.deepcopy(self.cases);report=compare_policies(self.before,self.after,self.cases)
        self.assertEqual(self.cases,original)
        report['cases'][0]['expected']['effect']='deny';self.assertEqual(self.cases,original)
        missing=[case for case in report['cases'] if case['id'].startswith('missing-')]
        self.assertTrue(all(case['before']['matched_rules']==case['after']['matched_rules']==[] for case in missing))

    def test_ac2301_member_effect_changes_are_named_without_full_policy_disclosure(self):
        changed=replace(self.before.rules[0],subjects=('other',),tools=('other',),permissions=('other',),effect='deny')
        policy=Policy(self.before.revision,(changed,*self.before.rules[1:]))
        detail=compare_policies(self.before,policy,self.cases)['rule_changes']['modified_details']
        self.assertEqual(detail,[dict(id='allow-read',fields=['effect','subjects','tools','permissions'])])
