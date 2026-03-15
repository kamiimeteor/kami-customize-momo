from __future__ import annotations

import argparse
import json

from voice_agent.memory import (
    delete_facts_by_query,
    delete_last_fact,
    list_active_facts,
    load_memory_profile,
    memory_summary_text,
    replace_fact_value,
)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("summary")
    subparsers.add_parser("profile")

    facts_parser = subparsers.add_parser("facts")
    facts_parser.add_argument("--limit", type=int, default=20)

    subparsers.add_parser("forget-last")

    forget_parser = subparsers.add_parser("forget")
    forget_parser.add_argument("query")

    replace_parser = subparsers.add_parser("replace")
    replace_parser.add_argument("query")
    replace_parser.add_argument("new_value")

    args = parser.parse_args()

    if args.command == "summary":
        print(memory_summary_text())
    elif args.command == "profile":
        print(json.dumps(load_memory_profile(), ensure_ascii=False, indent=2))
    elif args.command == "facts":
        print(json.dumps(list_active_facts(limit=args.limit), ensure_ascii=False, indent=2))
    elif args.command == "forget-last":
        deleted = delete_last_fact()
        print(json.dumps(deleted, ensure_ascii=False, indent=2) if deleted else "null")
    elif args.command == "forget":
        print(json.dumps(delete_facts_by_query(args.query), ensure_ascii=False, indent=2))
    elif args.command == "replace":
        deleted, replacement = replace_fact_value(args.query, args.new_value)
        print(
            json.dumps(
                {"deleted": deleted, "replacement": replacement},
                ensure_ascii=False,
                indent=2,
            )
        )
