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
4. Plain text in Codex mode continues in the same saved Codex session for that Telegram chat.
5. Use `/newsession` when you want a fresh Codex context without deleting older ones.
6. Use `/switchsession` to jump back to a saved Codex session.
7. Use `/run` or `/turix` to switch the chat back to TuriX mode.
8. Use `/thread` style aliases if you prefer thread wording over session wording.
9. Use `/status` or `/logs` only when you need debug details.

## Telegram Commands

- `/start`
  Return the help summary.
- `/help`
  Show supported commands.
- `/chatid`
  Return the current chat id.
- `/mode`
  Show the current plain-text mode for this chat.
- `/session`
  Show the current Codex session binding for this chat.
- `/thread`
  Alias of `/session`.
- `/sessions`
  List saved Codex sessions for this chat.
- `/threads`
  Alias of `/sessions`.
- `/newsession [label]`
  Create and switch to a fresh Codex session slot.
- `/newthread [label]`
  Alias of `/newsession`.
- `/switchsession <ref>`
  Switch to a saved Codex session by index, bridge id, label, or Codex session id.
- `/switchthread <ref>`
  Alias of `/switchsession`.
- `/renamesession <label>`
  Rename the current Codex session slot.
- `/renamethread <label>`
  Alias of `/renamesession`.
- `/dropsession <ref>`
  Forget a saved Codex session slot from bridge state.
- `/dropthread <ref>`
  Alias of `/dropsession`.
- `/codex [prompt]`
  Switch to Codex read-only mode and optionally send a prompt immediately.
- `/codexw [prompt]`
  Switch to Codex workspace-write mode and optionally send a prompt immediately.
- `/run <task>`
  Start a local TuriX task and switch plain text back to TuriX.
- `/turix [task]`
  Same as `/run`, but can also be used without a task to only switch modes.
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

- After `/codex`, plain text continues in the current chat-bound Codex session.
- After `/codexw`, plain text continues in the current chat-bound Codex write session.
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
- Transient Telegram SSL or connection failures are retried automatically, and undelivered replies are queued for later retry.

## Resources

- `scripts/telegram_turix_bridge.py`
  Standard-library Telegram bridge for Codex and TuriX, with per-chat persistent Codex sessions.
- `scripts/launch_bot.ps1`
  Windows launcher and preflight checker.
