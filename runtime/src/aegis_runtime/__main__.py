"""Read-only configured-host inspection; no Agent or tracing startup."""
import argparse
import json
import sys
from aegis_policy.workbench import write_report
from .application import inspect_application,load_application


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    inspect=commands.add_parser('inspect');inspect.add_argument('config');inspect.add_argument('--subject',required=True);inspect.add_argument('--output')
    args=parser.parse_args(argv)
    try:
        report=inspect_application(load_application(args.config),subject=args.subject)
        if args.output:write_report(args.output,report)
        print(json.dumps(report,sort_keys=True));return 0 if report['status']=='valid' else 1
    except Exception:
        print(json.dumps(dict(status='error',error='Application inspection failed; check configuration and new report path')),file=sys.stderr)
        return 2


if __name__=='__main__':sys.exit(main())
