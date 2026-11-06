"""Run a pinned external ReAct template against explicit synthetic service seams."""
import argparse
import asyncio
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import difflib

STARTED = time.perf_counter()

os.environ.update(LANGSMITH_TRACING='false', LANGCHAIN_TRACING_V2='false')

import httpx2
from openai import AsyncOpenAI
from langchain_core.messages import AIMessage, HumanMessage, convert_to_openai_messages
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt
import aegis
from aegis.langgraph import observe_graph
from aegis.openai import wrap_openai
from aegis_policy import Policy, Rule
from aegis_runtime import Runtime, ActionDenied
from aegis_runtime.async_reviewed_execution import AsyncReviewedClient
from aegis_runtime.policy_tool import AsyncPolicyTool, PendingReview
from aegis_runtime.approvals import ApprovalUnavailable

HERE = Path(__file__).resolve().parent
counts = {'model_calls': 0, 'tool_calls': 0}
controlled = None
ticket = None
mode = 'baseline'
model_client = None


async def business_search(query: str) -> dict:
    """Search a synthetic local catalogue."""
    if query != 'synthetic-order':
        raise ValueError('Only the synthetic query is supported')
    counts['tool_calls'] += 1
    return {'status': 'shipped'}


async def search(query: str) -> dict:
    """Search the synthetic catalogue with the host's explicit control."""
    global ticket
    if mode == 'baseline':
        return await business_search(query)
    if mode in ('observe', 'allow', 'deny'):
        return await controlled(query=query)
    if ticket is None:
        pending = await controlled.invoke({'query': query}, summary='Synthetic external template search')
        if not isinstance(pending, PendingReview):
            raise RuntimeError('Expected a pending request')
        ticket = pending.record
    # interrupt is raised through ToolNode. The host resumes this node only after
    # an independent reviewer decision. A resume value never authorizes execution.
    interrupt({'kind': 'review_required', 'action_id': ticket['action_id']})
    result = await controlled.resume(ticket, {'query': query}, summary='Synthetic external template search')
    if result.confirmation != 'confirmed':
        raise ApprovalUnavailable()
    return result.value


class SyntheticModel:
    def bind_tools(self, tools):
        if len(tools) != 1 or tools[0].__name__ != 'search':
            raise ValueError('Unexpected upstream tools')
        return self

    async def ainvoke(self, messages):
        response = await model_client.chat.completions.create(
            model='synthetic-model', messages=convert_to_openai_messages(messages),
        )
        message = response.choices[0].message
        calls = [{'name': call.function.name, 'args': json.loads(call.function.arguments),
                  'id': call.id, 'type': 'tool_call'} for call in message.tool_calls or []]
        return AIMessage(content=message.content or '', tool_calls=calls)


def load_chat_model(name):
    if name != 'synthetic/model':
        raise ValueError('Only the synthetic model is supported')
    return SyntheticModel()


def provider(request):
    counts['model_calls'] += 1
    messages = json.loads(request.content)['messages']
    first = not any(message['role'] == 'tool' for message in messages)
    message = {'role': 'assistant', 'content': None if first else 'Synthetic search complete'}
    if first:
        message['tool_calls'] = [{'id': 'synthetic-call', 'type': 'function',
            'function': {'name': 'search', 'arguments': '{"query":"synthetic-order"}'}}]
    return httpx2.Response(200, json={
        'id': 'synthetic-response', 'object': 'chat.completion', 'created': 0,
        'model': 'synthetic-model', 'choices': [{'index': 0, 'message': message,
            'finish_reason': 'tool_calls' if first else 'stop'}],
        'usage': {'prompt_tokens': 7, 'completion_tokens': 3, 'total_tokens': 10},
    })


def prepare_project(folder):
    manifest = json.loads((HERE / 'upstream.json').read_text(encoding='utf-8-sig'))
    for row in manifest['files']:
        path = HERE / 'upstream' / row['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Upstream source hash mismatch')
    target = folder / 'project'
    shutil.copytree(HERE / 'upstream', target)
    package = target / 'src/react_agent'
    (package / 'tools.py').write_text('from external_host import search\nTOOLS = [search]\n', encoding='utf-8')
    (package / 'utils.py').write_text('from external_host import load_chat_model\n', encoding='utf-8')
    sys.path.insert(0, str(target / 'src'))
    sys.modules['external_host'] = sys.modules[__name__]
    return manifest


def source_diff(folder, manifest):
    changed = []
    added = removed = 0
    for row in manifest['files']:
        relative = row['path']
        original = (HERE / 'upstream' / relative).read_bytes()
        adapted = (folder / 'project' / relative).read_bytes()
        if original == adapted:
            continue
        changed.append(relative)
        for line in difflib.ndiff(original.decode().splitlines(), adapted.decode().splitlines()):
            added += line.startswith('+ ')
            removed += line.startswith('- ')
    if changed != ['src/react_agent/tools.py', 'src/react_agent/utils.py']:
        raise ValueError('Unexpected upstream source changes')
    return {'changed_files': changed, 'added_lines': added, 'removed_lines': removed}


