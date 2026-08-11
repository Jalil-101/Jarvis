"""CLI entrypoint: ``python -m jarvis``."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="Jarvis - personal AI operating layer (text chat for Phase 0).",
    )
    parser.add_argument(
        "--once",
        metavar="MESSAGE",
        help="Send a single message and exit (non-interactive).",
    )
    parser.add_argument(
        "--session",
        default=None,
        help="Resume or name a conversation session id.",
    )
    args = parser.parse_args(argv)

    from jarvis.core.agent import run_chat_loop, run_once

    if args.once is not None:
        reply = run_once(args.once, session_id=args.session)
        print(reply)
        return 0

    run_chat_loop(session_id=args.session)
    return 0


if __name__ == "__main__":
    sys.exit(main())
