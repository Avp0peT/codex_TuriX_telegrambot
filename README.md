# codex_TuriX_telegrambot

Telegram bridge skill for Windows that lets you talk to local Codex and local TuriX from a Telegram bot.

[中文说明](./README.zh-CN.md)

## Overview

This repository contains a public, sanitized version of a local Codex skill named `telegram-turix-bridge`.

It is designed for people who want to:
- chat with local Codex from Telegram
- trigger local TuriX desktop automation from Telegram
- switch between Codex and TuriX inside the same bot chat
- keep secrets and runtime state outside the repository

The bridge runs locally on Windows and uses Telegram long polling. It does not require a hosted backend.

## Features

- Telegram to Codex bridge via `codex exec`
- Telegram to TuriX bridge via local `run_turix.ps1`
- Per-chat mode memory
  After `/codex`, plain text continues to go to Codex
  After `/codexw`, plain text continues to go to Codex workspace-write mode
  After `/run` or `/turix`, plain text switches back to TuriX
- Quiet chat output by default
  Normal replies stay clean
  Debug details stay behind `/status` and `/logs`
- Public-safe structure
  Tokens, chat IDs, logs, runtime state, and machine-specific private data are not included

## Repository Layout

```text
telegram-turix-bridge/
  SKILL.md
  agents/openai.yaml
  scripts/
    launch_bot.ps1
    telegram_turix_bridge.py
```

## What Is Included

- A Codex-discoverable skill folder at `telegram-turix-bridge/`
- A Python Telegram bridge built with the standard library
- A PowerShell launcher for Windows
- Public-facing setup guidance

## What Is Not Included

- Telegram bot tokens
- Allowed chat IDs
- Runtime logs
- Local state files
- Personal machine paths
- Private deployment details

## Installation

Copy the skill into your local Codex skills directory:

```powershell
Copy-Item -Recurse -Force .\telegram-turix-bridge "$HOME\.codex\skills\telegram-turix-bridge"
```

If you also want TuriX support, install or prepare your local `turix-cua` skill and ensure its runner script exists.

## Required Environment Variable

```powershell
$env:TELEGRAM_BOT_TOKEN = "123456:bot-token"
```

## Recommended Environment Variables

```powershell
$env:TELEGRAM_ALLOWED_CHAT_ID = "123456789"
$env:TURIX_RUNNER = "$HOME\.codex\skills\turix-cua\scripts\run_turix.ps1"
$env:TURIX_WORKDIR = "D:\work"
$env:CODEX_WORKDIR = "D:\work"
```

## Optional Environment Variables

```powershell
$env:CODEX_CLI = "codex"
$env:CODEX_SANDBOX = "read-only"
$env:TELEGRAM_BRIDGE_PYTHON = "python"
$env:TELEGRAM_POLL_TIMEOUT = "30"
```

## Start

Run a preflight check:

```powershell
powershell -ExecutionPolicy Bypass -File .\telegram-turix-bridge\scripts\launch_bot.ps1 -Check
```

Start the bridge:

```powershell
powershell -ExecutionPolicy Bypass -File .\telegram-turix-bridge\scripts\launch_bot.ps1
```

## Telegram Commands

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

## Typical Usage

Use Codex chat mode:

```text
/codex Explain the current project structure
Now summarize it in Chinese
```

Switch to TuriX:

```text
/turix Open Edge and go to github.com
```

Check runtime details only when needed:

```text
/status
/logs 30
```

## Security Notes

- Keep `TELEGRAM_BOT_TOKEN` out of the repository
- Prefer a private bot or a strict `TELEGRAM_ALLOWED_CHAT_ID` allowlist
- Keep `/codex` in `read-only` mode by default
- Use `/codexw` only in trusted private chats
- Do not commit `runtime/`, logs, or state files

## License

No license file is included yet. Add one before broader public reuse if needed.
