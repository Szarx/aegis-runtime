"""Offline by default; live requires local credentials and an explicit model."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

import aegis
from aegis import observe, tool
from aegis.openai import AegisAsyncOpenAI, AegisOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from examples.openai.offline import Fixture


@tool(permission="orders.read")
def lookup_order():
    return {"status": "shipped", "source": "synthetic"}


def call_options(api, model, stream):
    arguments = {"model": model, "stream": stream}
    if api == "responses":
        arguments["input"] = "Return a short greeting."
    else:
        arguments["messages"] = [{"role": "user", "content": "Return a short greeting."}]
        if stream:
            arguments["stream_options"] = {"include_usage": True}
    return arguments


@observe(name="openai-order-agent")
def run_agent(client, *, api="responses", model="offline-model", stream=False):
    create = client.responses.create if api == "responses" else client.chat.completions.create
    result = create(**call_options(api, model, stream))
    if stream:
        with result as events:
            for _ in events:
                pass
    return lookup_order()


@observe(name="openai-order-agent")
async def run_async_agent(client, *, api="responses", model="offline-model", stream=False):
    create = client.responses.create if api == "responses" else client.chat.completions.create
    result = await create(**call_options(api, model, stream))
    if stream:
        async with result as events:
            async for _ in events:
                pass
    return lookup_order()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("offline", "live"), default="offline")
    parser.add_argument("--api", choices=("responses", "chat"), default="responses")
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--async", dest="asynchronous", action="store_true")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path)
    destination.add_argument("--endpoint")
    args = parser.parse_args()
    model = "offline-model"
    client_options = {"max_retries": 0, "timeout": 30}
    if args.mode == "live":
        if not os.environ.get("OPENAI_API_KEY") or not os.environ.get("OPENAI_MODEL"):
            parser.error("live mode requires local OPENAI_API_KEY and OPENAI_MODEL")
        model = os.environ["OPENAI_MODEL"]
    else:
        client_options.update(api_key="offline-synthetic-key", base_url="https://offline.invalid/v1", http_client=Fixture(asynchronous=args.asynchronous).http_client())
    telemetry = {"output_path": args.output or Path("artifacts/openai/traces.jsonl")}
    if args.endpoint:
        telemetry = {"endpoint": args.endpoint}
        if os.environ.get("AEGIS_API_TOKEN"):
            telemetry["headers"] = {"Authorization": "Bearer " + os.environ["AEGIS_API_TOKEN"]}
    sdk = aegis.init("openai-example", **telemetry)
    api = "responses" if args.api == "responses" else "chat.completions"
    try:
        if args.asynchronous:
            async def execute():
                async with AegisAsyncOpenAI(**client_options) as client:
                    return await run_async_agent(client, api=api, model=model, stream=args.stream)
            result = asyncio.run(execute())
        else:
            with AegisOpenAI(**client_options) as client:
                result = run_agent(client, api=api, model=model, stream=args.stream)
        print(json.dumps({"mode": args.mode, "api": api, "stream": args.stream, "async": args.asynchronous, "result": result}))
    finally:
        flushed, closed = aegis.flush(), aegis.shutdown()
        print(json.dumps({"diagnostics": sdk.diagnostics(), "flush": flushed, "shutdown": closed}))
    return 0 if flushed and closed else 1


if __name__ == "__main__":
    raise SystemExit(main())
