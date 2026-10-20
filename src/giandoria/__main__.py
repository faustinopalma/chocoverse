import argparse
import json
import sqlite3
import sys
from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError

from .store import RunStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Giandoria local foundation; never changes Azure or Fabric.")
    parser.add_argument("--database", type=Path, default=Path(".local") / "demo.sqlite3")
    subcommands = parser.add_subparsers(dest="command", required=True)
    init = subcommands.add_parser("init", help="Create a new persistent local run; refuses to overwrite.")
    init.add_argument("--config", type=Path, default=Path("config") / "demo.json")
    init.add_argument("--run-id", required=True)
    for action in ("start", "resume", "pause", "hibernate", "stop", "status"):
        subcommands.add_parser(action)
    advance = subcommands.add_parser("advance", help="Commit unpaced clock ticks, not business simulation.")
    advance.add_argument("--ticks", type=int, default=1)
    export = subcommands.add_parser("export", help="Export CloudEvents JSONL to a new file.")
    export.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    store = RunStore(arguments.database)
    try:
        if arguments.command == "init":
            store.create(arguments.config, arguments.run_id)
        elif arguments.command == "export":
            count = store.export(arguments.output)
            print(json.dumps({"exported_events": count, "output": str(arguments.output)}))
            return 0
        elif arguments.command != "status":
            store.apply(arguments.command, ticks=arguments.ticks if arguments.command == "advance" else 1)
        print(json.dumps(store.status(), indent=2))
    except (OSError, ValueError, sqlite3.Error, ZoneInfoNotFoundError) as error:
        print(f"Giandoria: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
