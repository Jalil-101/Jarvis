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

## 2026-08-25 — Week 2–4 workshop push (Windows)

Shipped without waiting on Linux body:

- **Wake:** openWakeWord + **Enter interrupt** in parallel (no more stuck wake)
- **Always-on:** retry once on missed STT before “Standing by”
- **Memory:** broader “remember that…”, favorite→preference extraction
- **Safe hands:** Windows allowlisted `date` / `disk` / `dir`; `.\scripts\run.cmd hands` smoke (8 actions + audit)
- **Day-30 demo:** structured steps (ack → tools → recall → chat → audit tail)

**Run today:**

1. `.\scripts\run.cmd hands`
2. `.\scripts\run.cmd demo`
3. `.\scripts\run.cmd listen` — Hey Jarvis or Enter → teach a fact → recall → “that's all”

Still later (plan): Linux systemd body, STT clarity (`JARVIS_STT_MODEL=base`), Gmail OAuth, autonomy polish.

## 2026-08-25 — Voice latency + transcript polish

- STT default `tiny.en` (fast CPU) with beam_size=1; preload on voice start
- Pre-roll buffer (~0.6s) so early words aren’t dropped; gentler VAD padding
- Local transcript cleanup (Jarvis misspellings, fillers) — no extra LLM round-trip
- Voice mode: shorter Claude replies (256 tokens) + 1–2 sentence system hint

**Tradeoff:** tiny.en is faster but can still jumble uncommon words. For clearer STT (slower), add to `.env`:
`JARVIS_STT_MODEL=base` or `small.en`

## Tomorrow (your 1-hour session)

On Windows, `python` and `jarvis` are not shell commands. Use the `.cmd` wrappers from this repo:

1. Set `ANTHROPIC_API_KEY` in `.env`
2. `.\scripts\run.cmd speak "Yes, sir?"`
3. `.\scripts\run.cmd demo`
4. Text chat: `.\scripts\run.cmd` and teach it one fact about you
5. Tests: `.\scripts\test.cmd`

## 2026-08-25 — Week 1→2 voice upgrade (plan-aligned)

- Prefer **ElevenLabs** when `ELEVENLABS_API_KEY` is set (`tts_provider: auto`); flash model for lower latency
- Strip markdown / trim long replies before speaking so it feels less like reading aloud
- Personality tightened for 1–3 sentence spoken answers
- `scripts/install-voice.cmd` + clearer always-on `listen` path (wake → session → silence timeout)

**Your next moves (do these, in order):**

1. Add ElevenLabs key + British Voice ID to `.env` → `.\scripts\run.cmd speak "Yes, sir?"`
2. `.\scripts\install-voice.cmd` then `.\scripts\run.cmd listen` (leave terminal open)
3. Teach one fact by voice; confirm recall; say "that's all" to end the session

