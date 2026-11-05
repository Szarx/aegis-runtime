"""Offline policy validation, explanations and declared-case acceptance."""
import argparse
import json
import sys
from .workbench import NOTICE,check_cases,explain,fingerprint,load_cases,load_policy,write_report
from .comparison import compare_policies


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    check=commands.add_parser('check');check.add_argument('policy');check.add_argument('--cases')
    explanation=commands.add_parser('explain');explanation.add_argument('policy')
    explanation.add_argument('--subject');explanation.add_argument('--tool',required=True);explanation.add_argument('--permission')
    comparison=commands.add_parser('compare');comparison.add_argument('policy');comparison.add_argument('candidate');comparison.add_argument('--cases',required=True)
    for command in (check,explanation,comparison):command.add_argument('--output')
    args=parser.parse_args(argv)
    try:
        policy=load_policy(args.policy)
        if args.command=='compare':
            report=compare_policies(policy,load_policy(args.candidate),load_cases(args.cases))
            code=0 if report['status']=='unchanged' else 1
        elif args.command=='check':
            report=check_cases(policy,load_cases(args.cases) if args.cases else None)
            code=0 if report['status']=='passed' else 1
        else:
            report=dict(schema_version='aegis.policy-explanation.v2' if policy.schema_version=='aegis.policy.v2' else 'aegis.policy-explanation.v1',policy_revision=policy.revision,
                policy_fingerprint=fingerprint(policy),notice=NOTICE,
                **explain(policy,subject=args.subject,tool=args.tool,permission=args.permission))
            code=0
        if args.output:write_report(args.output,report)
        print(json.dumps(report,ensure_ascii=False,sort_keys=True))
        return code
    except Exception:
        print(json.dumps(dict(status='error',error='Invalid or unreadable policy/cases, or report output unavailable; existing output is never overwritten')),file=sys.stderr)
        return 2


if __name__=='__main__':sys.exit(main())
