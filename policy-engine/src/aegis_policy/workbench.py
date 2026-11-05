"""Offline development reports for the existing exact-match policy format."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from . import Policy, Decision, identifier, effect_rank

MAX_BYTES = 1024*1024
NOTICE = 'Offline policy evaluation only; case coverage is limited to supplied cases. Fingerprints do not authenticate policies or replace approval bindings.'


def require(condition):
    if not condition: raise ValueError('invalid policy workbench input')


def _unique(pairs):
    result={}
    for key,value in pairs:
        require(key not in result);result[key]=value
    return result


def _load(path):
    try:
        with Path(path).open('rb') as stream:raw=stream.read(MAX_BYTES+1)
        require(len(raw)<=MAX_BYTES)
        return json.loads(raw.decode('utf-8'),object_pairs_hook=_unique,
                          parse_constant=lambda value:require(False))
    except (OSError,ValueError,TypeError,RecursionError):
        raise ValueError('invalid or unreadable policy workbench file') from None


def load_policy(path):
    try:return Policy.from_dict(_load(path))
    except (ValueError,TypeError):raise ValueError('invalid or unreadable policy file') from None


def load_cases(path):
    return _validate_cases(_load(path))


def _validate_cases(document):
    require(type(document) is dict and set(document)=={'schema_version','cases'} and document['schema_version'] in ('aegis.policy-cases.v1','aegis.policy-cases.v2'))
    cases=document['cases'];require(type(cases) is list and 1<=len(cases)<=128)
    ids=set();snapshot=[]
    for case in cases:
        require(type(case) is dict and set(case)=={'id','subject','tool','permission','expected'})
        identifier(case['id']);require(case['id'] not in ids);ids.add(case['id'])
        identifier(case['tool'])
        for key in ('subject','permission'):
            if case[key] is not None:identifier(case[key])
        expected=case['expected']
        require(type(expected) is dict and set(expected)=={'effect','reason','rule_id'})
        require(expected['reason'] in ('explicit_allow','explicit_deny','no_match','identity_missing','permission_missing','explicit_require_approval'))
        require(document['schema_version']=='aegis.policy-cases.v2' or expected['effect']!='require_approval')
        Decision(expected['effect'],expected['reason'],'case-validation',expected['rule_id'])
        snapshot.append({**case,'expected':dict(expected)})
    return {'schema_version':document['schema_version'],'cases':snapshot}


def fingerprint(policy):
    require(type(policy) is Policy)
    document={'schema_version':policy.schema_version,'revision':policy.revision,'rules':[
        dict(id=rule.id,effect=rule.effect,subjects=sorted(rule.subjects),tools=sorted(rule.tools),permissions=sorted(rule.permissions))
        for rule in sorted(policy.rules,key=lambda rule:rule.id)]}
    canonical=json.dumps(document,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('utf-8')
    return hashlib.sha256(canonical).hexdigest()


def explain(policy, *, subject, tool, permission):
    require(type(policy) is Policy);identifier(tool)
    for value in (subject,permission):
        if value is not None:identifier(value)
    decision=policy.evaluate(subject=subject,tool=tool,permission=permission)
    matched=sorted((rule for rule in policy.rules if subject is not None and permission is not None and rule.matches(subject,tool,permission)),
                   key=lambda rule:(effect_rank(rule.effect),rule.id))
    return dict(decision=asdict(decision),matched_rules=[dict(id=rule.id,effect=rule.effect,selected=rule.id==decision.rule_id) for rule in matched])


def check_cases(policy, document=None):
    require(type(policy) is Policy)
    cases=[] if document is None else _validate_cases(document)['cases']
    reports=[];selected=set();matched=set()
    for case in cases:
        explanation=explain(policy,subject=case['subject'],tool=case['tool'],permission=case['permission'])
        actual={key:explanation['decision'][key] for key in ('effect','reason','rule_id')}
        if actual['rule_id'] is not None:selected.add(actual['rule_id'])
        matched.update(rule['id'] for rule in explanation['matched_rules'])
        reports.append(dict(id=case['id'],passed=actual==case['expected'],expected=case['expected'],**explanation))
    passed=sum(case['passed'] for case in reports)
    return dict(schema_version='aegis.policy-report.v2' if policy.schema_version=='aegis.policy.v2' or document is not None and document.get('schema_version')=='aegis.policy-cases.v2' else 'aegis.policy-report.v1',status='passed' if passed==len(reports) else 'failed',
        policy_revision=policy.revision,policy_fingerprint=fingerprint(policy),rule_count=len(policy.rules),
        cases_total=len(reports),cases_passed=passed,cases_failed=len(reports)-passed,cases=reports,
        coverage=dict(matched_rule_ids=sorted(matched),selected_rule_ids=sorted(selected),
            not_selected_by_cases=sorted({rule.id for rule in policy.rules}-selected)),notice=NOTICE)


def write_report(path, report):
    raw=(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')
    require(len(raw)<=8*MAX_BYTES)
    path=Path(path)
    stream=path.open('xb')
    try:
        with stream:stream.write(raw)
    except BaseException:
        path.unlink();raise
