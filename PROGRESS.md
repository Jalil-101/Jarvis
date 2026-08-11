# Progress

## 2026-08-10 — Phase 0 scaffold

- Created repo, venv wiring, package skeleton
- Claude text chat via `python -m jarvis`
- SQLite conversation logging
- Permission + audit stubs
- Personality prompt in `config/personality.md`

## 2026-08-11 — Phases 1–9 implemented in-tree

Shipped a working operating layer so daily 1-hour sessions improve a real Jarvis instead of empty folders.

- **Phase 1 Baby Jarvis:** edge-tts British voice, STT/wake adapters, sandbox tools (folder, allowlisted commands, weather, system info), Day-30 `python -m jarvis demo`
- **Phase 2 Linux body:** `scripts/install.sh`, `setup-linux.sh`, `deploy.sh`, systemd units, XDG data dir (`~/.local/share/jarvis`)
- **Phase 3 Hands:** allowlisted filesystem, apps, terminal (denylist), clipboard, screenshot, documents, project aliases
- **Phase 4 Memory OS:** people / projects / preferences / episodes + hashed recall, remember/forget/export
- **Phase 5 Research:** DuckDuckGo search, fetch, multi-source `research_topic`
- **Phase 6 Dev agent:** repo tree/search/read/write/tests/git (commit = Level 3)
- **Phase 7 Life admin:** local mail + calendar, drafts, morning briefing; Gmail/Calendar wait on official OAuth files
- **Phase 8 Autonomy:** event bus, quiet hours, rate limit, watchers, `python -m jarvis autonomy`
- **Phase 9 Hardening:** audit redaction, localhost-only nmap, HTTP API on 127.0.0.1 with optional bearer token

## Tomorrow (your 1-hour session)

On Windows, `python` and `jarvis` are not shell commands. Use the `.cmd` wrappers from this repo:

1. Set `ANTHROPIC_API_KEY` in `.env`
2. `.\scripts\run.cmd speak "Yes, sir?"`
3. `.\scripts\run.cmd demo`
4. Text chat: `.\scripts\run.cmd` and teach it one fact about you
5. Tests: `.\scripts\test.cmd`
