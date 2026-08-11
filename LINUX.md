# Linux body (Ubuntu LTS)

The Windows PC is the workshop. This machine is Jarvis.

Do **not** use Kali as the host OS. Ubuntu 24.04 LTS (or Debian) is the body; security tools are optional packages Jarvis may invoke with confirmation.

## First boot

1. Install Ubuntu LTS on the 8 GB machine.
2. Enable SSH: `sudo apt install openssh-server`
3. From Windows: `ssh <user>@<linux-ip>`
4. Clone this repo (or `git pull` if already cloned).
5. `./scripts/install.sh`
6. Edit `.env` and set `ANTHROPIC_API_KEY`.
7. Attach a microphone and speakers.
8. `./scripts/setup-linux.sh`

Jarvis then runs as a user systemd service after login/reboot:

```
python -m jarvis listen
```

Runtime data (DB, audit log, TTS cache) lives in `~/.local/share/jarvis`, **not** in the git working tree, so deploys never wipe memory.

## Deploy from Windows

```
# on Windows
git push

# on Linux
./scripts/deploy.sh
```

`deploy.sh` is `git pull --ff-only` + pip + `systemctl --user restart jarvis`.

## Audio

```
sudo apt install pulseaudio-utils ffmpeg
```

Optional local STT / wake word:

```
.venv/bin/pip install -e ".[voice]"
```

## Autonomy (optional second service)

```
systemctl --user enable --now jarvis-autonomy.service
```

Battery, disk, morning tick, and scheduled jobs go through the interrupt policy (quiet hours + rate limit).
