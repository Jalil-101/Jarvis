# Jarvis

Persistent, voice-first **personal AI operating layer**: perception → memory → reasoning → permissioned tools → speech.

Windows is the workshop. Ubuntu Linux is the body. The cloud LLM is the brain.

## Day-30 north star

Walk in, say “Jarvis,” get a British reply, remember prior chats, run a few safe commands.

## Quick start (Windows)

Python is **not** on PATH on this machine (the `python` command is a Microsoft Store stub). PowerShell also blocks `.ps1` scripts by default. Use the `.cmd` wrappers — they call `.venv\Scripts\python.exe` directly.

From `C:\Users\abdul\Projects\jarvis`:

```powershell
.\scripts\install.cmd
# Edit .env and set ANTHROPIC_API_KEY=...
.\scripts\run.cmd
```

One-shot (prints **and** speaks the reply):

```powershell
.\scripts\run.cmd --once "Good evening."
```

Text only (no TTS):

```powershell
.\scripts\run.cmd --no-speak --once "Good evening."
```

British TTS smoke test (no API key needed):

```powershell
.\scripts\run.cmd speak "Yes, sir?"
```

Day-30 demo (wake acknowledgement, memory, sandbox folder, weather):

```powershell
.\scripts\run.cmd demo
```

Push-to-talk (needs `.\.venv\Scripts\pip.exe install -e ".[voice]"` for mic/STT):

```powershell
.\scripts\run.cmd voice
```

Always-on wake loop (Linux body uses this under systemd):

```powershell
.\scripts\run.cmd listen
```

**Do not** type `jarvis` or `python` in PowerShell. `jarvis` is not a shell command; `python` opens the Store stub. If you want the raw interpreter:

```powershell
.\.venv\Scripts\python.exe -m jarvis
```

## Commands

Windows: prefix with `.\scripts\run.cmd`. Linux / activated venv: `python -m jarvis`.

| Command | What it does |
| --- | --- |
| `.\scripts\run.cmd` | Text chat with tools + memory |
| `.\scripts\run.cmd speak "..."` | British TTS |
| `.\scripts\run.cmd voice` | Push-to-talk |
| `.\scripts\run.cmd listen` | Wake word → session |
| `.\scripts\run.cmd demo` | Day-30 acceptance script |
| `.\scripts\run.cmd autonomy` | Proactive engine (battery, disk, jobs) |
| `.\scripts\run.cmd serve` | Localhost HTTP API (`/health`, `POST /v1/chat`) |

Resume a session: `.\scripts\run.cmd --session demo`

## Permissions

Maximum capability, minimum unchecked authority. Every tool call is audited to `audit.jsonl`.

| Level | Name | Gate |
| --- | --- | --- |
| 0 | Read | allowlists |
| 1 | Suggest | always |
| 2 | Low-risk | policy |
| 3 | Sensitive | confirm |
| 4 | Dangerous | explicit confirm + audit |

Hard denials (not just “ask first”): `rm -rf /`, `sudo`, path escape from the sandbox / project roots, nmap against anything but localhost.

## Memory

SQLite under the data dir:

- conversation turns (short-term)
- semantic facts, episodes, people, projects, preferences
- hashed n-gram recall (no extra model download)

Say “remember that…” or “my advisor is Sarah” — Jarvis stores it.

On Linux the data dir is `~/.local/share/jarvis` so `git pull` never wipes memory. On Windows it is `./data`. Override with `JARVIS_DATA_DIR`.

## Linux body

See [LINUX.md](LINUX.md). Short version: Ubuntu LTS, `./scripts/install.sh`, `./scripts/setup-linux.sh`, deploy with `./scripts/deploy.sh`.

## Layout

```
jarvis/
  core/          agent + personality
  memory/        SQLite + embeddings
  voice/         wake / STT / TTS
  tools/         computer, web, memory, code, mail, security
  perception/    event bus + watchers
  autonomy/      interrupt policy + engine
  security/      levels + path denylist
  server/        localhost HTTP API
config/          YAML + personality (no secrets)
scripts/         install, run, systemd, deploy
tests/
```

## Config

- Secrets: `.env` (from `.env.example`) — never commit
- Defaults: `config/default.yaml` (projects, allowlists, quiet hours, TTS voice)
- Personality: `config/personality.md`

## Tests

```powershell
.\scripts\test.cmd
```

Equivalent (no wrapper):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Optional extras

```powershell
.\.venv\Scripts\pip.exe install -e ".[voice]"     # mic, faster-whisper, openWakeWord
.\.venv\Scripts\pip.exe install -e ".[desktop]"   # screenshots, PDF, clipboard
```
