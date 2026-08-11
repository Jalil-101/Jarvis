# Remote / phone clients

Jarvis’s brain stays on the Linux (or Windows) host. Other devices only send text.

Start the API on the host (localhost by default):

```
python -m jarvis serve
```

- `GET /health` → `{"ok": true}`
- `POST /v1/chat` with `{"text": "What's on my calendar?"}`
- `POST /v1/speak` with `{"text": "Yes, sir?"}`

Bind-address is `127.0.0.1` in `config/default.yaml`. To reach it from a phone on your LAN, change `server.host` **and** set `JARVIS_API_TOKEN` in `.env`, then send `Authorization: Bearer <token>`. Do not expose the port to the public internet.