async def execute(args, folder):
    global controlled, mode, model_client
    mode = args.mode
    manifest = prepare_project(folder)
    options = {'endpoint': args.endpoint + '/v1/traces',
               'headers': {'Authorization': 'Bearer ' + os.environ['AEGIS_API_TOKEN']}} if args.endpoint else {
                   'output_path': folder / 'traces.jsonl'}
    sdk = aegis.init('external-react-agent', **options) if mode != 'baseline' else None
    effect = 'require_approval' if mode == 'approval' else 'deny' if mode == 'deny' else 'allow'
    policy = Policy('external-v2', (Rule('search-rule', effect, ('external-agent',), ('search',), ('catalogue.read',)),), 'aegis.policy.v2')
    async with AsyncOpenAI(api_key='synthetic', max_retries=0,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(provider))) as raw:
        model_client = wrap_openai(raw) if sdk else raw
        async with AsyncReviewedClient(
            args.endpoint or 'http://127.0.0.1:8000',
            token=os.environ.get('AEGIS_APPROVAL_REQUEST_TOKEN', 'synthetic-producer'),
            execution_token=os.environ.get('AEGIS_APPROVAL_EXECUTION_TOKEN', 'synthetic-executor'),
            binding_key=bytes.fromhex(os.environ.get('AEGIS_APPROVAL_BINDING_KEY', '11' * 32)),
        ) as reviewer:
            if mode == 'observe':
                controlled = aegis.tool(business_search, permission='catalogue.read')
            elif mode in ('allow', 'deny'):
                controlled = Runtime(policy=policy, subject='external-agent').tool(business_search, name='search', permission='catalogue.read')
            elif mode == 'approval':
                controlled = AsyncPolicyTool(business_search, client=reviewer, policy=policy, subject='external-agent',
                    tool='search', permission='catalogue.read', tool_revision='synthetic-search-v1', disclose_arguments=True)
            module = importlib.import_module('react_agent.graph')
            from react_agent.context import Context
            graph = module.builder.compile(checkpointer=InMemorySaver())
            graph = observe_graph(graph, name='external-react-agent') if sdk else graph
            config = {'configurable': {'thread_id': 'synthetic-external'}, 'recursion_limit': 12}
            context = Context(model='synthetic/model', system_prompt='Synthetic catalogue assistant.')
            try:
                result = await graph.ainvoke({'messages': [HumanMessage(content='Search synthetic-order')]}, config, context=context)
                if mode == 'approval':
                    if not result.get('__interrupt__') or counts['tool_calls']:
                        raise ValueError('Expected a safe tool interrupt')
                    (folder / 'pending.json').write_text(json.dumps({'action_id': ticket['action_id']}), encoding='utf-8')
                    print(json.dumps({'status': 'pending', 'action_id': ticket['action_id']}), flush=True)
                    # The go file is a local host trigger. It carries no approval.
                    deadline = time.monotonic() + args.wait_seconds
                    while not (folder / 'resume').exists():
                        if time.monotonic() >= deadline:
                            raise TimeoutError('Host resume trigger timed out')
                        await asyncio.sleep(.1)
                    result = await graph.ainvoke(Command(resume=True), config, context=context)
                    try:
                        await controlled.resume(ticket, {'query': 'synthetic-order'}, summary='Synthetic external template search')
                    except ApprovalUnavailable:
                        pass
                    else:
                        raise ValueError('Consumed approval executed twice')
                status = 'completed'
            except ActionDenied:
                result = {'messages': []}
                status = 'denied'
            except ApprovalUnavailable:
                result = {'messages': []}
                status = 'approval_unavailable'
            finally:
                if sdk:
                    if not sdk.flush() or not sdk.shutdown():
                        raise RuntimeError('Telemetry delivery failed')
    # Compare stable business content. Framework-generated IDs are excluded.
    messages = [(m.type, m.content, getattr(m, 'tool_calls', [])) for m in result['messages']]
    return {'schema_version': 'aegis.external-agent.v1', 'status': status, 'mode': mode,
        'upstream_revision': manifest['revision'], 'counts': counts,
        'business_sha256': hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest(),
        'service_boundary_files': ['src/react_agent/tools.py', 'src/react_agent/utils.py'],
        'source_diff': source_diff(folder, manifest),
        'upstream_graph_unchanged': True, 'real_provider_requests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['baseline','observe','allow','deny','approval'], default='observe')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--endpoint')
    parser.add_argument('--wait-seconds', type=int, default=45)
    args = parser.parse_args()
    if args.mode == 'approval' and (not args.endpoint or not all(os.environ.get(name) for name in (
        'AEGIS_API_TOKEN','AEGIS_APPROVAL_REQUEST_TOKEN','AEGIS_APPROVAL_EXECUTION_TOKEN','AEGIS_APPROVAL_BINDING_KEY'))):
        parser.error('Approval requires Collector and explicit host credentials')
    if not 1 <= args.wait_seconds <= 300:
        parser.error('wait-seconds must be 1..300')
    args.output.mkdir(parents=True, exist_ok=False)
    report = asyncio.run(execute(args, args.output))
    report['automated_elapsed_ms'] = round((time.perf_counter() - STARTED) * 1000, 3)
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))
    return int(report['status'] == 'approval_unavailable')


if __name__ == '__main__':
    raise SystemExit(main())
