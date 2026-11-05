import hashlib
import json
import unittest
from aegis_policy import Policy, Rule
from aegis_policy.workbench import check_cases, explain, fingerprint
from aegis_policy.comparison import compare_policies


def policy(effect='require_approval', revision='policy-v2'):
    return Policy(revision,(Rule('rule',effect,('agent',),('write',),('records.write',)),),'aegis.policy.v2')


class ApprovalPolicy(unittest.TestCase):
    def test_versioned_effect_and_all_priority_combinations(self):
        for effects in [('allow','require_approval'),('require_approval','deny'),('deny','allow'),('allow','require_approval','deny')]:
            rules=tuple(Rule(str(i),value,('agent',),('write',),('records.write',)) for i,value in enumerate(effects))
            configured=Policy('v2',rules,'aegis.policy.v2')
            expected='deny' if 'deny' in effects else 'require_approval'
            self.assertEqual(configured.evaluate(subject='agent',tool='write',permission='records.write').effect,expected)
            self.assertEqual(explain(configured,subject='agent',tool='write',permission='records.write')['matched_rules'][0]['effect'],expected)
        with self.assertRaises(ValueError):Policy('v1',policy().rules)
        raw=dict(schema_version='aegis.policy.v2',revision='policy-v2',rules=[dict(id='rule',effect='require_approval',subjects=['agent'],tools=['write'],permissions=['records.write'])])
        self.assertEqual(Policy.from_dict(raw),policy())
        with self.assertRaises(ValueError):Policy.from_dict({**raw,'schema_version':'aegis.policy.v1'})

    def test_legacy_digest_and_normalized_fingerprint_bytes_remain_exact(self):
        old=Policy('old',(Rule('permit','allow',('agent',),('write',),('records.write',)),))
        raw=dict(schema_version='aegis.policy.v1',revision='old',rules=[dict(id='permit',effect='allow',subjects=['agent'],tools=['write'],permissions=['records.write'])])
        def sha(ascii):return hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':'),ensure_ascii=ascii).encode()).hexdigest()
        self.assertEqual(fingerprint(old),sha(True))
        self.assertNotEqual(fingerprint(policy('allow')),fingerprint(Policy('policy-v2',policy('allow').rules)))

    def test_v2_cases_third_decision_and_v1_rejection(self):
        cases=dict(schema_version='aegis.policy-cases.v2',cases=[dict(id='review',subject='agent',tool='write',permission='records.write',expected=dict(effect='require_approval',reason='explicit_require_approval',rule_id='rule'))])
        self.assertEqual(check_cases(policy(),cases)['cases_passed'],1)
        with self.assertRaises(ValueError):check_cases(policy(),{**cases,'schema_version':'aegis.policy-cases.v1'})
        cases['cases'][0]['expected']=dict(effect='deny',reason='explicit_deny',rule_id='rule')
        self.assertEqual(compare_policies(policy('deny'),policy(),cases)['counts']['widened'],1)
        self.assertEqual(compare_policies(policy('allow'),policy(),cases)['counts']['narrowed'],1)
        self.assertEqual(compare_policies(policy(),policy('deny'),cases)['counts']['narrowed'],1)

    def test_missing_identity_permission_and_no_match_still_deny(self):
        for subject,permission,reason in [(None,'records.write','identity_missing'),('agent',None,'permission_missing'),('other','records.write','no_match')]:
            decision=policy().evaluate(subject=subject,tool='write',permission=permission)
            self.assertEqual((decision.effect,decision.reason),('deny',reason))
