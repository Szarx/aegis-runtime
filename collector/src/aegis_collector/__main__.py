"""Explicit migration and local server commands."""

import argparse
import os

from .api import create_app
from .storage import PostgresSpanStore


def configured_store() -> PostgresSpanStore:
    return PostgresSpanStore(os.environ.get("AEGIS_DATABASE_URL", ""), os.environ.get("AEGIS_DB_SCHEMA", "aegis"))


def main():
    parser = argparse.ArgumentParser(description="Aegis Collector")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("migrate")
    server = subcommands.add_parser("serve")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8000)
    server.add_argument("--migrate", action="store_true")
    args = parser.parse_args()
    store = configured_store()
    if args.command == "migrate" or args.migrate:
        store.migrate()
    if args.command == "migrate":
        print("Aegis schema version 4 is ready")
        return
    import uvicorn
    uvicorn.run(create_app(store, api_token=os.environ.get("AEGIS_API_TOKEN") or None,
                          approval_request_token=os.environ.get("AEGIS_APPROVAL_REQUEST_TOKEN") or None,
                          approval_review_token=os.environ.get("AEGIS_APPROVAL_REVIEW_TOKEN") or None,
                          approval_reviewer=os.environ.get("AEGIS_APPROVAL_REVIEWER", "local-reviewer"),
                          approval_execution_token=os.environ.get("AEGIS_APPROVAL_EXECUTION_TOKEN") or None,
                          approval_executor=os.environ.get("AEGIS_APPROVAL_EXECUTOR", "local-executor")), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
