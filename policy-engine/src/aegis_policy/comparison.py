"""Bounded offline policy-change reports; never installs a candidate policy."""
from . import Policy, effect_rank
from .workbench import _validate_cases, check_cases, require

NOTICE = 'Case-based offline comparison, not global equivalence, production completeness or approval to deploy. Fingerprints do not authenticate policies or replace approval bindings.'


def _rules(policy):
    return {rule.id:(rule.effect,tuple(sorted(rule.subjects)),tuple(sorted(rule.tools)),tuple(sorted(rule.permissions)))
            for rule in policy.rules}


def _category(before, after):
    if before['effect']!=after['effect']:
        return 'widened' if effect_rank(after['effect'])>effect_rank(before['effect']) else 'narrowed'
    return 'decision_changed' if any(before[key]!=after[key] for key in ('reason','rule_id')) else 'unchanged'


def compare_policies(before, after, document):
    require(type(before) is Policy and type(after) is Policy and document is not None)
    snapshot=_validate_cases(document)
    baseline=check_cases(before,snapshot);candidate=check_cases(after,snapshot)
    old=_rules(before);new=_rules(after)
    shared=old.keys() & new.keys()
    rules=dict(added=sorted(new.keys()-old.keys()),removed=sorted(old.keys()-new.keys()),
        modified=sorted(key for key in shared if old[key]!=new[key]),
        unchanged=sorted(key for key in shared if old[key]==new[key]))
    names=('effect','subjects','tools','permissions')
    rules['modified_details']=[dict(id=key,fields=[name for index,name in enumerate(names) if old[key][index]!=new[key][index]]) for key in rules['modified']]
    counts={name:0 for name in ('widened','narrowed','decision_changed','unchanged')}
    cases=[]
    for left,right in zip(baseline['cases'],candidate['cases']):
        category=_category(left['decision'],right['decision']);counts[category]+=1
        cases.append(dict(id=left['id'],category=category,expected=left['expected'],baseline_matches_expected=left['passed'],
            before=dict(decision=left['decision'],matched_rules=left['matched_rules']),
            after=dict(decision=right['decision'],matched_rules=right['matched_rules'])))
    changed=baseline['policy_fingerprint']!=candidate['policy_fingerprint']
    return dict(schema_version='aegis.policy-comparison.v2' if any(p.schema_version=='aegis.policy.v2' for p in (before,after)) or document.get('schema_version')=='aegis.policy-cases.v2' else 'aegis.policy-comparison.v1',
        status='review_required' if changed or baseline['cases_failed'] else 'unchanged',
        before=dict(revision=before.revision,fingerprint=baseline['policy_fingerprint'],rule_count=len(before.rules),coverage=baseline['coverage']),
        after=dict(revision=after.revision,fingerprint=candidate['policy_fingerprint'],rule_count=len(after.rules),coverage=candidate['coverage']),
        configuration_changed=changed,revision_changed=before.revision!=after.revision,
        rule_changes=rules,cases_total=len(cases),baseline_mismatches=baseline['cases_failed'],
        counts=counts,cases=cases,notice=NOTICE)
