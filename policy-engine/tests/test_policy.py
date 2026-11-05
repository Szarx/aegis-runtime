import copy
from dataclasses import FrozenInstanceError
import json
import unittest

from aegis_policy import Policy, Rule, Decision


def document():
    return {'schema_version':'aegis.policy.v1','revision':'demo-v1','rules':[
        {'id':'allow-read','effect':'allow','subjects':['reader'],'tools':['lookup'],'permissions':['orders.read']}]}


class PolicyAcceptance(unittest.TestCase):
    def test_exact_three_part_matching_and_empty_default_deny(self):
        policy=Policy.from_json(json.dumps(document()))
        self.assertEqual(policy.evaluate(subject='reader',tool='lookup',permission='orders.read').effect,'allow')
        for subject,tool,permission in [('other','lookup','orders.read'),('reader','different','orders.read'),('reader','lookup','orders.write')]:
            result=policy.evaluate(subject=subject,tool=tool,permission=permission)
            self.assertEqual((result.effect,result.reason),('deny','no_match'))
        self.assertEqual(Policy('empty',()).evaluate(subject='reader',tool='lookup',permission='orders.read').effect,'deny')

    def test_deny_and_rule_id_precedence_independent_of_order(self):
        value=document()
        for name in ('z-deny','a-deny'):
            rule=copy.deepcopy(value['rules'][0]);rule.update(id=name,effect='deny');value['rules'].append(rule)
        for rules in (value['rules'],list(reversed(value['rules']))):
            policy=Policy.from_dict({**value,'rules':rules})
            result=policy.evaluate(subject='reader',tool='lookup',permission='orders.read')
            self.assertEqual((result.effect,result.rule_id),('deny','a-deny'))

    def test_copied_immutable_snapshot_and_direct_construction(self):
        value=document();policy=Policy.from_dict(value)
        value['rules'][0]['subjects'].append('attacker')
        value['revision']='changed'
        self.assertEqual(policy.revision,'demo-v1')
        self.assertEqual(policy.evaluate(subject='attacker',tool='lookup',permission='orders.read').effect,'deny')
        with self.assertRaises(FrozenInstanceError): policy.revision='changed'
        with self.assertRaises(ValueError): Policy('rev',list(policy.rules))
        with self.assertRaises(ValueError): Rule('id','allow',['reader'],('lookup',),('orders.read',))

    def test_unknown_keys_types_wildcards_duplicates_and_limits_rejected(self):
        cases=[]
        for update in ({'unknown':True},{'schema_version':'future'},{'revision':'*'},{'rules':None}):
            cases.append({**document(),**update})
        for field,bad in [('effect','require_approval'),('subjects',[]),('tools',['*']),('permissions',['orders.read','orders.read']),('id','bad\x00'),('tools',['lookup']*129),('unknown',True)]:
            value=document();value['rules'][0][field]=bad;cases.append(value)
        value=document();value['rules']*=2;cases.append(value)
        value=document();value['rules']*=129;cases.append(value)
        for value in cases:
            with self.assertRaises(ValueError): Policy.from_dict(value)
        for content in ('private invalid json','{"schema_version":1,"schema_version":2}'):
            with self.assertRaisesRegex(ValueError,'^invalid policy document$'): Policy.from_json(content)

    def test_missing_identity_permission_and_invalid_decision(self):
        policy=Policy.from_dict(document())
        self.assertEqual(policy.evaluate(subject=None,tool='lookup',permission=None).reason,'identity_missing')
        self.assertEqual(policy.evaluate(subject='reader',tool='lookup',permission=None).reason,'permission_missing')
        for args in [('allow','no_match'),('deny','explicit_allow'),('allow','explicit_allow',None,'rule'),('allow',[])]:
            with self.assertRaises(ValueError): Decision(*args)


if __name__=='__main__': unittest.main()
