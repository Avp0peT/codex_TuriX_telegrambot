# codex_TuriX_telegrambot

Windows-local Telegram bridge skill for talking to local Codex and local TuriX from a Telegram bot.

[中文说明](./README.zh-CN.md)

## Overview

This repository contains a public, sanitized version of the `telegram-turix-bridge` Codex skill.

It is designed for people who want to:

- chat with a local Codex instance from Telegram
- trigger local TuriX desktop automation from Telegram
- switch between Codex and TuriX inside the same bot chat
- keep secrets, logs, and runtime state outside the repository

The bridge runs locally on Windows and uses Telegram long polling. No hosted backend is required.

## Highlights

- Telegram to Codex bridge via `codex exec`
- Telegram to TuriX bridge via local `run_turix.ps1`
- Per-chat persistent Codex sessions
- Thread-style aliases for session switching, such as `/thread`, `/threads`, `/newthread`, and `/switchthread`
- Session management commands for creating, listing, switching, renaming, and forgetting saved Codex sessions
- Retry and deferred delivery for transient Telegram API network failures
- Per-chat mode memory
- Quiet chat output by default, with `/status` and `/logs` for troubleshooting
- Public-safe repository layout without tokens, chat ids, or runtime state

## Repository Layout

```text
telegram-turix-bridge/
  SKILL.md
  agents/openai.yaml
  scripts/
    launch_bot.ps1
    telegram_turix_bridge.py
```

## Not Included

- Telegram bot tokens
- Allowed chat ids
- Runtime logs
- State files
- Personal machine paths
- Private deployment details

## Installation

Copy the skill into your local Codex skills directory:

```powershell
Copy-Item -Recurse -Force .\telegram-turix-bridge "$HOME\.codex\skills\telegram-turix-bridge"
```

If you also want TuriX support, prepare your local `turix-cua` skill and make sure its `run_turix.ps1` runner exists.

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
- `/session`
- `/thread`
- `/sessions`
- `/threads`
- `/newsession [label]`
- `/newthread [label]`
- `/switchsession <ref>`
- `/switchthread <ref>`
- `/renamesession <label>`
- `/renamethread <label>`
- `/dropsession <ref>`
- `/dropthread <ref>`
- `/codex [prompt]`
- `/codexw [prompt]`
- `/run <task>`
- `/turix [task]`
- `/dryrun <task>`
- `/resume <agent_id>`
- `/status`
- `/logs [N]`
- `/stop`

## How Persistent Codex Sessions Work

- Each Telegram chat keeps its own saved Codex session slots.
- The first `/codex` message starts a fresh Codex session for that chat.
- Later plain-text messages in Codex mode continue through `codex exec resume <session-id>`.
- `/newsession` creates a fresh conversation slot without deleting older ones.
- `/switchsession` lets you jump back to an earlier slot by index, bridge session id, label, or Codex session id.
- `/thread` and related thread commands are user-friendly aliases for the same saved Codex session slots.

## Network Resilience

- Telegram API calls retry automatically on transient SSL or connection failures.
- If a reply cannot be delivered immediately, it is queued in local state and retried on the next successful loop.
- Temporary Telegram network issues should no longer kill the bridge process.

## Typical Usage

Start a persistent Codex chat:

```text
/codex Explain the current project structure
Now summarize it in Chinese
What risks do you see next?
```

Create a fresh Codex session:

```text
/newsession release-notes
/codex Draft release notes for the latest bridge changes
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
