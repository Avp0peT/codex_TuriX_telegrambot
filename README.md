# codex_TuriX_telegrambot

Public, sanitized Windows skill for running a Telegram bot that can talk to local Codex and TuriX.

What is included:
- A Codex-discoverable skill folder at `telegram-turix-bridge/`
- A Python long-poll bridge using only the standard library
- A PowerShell launcher for Windows

What is intentionally not included:
- Bot tokens
- Chat IDs
- Runtime logs
- Local state files
- Machine-specific private paths

## Install

Copy `telegram-turix-bridge/` into your local Codex skills directory, for example:

```powershell
Copy-Item -Recurse -Force .\telegram-turix-bridge "$HOME\.codex\skills\telegram-turix-bridge"
```

## Required environment variables

```powershell
$env:TELEGRAM_BOT_TOKEN = "123456:bot-token"
```

Recommended:

```powershell
$env:TELEGRAM_ALLOWED_CHAT_ID = "123456789"
$env:TURIX_RUNNER = "$HOME\.codex\skills\turix-cua\scripts\run_turix.ps1"
$env:TURIX_WORKDIR = "D:\work"
$env:CODEX_WORKDIR = "D:\work"
```

Optional:

```powershell
$env:CODEX_CLI = "codex"
$env:CODEX_SANDBOX = "read-only"
$env:TELEGRAM_BRIDGE_PYTHON = "python"
$env:TELEGRAM_POLL_TIMEOUT = "30"
```

## Start

```powershell
powershell -ExecutionPolicy Bypass -File .\telegram-turix-bridge\scripts\launch_bot.ps1 -Check
powershell -ExecutionPolicy Bypass -File .\telegram-turix-bridge\scripts\launch_bot.ps1
```

## Telegram commands

- `/chatid`
- `/mode`
- `/codex <prompt>`
- `/codexw <prompt>`
- `/run <task>`
- `/turix <task>`
- `/dryrun <task>`
- `/resume <agent_id>`
- `/status`
- `/logs [N]`
- `/stop`

Plain text follows the current chat mode:
- `/codex` switches plain text to Codex read-only
- `/codexw` switches plain text to Codex workspace-write
- `/run` or `/turix` switches plain text back to TuriX
