"""Compare an existing business call with configured Aegis control."""
import argparse
import asyncio
import json
from pathlib import Path
from application import make_tool,build_graph,business_view
from aegis_runtime import ActionDenied
from aegis_runtime.application import Application,load_application


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default=str(Path(__file__).with_name('application.json')))
    parser.add_argument('--subject',default='reader');parser.add_argument('--framework',choices=('native','langgraph'),default='native')
    parser.add_argument('--async',dest='asynchronous',action='store_true');args=parser.parse_args(argv)
    try:
        config=load_application(args.config);counter={'calls':0};raw=make_tool(counter,args.asynchronous)
        if args.framework=='native':baseline=asyncio.run(raw('demo')) if args.asynchronous else raw('demo')
        else:
            graph=build_graph(raw);baseline=business_view(asyncio.run(graph.ainvoke({'messages':[]})) if args.asynchronous else graph.invoke({'messages':[]}))
        baseline_calls=counter['calls'];counter['calls']=0
        with Application(config,subject=args.subject) as app:
            tool=app.tool(raw)
            if args.framework=='native':
                if args.asynchronous:
                    async def invoke():
                        try:return await tool('demo')
                        except ActionDenied:return 'blocked'
                else:
                    def invoke():
                        try:return tool('demo')
                        except ActionDenied:return 'blocked'
                agent=app.agent(invoke,name='configured-native')
                result=asyncio.run(agent()) if args.asynchronous else agent()
            else:
                graph=build_graph(tool)
                agent=app.agent(graph.ainvoke if args.asynchronous else graph.invoke,name='configured-langgraph')
                result=business_view(asyncio.run(agent({'messages':[]})) if args.asynchronous else agent({'messages':[]}))
        status=app.status();allowed=config.policy.evaluate(subject=args.subject,tool='lookup_order',permission='orders.read').effect=='allow'
        valid=baseline_calls==1 and counter['calls']==int(allowed) and (result==baseline)==allowed and status['flush'] and status['shutdown'] and status['diagnostics']['exported_spans']==2
        print(json.dumps(dict(status='passed' if valid else 'failed',framework=args.framework,asynchronous=args.asynchronous,
            baseline_calls=baseline_calls,business_calls=counter['calls'],equivalent_to_baseline=result==baseline,application=status)))
        return 0 if valid else 1
    except Exception:
        print(json.dumps(dict(status='failed',error='Configured Agent validation failed; inspect configuration and dependencies')))
        return 1


if __name__=='__main__':raise SystemExit(main())
