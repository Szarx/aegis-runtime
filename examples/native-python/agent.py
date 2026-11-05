"""Run from the repo root after installing sdk/python; no model credentials needed."""

import argparse
import json
import os

import aegis
from aegis import observe, tool

ORDERS = {"demo-001": {"order_id": "demo-001", "status": "shipped"}}


@tool(permission="orders.read")
def lookup_order(order_id: str) -> dict[str, str]:
    if order_id not in ORDERS:
        raise LookupError("Synthetic demo order was not found")
    return ORDERS[order_id]


@observe(name="customer-agent")
def customer_agent(order_id: str) -> dict[str, str]:
    return lookup_order(order_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="Aegis native Python tracing demo")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output")
    destination.add_argument("--endpoint", help="Full Collector /v1/traces URL")
    args = parser.parse_args()
    output = args.output or "artifacts/native-python/traces.jsonl"
    if args.endpoint:
        token = os.environ.get("AEGIS_API_TOKEN")
        sdk = aegis.init("order-service", endpoint=args.endpoint, headers={"Authorization": f"Bearer {token}"} if token else None)
    else:
        sdk = aegis.init("order-service", output_path=output)
    try:
        print(json.dumps(customer_agent("demo-001"), ensure_ascii=False))
        try:
            customer_agent("missing-demo-order")
        except LookupError:
            print("Expected failure: synthetic order lookup failed")
        flushed = aegis.flush()
    finally:
        stopped = sdk.shutdown()
    print(json.dumps({"destination": args.endpoint or output, "diagnostics": sdk.diagnostics()}, ensure_ascii=False))
    return 0 if flushed and stopped else 1


if __name__ == "__main__":
    raise SystemExit(main())
