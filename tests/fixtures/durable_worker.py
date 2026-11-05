"""Subprocess-only crash injection; production example has no crash flags."""

import argparse
import importlib.util
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('aegis_durable_example',ROOT/'examples/durable-graph/agent.py')
example=importlib.util.module_from_spec(spec);sys.modules[spec.name]=example;spec.loader.exec_module(example)
parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('pause','claim','write','complete','graph'),required=True)
args,remaining=parser.parse_known_args();sys.argv=[sys.argv[0],*remaining]
native_client=example.ReviewedClient
def configured_client(*positional,**kwargs):
    client=native_client(*positional,**kwargs)
    if args.phase in ('claim','complete'):
        name=args.phase;native=getattr(client,name)
        def committed(*positional,**kwargs):
            native(*positional,**kwargs)
            os._exit(71 if name=='claim' else 73)
        setattr(client,name,committed)
    return client
example.ReviewedClient=configured_client
native_gate=example.make_gate
def configured_gate(*positional,**kwargs):
    gate=native_gate(*positional,**kwargs)
    if args.phase=='write':
        native=gate._function
        def written(*positional,**kwargs):
            native(*positional,**kwargs);os._exit(72)
        gate._function=written
    elif args.phase=='graph':
        native=gate.resume
        def continued(*positional,**kwargs):
            native(*positional,**kwargs);os._exit(74)
        gate.resume=continued
    return gate
example.make_gate=configured_gate
if args.phase=='pause':
    native_save=example.save_ticket
    def saved(*positional,**kwargs):
        native_save(*positional,**kwargs);os._exit(70)
    example.save_ticket=saved
raise SystemExit(example.main())
