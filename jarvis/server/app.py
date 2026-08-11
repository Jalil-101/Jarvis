"""Minimal HTTP API bound to localhost by default.

POST /v1/chat   {"text": "...", "session": "optional"}
POST /v1/speak  {"text": "..."}
GET  /health
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from jarvis.config_loader import get_settings
from jarvis.core.agent import Agent


def serve(host: str | None = None, port: int | None = None) -> None:
    settings = get_settings()
    host = host or settings.server_host
    port = port or settings.server_port
    agent = Agent(session_id="http", confirm_fn=lambda _p: False)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:  # noqa: A003
            print(f"[http] {self.address_string()} {fmt % args}")

        def _auth(self) -> bool:
            token = settings.api_token
            if not token:
                return True
            given = self.headers.get("Authorization", "")
            return given == f"Bearer {token}"

        def _json(self, code: int, payload: dict) -> None:
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:  # noqa: N802
            if urlparse(self.path).path == "/health":
                self._json(200, {"ok": True, "name": "jarvis"})
                return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if not self._auth():
                self._json(401, {"error": "unauthorized"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            path = urlparse(self.path).path
            if path == "/v1/chat":
                text = str(body.get("text", "")).strip()
                if not text:
                    self._json(400, {"error": "text required"})
                    return
                reply = agent.chat(text)
                self._json(200, {"reply": reply})
                return
            if path == "/v1/speak":
                from jarvis.voice.tts import speak

                speak(str(body.get("text", "")))
                self._json(200, {"ok": True})
                return
            self._json(404, {"error": "not found"})

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Jarvis HTTP API on http://{host}:{port}  (health: /health)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("HTTP API stopped.")
        httpd.server_close()
