"""CLI entrypoint: ``python -m jarvis``."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="Jarvis — personal AI operating layer.",
    )
    parser.add_argument("--once", metavar="MESSAGE", help="Send a single message and exit.")
    parser.add_argument("--session", default=None, help="Resume or name a conversation session id.")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Auto-confirm Level 3+ tools (use only for trusted --once commands).",
    )
    parser.add_argument(
        "--no-speak",
        action="store_true",
        help="Print replies without British TTS.",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("chat", help="Interactive text chat (default).")
    sub.add_parser("voice", help="Push-to-talk voice loop.")
    sub.add_parser("listen", help="Always-on wake-word loop (Linux body).")
    sub.add_parser("demo", help="Day-30 demo: greet, recall, folder, weather.")
    sub.add_parser("autonomy", help="Run the proactive engine (watchers + jobs).")

    speak_p = sub.add_parser("speak", help="Speak text with the British TTS voice.")
    speak_p.add_argument("text", nargs="+", help="Words to speak.")

    serve_p = sub.add_parser("serve", help="Local HTTP API for phone / remote clients.")
    serve_p.add_argument("--host", default=None)
    serve_p.add_argument("--port", type=int, default=None)

    args = parser.parse_args(argv)

    if args.once is not None:
        from jarvis.core.agent import run_once

        reply = run_once(args.once, session_id=args.session, confirm=args.confirm)
        print(reply)
        if not args.no_speak:
            from jarvis.voice.tts import speak

            speak(reply)
        return 0

    cmd = args.cmd or "chat"
    if cmd == "chat":
        from jarvis.core.agent import run_chat_loop

        run_chat_loop(session_id=args.session, speak_replies=not args.no_speak)
        return 0
    if cmd == "voice":
        from jarvis.voice.loop import push_to_talk

        push_to_talk(session_id=args.session)
        return 0
    if cmd == "listen":
        from jarvis.voice.loop import always_on

        always_on(session_id=args.session)
        return 0
    if cmd == "demo":
        from jarvis.voice.loop import day30_demo

        day30_demo()
        return 0
    if cmd == "autonomy":
        from jarvis.autonomy.engine import AutonomyEngine

        AutonomyEngine().run_forever()
        return 0
    if cmd == "speak":
        from jarvis.voice.tts import speak

        speak(" ".join(args.text))
        return 0
    if cmd == "serve":
        from jarvis.server.app import serve

        serve(host=args.host, port=args.port)
        return 0

    parser.error(f"unknown command {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
