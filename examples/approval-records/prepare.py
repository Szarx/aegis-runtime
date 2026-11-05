"""Prepare one synthetic approval record. Does not call a tool or model."""

import argparse
import os
import uuid

from aegis_policy import Policy
from aegis_runtime.approvals import ApprovalClient, ApprovalUnavailable


def main():
    parser = argparse.ArgumentParser(description="Prepare a synthetic approval; no execution")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8000")
    parser.add_argument("--action-id", help="Reuse only for an explicit retry of the same request")
    args = parser.parse_args()
    try:
        key = bytes.fromhex(os.environ["AEGIS_APPROVAL_BINDING_KEY"])
        client = ApprovalClient(args.endpoint, token=os.environ["AEGIS_APPROVAL_REQUEST_TOKEN"], binding_key=key)
        result = client.prepare(action_id=args.action_id or uuid.uuid4().hex, subject="demo-agent", tool="update_demo_record",
                                permission="demo.write", policy=Policy("demo-v1", ()), arguments={"record": "synthetic-001", "value": 1},
                                summary="合成演示：申请修改测试记录（只记录审批，不执行）")
    except (KeyError, ValueError, ApprovalUnavailable):
        parser.exit(1, "Approval preparation failed; check local configuration and service.\n")
    print("action_id=" + result["action_id"] + " status=" + result["status"] + "; no tool executed")


if __name__ == "__main__":
    main()
