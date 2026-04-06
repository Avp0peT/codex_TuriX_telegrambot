---
name: telegram-turix-bridge
description: Set up and run a Windows-local Telegram bot that long-polls Telegram and forwards `/run` or `/resume` into a local TuriX runner plus `/codex` or `/codexw` into the local Codex CLI. Use when Codex needs to create, configure, troubleshoot, or operate Telegram bot access, BotFather tokens, chat-id allowlists, Telegram-to-TuriX bridges, Telegram-to-Codex chat bridges, or remote task dispatch from Telegram.
---

# Telegram TuriX Bridge

## Quick Start

Use this skill to run a Telegram bot on Windows that can talk to both local Codex and local TuriX.

1. Create a Telegram bot with BotFather.
2. Set environment variables before launch:

```powershell
$env:TELEGRAM_BOT_TOKEN = "123456:bot-token"
$env:TELEGRAM_ALLOWED_CHAT_ID = "123456789"
$env:TURIX_RUNNER = "$HOME\.codex\skills\turix-cua\scripts\run_turix.ps1"
$env:TURIX_WORKDIR = "D:\work"
$env:CODEX_WORKDIR = "D:\work"
```

3. Validate the setup:

```powershell
powershell -ExecutionPolicy Bypass -File "{baseDir}\scripts\launch_bot.ps1" -Check
```

4. Start the bridge:

```powershell
powershell -ExecutionPolicy Bypass -File "{baseDir}\scripts\launch_bot.ps1"
```

## Workflow

1. Keep the bot private or use a strict `TELEGRAM_ALLOWED_CHAT_ID` allowlist.
2. Use `/chatid` once to discover the chat id to allow.
3. Use `/codex` or `/codexw` to switch the chat into Codex mode.
4. Use `/run` or `/turix` to switch the chat back to TuriX mode.
5. Use `/status` or `/logs` only when you need debug details.

## Telegram Commands

- `/start`
  Return the help summary.
- `/help`
  Show supported commands.
- `/chatid`
  Return the current chat id.
- `/mode`
  Show the current plain-text mode for this chat.
- `/codex <prompt>`
  Run local Codex in read-only mode and switch plain text to Codex.
- `/codexw <prompt>`
  Run local Codex in workspace-write mode and switch plain text to Codex write mode.
- `/run <task>`
  Start a local TuriX task and switch plain text back to TuriX.
- `/turix <task>`
  Same as `/run`.
- `/dryrun <task>`
  Run the TuriX launcher in `--dry-run` mode.
- `/resume <agent_id>`
  Resume a previous TuriX task.
- `/status`
  Show active process, engine, mode, and log path.
- `/logs [N]`
  Show the last `N` lines from the current log file. Default `20`.
- `/stop`
  Stop the active process tree.

Plain text follows the current chat mode:
- After `/codex`, plain text goes to Codex read-only.
- After `/codexw`, plain text goes to Codex workspace-write.
- After `/run` or `/turix`, plain text goes to TuriX.

## Required Environment Variables

- `TELEGRAM_BOT_TOKEN`
  Required. Telegram bot token from BotFather.

## Recommended Environment Variables

- `TELEGRAM_ALLOWED_CHAT_ID`
  One chat id or a comma-separated allowlist.
- `TURIX_RUNNER`
  Path to `run_turix.ps1`.
- `TURIX_WORKDIR`
  Working directory for TuriX tasks.
- `CODEX_WORKDIR`
  Working directory for Codex tasks.

## Optional Environment Variables

- `CODEX_CLI`
  Defaults to `codex`.
- `CODEX_SANDBOX`
  Defaults to `read-only`.
- `TELEGRAM_BRIDGE_PYTHON`
  Override the Python executable used by the launcher.
- `TELEGRAM_POLL_TIMEOUT`
  Long-poll timeout in seconds. Defaults to `30`.

## Safety Rules

- Keep the bot token out of the repository.
- Prefer a private bot or a strict chat-id allowlist.
- Keep `/codex` on `read-only` by default.
- Use `/codexw` only for trusted private chats.
- Do not expose runtime logs or `state.json` publicly.

## Resources

- `scripts/telegram_turix_bridge.py`
  Standard-library Telegram bridge for Codex and TuriX.
- `scripts/launch_bot.ps1`
  Windows launcher and preflight checker.
