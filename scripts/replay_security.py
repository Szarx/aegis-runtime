"""Recompute policy decisions for verified exported events; never run tools."""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.security_export import integer,read_bundle
from aegis_policy import Policy, effect_rank
from aegis_policy.workbench import fingerprint,load_policy,write_report

NOTICE = 'Counterfactual policy decisions for received telemetry only. No tools are executed; observed identity/revision and source hashes are not authentication, completeness, deployment approval or valid approval bindings.'


def replay_bundle(bundle, policy, *, max_events=1000):
    if type(policy) is not Policy or not integer(max_events,1,10000):
        raise ValueError('invalid replay configuration')
    manifest,rows=read_bundle(bundle)
    if len(rows)>max_events:raise ValueError('replay event limit exceeded')
    counts={name:0 for name in ('widened','narrowed','decision_changed','unchanged')}
    results=[];revision_differences=0
    for row in rows:
        decision=asdict(policy.evaluate(subject=row['subject'],tool=row['tool'],permission=row['permission']))
        if row['effect']!=decision['effect']:category='widened' if effect_rank(decision['effect'])>effect_rank(row['effect']) else 'narrowed'
        elif any(row[key]!=decision[key] for key in ('reason','rule_id')):category='decision_changed'
        else:category='unchanged'
        counts[category]+=1
        revision_matches=row['policy_revision']==policy.revision
        revision_differences+=int(not revision_matches)
        results.append(dict(event=row,candidate_decision=decision,category=category,revision_matches=revision_matches))
    canonical=json.dumps(manifest,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('utf-8')
    review=not rows or counts['unchanged']!=len(rows) or revision_differences>0
    return dict(schema_version='aegis.event-policy-replay.v2' if policy.schema_version=='aegis.policy.v2' or any(row['effect']=='require_approval' for row in rows) else 'aegis.event-policy-replay.v1',
        status='review_required' if review else 'unchanged_for_received_events',
        source=dict(count=manifest['count'],filters=manifest['filters'],files=manifest['files'],
            manifest_canonical_sha256=hashlib.sha256(canonical).hexdigest()),
        candidate=dict(revision=policy.revision,fingerprint=fingerprint(policy)),
        events_total=len(rows),counts=counts,revision_differences=revision_differences,
        recorded_outcomes=dict(sorted(Counter(row['outcome'] for row in rows).items())),events=results,notice=NOTICE)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle');parser.add_argument('--policy',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--max-events',type=int,default=1000);args=parser.parse_args(argv)
    try:
        report=replay_bundle(args.bundle,load_policy(args.policy),max_events=args.max_events)
        write_report(args.output,report)
        print(json.dumps({key:report[key] for key in ('status','events_total','counts','revision_differences','recorded_outcomes')},sort_keys=True))
        return 0 if report['status']=='unchanged_for_received_events' else 1
    except Exception:
        print(json.dumps(dict(status='error',error='Replay failed; check verified bundle, policy, event limit and new output path')),file=sys.stderr)
        return 2


if __name__=='__main__':sys.exit(main())
