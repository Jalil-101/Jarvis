# Jarvis

Personal AI operating layer: perception → memory → reasoning → permissioned tools → speech.

## Day-30 north star

Walk in, say “Jarvis,” get a British reply, remember prior chats, run a few safe commands.

**Phase 0 (now):** text chat with Claude + SQLite turn logging + permission/audit stubs.

## Quick start (Windows)

1. **Python 3.12+** installed and on `PATH`.
2. From this repo:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=...
python -m jarvis
```

One-shot message:

```powershell
python -m jarvis --once "Good evening."
```

Resume a session:

```powershell
python -m jarvis --session demo
```

Or use the helper:

```powershell
.\scripts\run.ps1
```

## Layout

```
jarvis/           # Python package (python -m jarvis)
  core/           # agent, personality
  memory/         # SQLite conversation log
  voice/          # wake / STT / TTS (Phase 1)
  tools/          # filesystem, terminal, … (Week 3)
  perception/     # event watchers (later)
  autonomy/       # initiative (later)
  security/       # permission levels + audit log
config/           # YAML + personality (no secrets)
scripts/          # install / run helpers
tests/
data/             # local DB + audit (gitignored)
```

## Permissions (stub)

| Level | Name      | Gate                         |
| ----- | --------- | ---------------------------- |
| 0     | Read      | allowlists                   |
| 1     | Suggest   | always                       |
| 2     | Low-risk  | policy                       |
| 3     | Sensitive | confirm                      |
| 4     | Dangerous | explicit confirm + audit     |

Tool calls (when added) go through `PermissionGate` and append to `data/audit.jsonl`.

## Config

- Secrets: `.env` (from `.env.example`) — never commit.
- Defaults: `config/default.yaml`
- Personality: `config/personality.md`

## What’s next

- Phase 1 Week 1: British TTS + STT duplex loop
- Then wake word, safe tools, Day-30 demo
