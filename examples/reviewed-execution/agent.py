"""Synthetic local append only; no LLM or external business system."""

import argparse
import json
import os
from pathlib import Path

from aegis_policy import Policy, Rule
from aegis_runtime import ActionDenied
from aegis_runtime.approvals import ApprovalUnavailable
from aegis_runtime.reviewed_execution import ReviewedClient, ReviewedTool

ROOT = Path(__file__).resolve().parents[2]
EVENTS = ROOT / "artifacts/reviewed-execution/tool-calls.jsonl"


class SyntheticFailure(ValueError):
    pass


def update_demo_record(*, record_id, value, fail=False):
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS.open("a", encoding="utf-8") as output:
        output.write(json.dumps({"record_id": record_id, "value": value, "fail": fail}) + "\n")
    if fail:
        raise SyntheticFailure("synthetic partial effect")
    return {"record_id": record_id, "updated": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "resume"))
    parser.add_argument("--endpoint", default="http://127.0.0.1:8000")
    parser.add_argument("--action-id")
    parser.add_argument("--fail", action="store_true")
    parser.add_argument("--value", default="synthetic-updated")
    args = parser.parse_args()
    if args.command == "resume" and not args.action_id:
        parser.error("resume requires --action-id")
    summary = "合成记录写入（核对参数后可恢复一次）"
    arguments = {"record_id": 9223372036854775807, "value": args.value, "fail": args.fail}
    try:
        client = ReviewedClient(args.endpoint, token=os.environ["AEGIS_APPROVAL_REQUEST_TOKEN"],
                                execution_token=os.environ["AEGIS_APPROVAL_EXECUTION_TOKEN"],
                                binding_key=bytes.fromhex(os.environ["AEGIS_APPROVAL_BINDING_KEY"]))
        policy = Policy("demo-reviewed-v1", (Rule("permit-demo", "allow", ("demo-agent",), ("update_demo_record",), ("demo.write",)),))
        governed = ReviewedTool(update_demo_record, client=client, policy=policy, subject="demo-agent", permission="demo.write",
                                tool="update_demo_record", tool_revision="demo-impl-v1", disclose_arguments=True)
        if args.command == "prepare":
            ticket = governed.prepare(arguments, summary=summary, action_id=args.action_id, ttl_seconds=600)
            print(json.dumps({"action_id": ticket["action_id"], "status": ticket["status"], "execution_state": ticket["execution_state"]}))
        else:
            result = governed.resume(args.action_id, arguments, summary=summary, ttl_seconds=600)
            print(json.dumps({"action_id": args.action_id, "confirmation": result.confirmation, "result": result.value}))
    except SyntheticFailure:
        print(json.dumps({"action_id": args.action_id, "business_error": "SyntheticFailure", "retry": False}))
        return 2
    except (KeyError, ValueError, ApprovalUnavailable, ActionDenied):
        print(json.dumps({"action_id": args.action_id, "operation": "not completed", "retry": False}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
