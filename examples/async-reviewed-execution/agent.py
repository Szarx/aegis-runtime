"""Synthetic asyncio tool; only appends a local record, without an LLM."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from aegis_policy import Policy, Rule
from aegis_runtime import ActionDenied
from aegis_runtime.approvals import ApprovalUnavailable
from aegis_runtime.async_reviewed_execution import AsyncReviewedClient, AsyncReviewedTool

ROOT = Path(__file__).resolve().parents[2]
EVENTS = ROOT / "artifacts/async-reviewed-execution/tool-calls.jsonl"


class SyntheticFailure(ValueError):
    pass


async def run(args):
    entered = asyncio.Event()

    async def update_demo_record(*, record_id, value, scenario="success"):
        await asyncio.sleep(0)
        EVENTS.parent.mkdir(parents=True, exist_ok=True)
        with EVENTS.open("a", encoding="utf-8") as output:
            output.write(json.dumps({"record_id": record_id, "value": value, "scenario": scenario}) + "\n")
        entered.set()
        if scenario == "failure":
            raise SyntheticFailure("synthetic partial effect")
        if scenario == "cancel":
            await asyncio.Event().wait()
        return {"record_id": record_id, "updated": True}

    policy = Policy("demo-reviewed-v1", (Rule("permit-demo", "allow", ("demo-agent",),
                                            ("update_demo_record",), ("demo.write",)),))
    async with AsyncReviewedClient(args.endpoint, token=os.environ["AEGIS_APPROVAL_REQUEST_TOKEN"],
                                   execution_token=os.environ["AEGIS_APPROVAL_EXECUTION_TOKEN"],
                                   binding_key=bytes.fromhex(os.environ["AEGIS_APPROVAL_BINDING_KEY"])) as client:
        governed = AsyncReviewedTool(update_demo_record, client=client, policy=policy, subject="demo-agent",
                                     permission="demo.write", tool="update_demo_record",
                                     tool_revision="demo-async-v1", disclose_arguments=True)
        arguments = {"record_id": 9223372036854775807, "value": args.value, "scenario": args.scenario}
        summary = "合成异步写入（取消也可能已有副作用）"
        if args.command == "prepare":
            ticket = await governed.prepare(arguments, summary=summary, action_id=args.action_id, ttl_seconds=600)
            print(json.dumps({"action_id": ticket["action_id"], "status": ticket["status"],
                              "execution_state": ticket["execution_state"]}))
            return
        if args.scenario != "cancel":
            result = await governed.resume(args.action_id, arguments, summary=summary, ttl_seconds=600)
        else:
            # Demo host owns and joins both tasks; the library creates neither.
            worker = asyncio.create_task(governed.resume(args.action_id, arguments, summary=summary, ttl_seconds=600))
            started = asyncio.create_task(entered.wait())
            try:
                await asyncio.wait((worker, started), return_when=asyncio.FIRST_COMPLETED)
                if entered.is_set() and not worker.done():
                    worker.cancel()
                result = await worker
            finally:
                for task in (worker, started):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(worker, started, return_exceptions=True)
        print(json.dumps({"action_id": args.action_id, "confirmation": result.confirmation, "result": result.value}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "resume"))
    parser.add_argument("--endpoint", default="http://127.0.0.1:8000")
    parser.add_argument("--action-id")
    parser.add_argument("--scenario", choices=("success", "failure", "cancel"), default="success")
    parser.add_argument("--value", default="synthetic-async-updated")
    args = parser.parse_args()
    if args.command == "resume" and not args.action_id:
        parser.error("resume requires --action-id")
    try:
        asyncio.run(run(args))
    except asyncio.CancelledError:
        print(json.dumps({"action_id": args.action_id, "cancelled": True, "confirmation": "unknown", "retry": False}))
        return 3
    except SyntheticFailure:
        print(json.dumps({"action_id": args.action_id, "business_error": "SyntheticFailure", "retry": False}))
        return 2
    except (KeyError, ValueError, ApprovalUnavailable, ActionDenied):
        print(json.dumps({"action_id": args.action_id, "operation": "not completed", "retry": False}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
