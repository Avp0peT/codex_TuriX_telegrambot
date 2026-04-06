import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = SKILL_DIR / "runtime"
LOG_DIR = RUNTIME_DIR / "logs"
STATE_FILE = RUNTIME_DIR / "state.json"
DEFAULT_RUNNER = Path.home() / ".codex" / "skills" / "turix-cua" / "scripts" / "run_turix.ps1"
DEFAULT_WORKDIR = Path.cwd()
MAX_MESSAGE_LEN = 3500
SESSION_ID_RE = re.compile(r"session id:\s*([0-9a-fA-F-]{36})", re.IGNORECASE)


def ensure_runtime_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else default


def now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict) -> None:
    ensure_runtime_dirs()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def chat_modes(state: dict) -> dict:
    modes = state.get("chat_modes")
    if isinstance(modes, dict):
        return modes
    modes = {}
    state["chat_modes"] = modes
    return modes


def get_chat_mode(state: dict, chat_id: str) -> dict:
    mode = chat_modes(state).get(chat_id)
    if isinstance(mode, dict):
        return mode
    return {"engine": "turix", "sandbox": ""}


def set_chat_mode(state: dict, chat_id: str, *, engine: str, sandbox: str = "") -> None:
    chat_modes(state)[chat_id] = {"engine": engine, "sandbox": sandbox}
    save_state(state)


def codex_chats(state: dict) -> dict:
    chats = state.get("codex_chats")
    if isinstance(chats, dict):
        return chats
    chats = {}
    state["codex_chats"] = chats
    return chats


def codex_chat_state(state: dict, chat_id: str) -> dict:
    chats = codex_chats(state)
    chat_state = chats.get(chat_id)
    if not isinstance(chat_state, dict):
        chat_state = {}
        chats[chat_id] = chat_state
    sessions = chat_state.get("sessions")
    if not isinstance(sessions, dict):
        sessions = {}
        chat_state["sessions"] = sessions
    if not isinstance(chat_state.get("current_session_key"), str):
        chat_state["current_session_key"] = ""
    if not isinstance(chat_state.get("next_session_number"), int):
        chat_state["next_session_number"] = 1
    return chat_state


def codex_sessions(chat_state: dict) -> dict:
    sessions = chat_state.get("sessions")
    if isinstance(sessions, dict):
        return sessions
    sessions = {}
    chat_state["sessions"] = sessions
    return sessions


def ordered_session_keys(chat_state: dict) -> list[str]:
    sessions = codex_sessions(chat_state)
    return sorted(sessions.keys(), key=lambda key: (int(sessions[key].get("created_index", 0)), key))


def current_session_key(chat_state: dict) -> str:
    key = chat_state.get("current_session_key")
    return key if isinstance(key, str) else ""


def get_session_entry(chat_state: dict, session_key: str) -> dict | None:
    entry = codex_sessions(chat_state).get(session_key)
    return entry if isinstance(entry, dict) else None


def current_session_entry(chat_state: dict) -> dict | None:
    key = current_session_key(chat_state)
    if not key:
        return None
    return get_session_entry(chat_state, key)


def normalize_label(label: str) -> str:
    return " ".join(label.strip().split())[:80]


def create_chat_session(
    state: dict,
    chat_id: str,
    *,
    label: str = "",
    sandbox: str = "",
    codex_session_id: str = "",
) -> dict:
    chat_state = codex_chat_state(state, chat_id)
    created_index = int(chat_state.get("next_session_number", 1))
    chat_state["next_session_number"] = created_index + 1
    session_key = f"s{created_index:03d}"
    session_label = normalize_label(label) or f"session-{created_index}"
    entry = {
        "session_key": session_key,
        "label": session_label,
        "codex_session_id": codex_session_id.strip(),
        "sandbox": sandbox.strip(),
        "created_at": now_text(),
        "created_index": created_index,
        "last_used_at": "",
        "message_count": 0,
        "last_log_path": "",
        "last_reply_path": "",
        "last_prompt": "",
    }
    codex_sessions(chat_state)[session_key] = entry
    chat_state["current_session_key"] = session_key
    save_state(state)
    return entry


def ensure_current_chat_session(state: dict, chat_id: str, *, sandbox: str = "") -> dict:
    chat_state = codex_chat_state(state, chat_id)
    entry = current_session_entry(chat_state)
    if entry:
        if sandbox:
            entry["sandbox"] = sandbox
            save_state(state)
        return entry
    return create_chat_session(state, chat_id, sandbox=sandbox)


def parse_switch_ref(chat_state: dict, ref: str) -> dict | None:
    target = ref.strip()
    if not target:
        return current_session_entry(chat_state)

    entry = get_session_entry(chat_state, target)
    if entry:
        return entry

    lowered = target.lower()
    for session_key in ordered_session_keys(chat_state):
        current = get_session_entry(chat_state, session_key)
        if not current:
            continue
        if str(current.get("codex_session_id", "")).lower() == lowered:
            return current
        if str(current.get("label", "")).lower() == lowered:
            return current

    if target.isdigit():
        index = int(target)
        ordered = ordered_session_keys(chat_state)
        if 1 <= index <= len(ordered):
            return get_session_entry(chat_state, ordered[index - 1])

    return None


def switch_chat_session(state: dict, chat_id: str, ref: str) -> dict | None:
    chat_state = codex_chat_state(state, chat_id)
    entry = parse_switch_ref(chat_state, ref)
    if not entry:
        return None
    chat_state["current_session_key"] = entry["session_key"]
    save_state(state)
    return entry


def rename_current_chat_session(state: dict, chat_id: str, label: str) -> dict | None:
    chat_state = codex_chat_state(state, chat_id)
    entry = current_session_entry(chat_state)
    if not entry:
        return None
    entry["label"] = normalize_label(label) or entry["label"]
    save_state(state)
    return entry


def drop_chat_session(state: dict, chat_id: str, ref: str) -> tuple[dict | None, bool]:
    chat_state = codex_chat_state(state, chat_id)
    entry = parse_switch_ref(chat_state, ref)
    if not entry:
        return None, False

    session_key = entry["session_key"]
    was_current = current_session_key(chat_state) == session_key
    codex_sessions(chat_state).pop(session_key, None)

    remaining = ordered_session_keys(chat_state)
    if was_current:
        chat_state["current_session_key"] = remaining[-1] if remaining else ""
    save_state(state)
    return entry, was_current


def telegram_token() -> str:
    return env("TELEGRAM_BOT_TOKEN")


def allowed_chat_ids() -> set[str]:
    raw = env("TELEGRAM_ALLOWED_CHAT_ID")
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def runner_path() -> Path:
    raw = env("TURIX_RUNNER")
    return Path(raw) if raw else DEFAULT_RUNNER


def workdir_path() -> Path:
    raw = env("TURIX_WORKDIR")
    return Path(raw) if raw else DEFAULT_WORKDIR


def codex_workdir_path() -> Path:
    raw = env("CODEX_WORKDIR")
    return Path(raw) if raw else workdir_path()


def codex_cli() -> str:
    return env("CODEX_CLI", "codex")


def codex_cli_resolved() -> str | None:
    raw = codex_cli()
    if raw and Path(raw).exists():
        return raw
    return shutil.which(raw)


def codex_default_sandbox() -> str:
    value = env("CODEX_SANDBOX", "read-only").lower()
    if value not in {"read-only", "workspace-write", "danger-full-access"}:
        return "read-only"
    return value


def poll_timeout() -> int:
    raw = env("TELEGRAM_POLL_TIMEOUT", "30")
    try:
        value = int(raw)
    except ValueError:
        value = 30
    return min(max(value, 1), 60)


def api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{telegram_token()}/{method}"


def api_call(method: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload or {}).encode("utf-8")
    request = urllib.request.Request(
        api_url(method),
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        body = response.read().decode("utf-8")
    parsed = json.loads(body)
    if not parsed.get("ok"):
        raise RuntimeError(f"Telegram API {method} failed: {parsed}")
    return parsed["result"]


def send_message(chat_id: str | int, text: str) -> None:
    if not text:
        return
    message = text
    while message:
        chunk = message[:MAX_MESSAGE_LEN]
        split_at = chunk.rfind("\n")
        if len(message) > MAX_MESSAGE_LEN and split_at > 500:
            chunk = chunk[:split_at]
        api_call("sendMessage", {"chat_id": str(chat_id), "text": chunk})
        message = message[len(chunk):].lstrip("\n")


def get_updates(offset: int | None) -> list[dict]:
    payload = {"timeout": poll_timeout()}
    if offset is not None:
        payload["offset"] = offset
    return api_call("getUpdates", payload)


def is_pid_running(pid: int | None) -> bool:
    if not pid:
        return False
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return str(pid) in result.stdout


def stop_pid_tree(pid: int) -> tuple[bool, str]:
    result = subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
        check=False,
    )
    ok = result.returncode == 0
    output = (result.stdout or "") + (result.stderr or "")
    return ok, output.strip()


def tail_lines(path: Path, count: int) -> str:
    if not path.exists():
        return f"log file not found: {path}"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:
        return f"failed to read log file: {exc}"
    tail = lines[-count:] if lines else ["<log is empty>"]
    return "\n".join(tail)


def extract_session_id(log_path: Path) -> str:
    if not log_path.exists():
        return ""
    try:
        for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines()[:80]:
            match = SESSION_ID_RE.search(line)
            if match:
                return match.group(1)
    except Exception:
        return ""
    return ""


def build_run_command(task: str, *, dry_run: bool = False, resume_id: str = "") -> list[str]:
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(runner_path()),
    ]
    if dry_run:
        command.append("--dry-run")
    if resume_id:
        command.extend(["--resume", resume_id])
    if task:
        command.append(task)
    return command


def build_codex_command(
    prompt: str,
    *,
    output_path: Path,
    sandbox: str,
    resume_session_id: str = "",
) -> list[str]:
    cli = codex_cli_resolved() or codex_cli()
    command = [
        cli,
        "exec",
        "--skip-git-repo-check",
        "-C",
        str(codex_workdir_path()),
        "-s",
        sandbox,
        "--color",
        "never",
        "-o",
        str(output_path),
    ]
    if resume_session_id:
        command.extend(["resume", resume_session_id, prompt])
    else:
        command.append(prompt)
    return command


def render_help() -> str:
    return (
        "Telegram TuriX Bridge commands:\n"
        "/chatid - show current chat id\n"
        "/run <task> - start a TuriX task\n"
        "/dryrun <task> - validate the TuriX launch command\n"
        "/resume <agent_id> - resume a previous TuriX task\n"
        "/codex [prompt] - switch to Codex read-only mode, optionally send a prompt now\n"
        "/codexw [prompt] - switch to Codex workspace-write mode, optionally send a prompt now\n"
        "/turix [task] - switch plain text back to TuriX, optionally start a task now\n"
        "/mode - show the current plain-text default for this chat\n"
        "/session - show the current Codex session binding for this chat\n"
        "/sessions - list saved Codex sessions for this chat\n"
        "/newsession [label] - create and switch to a fresh Codex session slot\n"
        "/switchsession <ref> - switch Codex session by index, bridge id, label, or Codex session id\n"
        "/renamesession <label> - rename the current Codex session slot\n"
        "/dropsession <ref> - forget a saved Codex session slot from bridge state\n"
        "/status - show active task status\n"
        "/logs [N] - show last log lines\n"
        "/stop - stop the current TuriX/Codex run\n"
        "Plain text messages follow the current chat mode. Codex mode keeps using the current chat-bound session."
    )


def parse_command(text: str) -> tuple[str, str]:
    if not text:
        return "", ""
    text = text.strip()
    if not text:
        return "", ""
    if not text.startswith("/"):
        return "plain", text
    first, _, rest = text.partition(" ")
    command = first[1:].split("@", 1)[0].lower()
    return command, rest.strip()


def preflight() -> tuple[bool, str]:
    issues = []
    token = telegram_token()
    if not token:
        issues.append("missing TELEGRAM_BOT_TOKEN")
    runner = runner_path()
    if not runner.exists():
        issues.append(f"missing TuriX runner: {runner}")
    workdir = workdir_path()
    if not workdir.exists():
        issues.append(f"missing workdir: {workdir}")
    codex_path = codex_cli_resolved()
    codex_wd = codex_workdir_path()
    if not codex_wd.exists():
        issues.append(f"missing Codex workdir: {codex_wd}")
    if not codex_path:
        issues.append(f"missing Codex CLI: {codex_cli()}")
    if issues:
        return False, "\n".join(issues)
    return True, (
        "Configuration OK\n"
        f"runner={runner}\n"
        f"workdir={workdir}\n"
        f"codex_cli={codex_path}\n"
        f"codex_workdir={codex_wd}\n"
        f"allowed_chat_ids={','.join(sorted(allowed_chat_ids())) or '<all>'}"
    )


def describe_chat_mode(state: dict, chat_id: str) -> str:
    mode = get_chat_mode(state, chat_id)
    engine = mode.get("engine", "turix")
    sandbox = mode.get("sandbox") or codex_default_sandbox()
    if engine == "codex":
        return f"Current plain-text mode: Codex ({sandbox})"
    return "Current plain-text mode: TuriX"


def format_session_entry(entry: dict, *, index: int, is_current: bool) -> str:
    marker = "*" if is_current else " "
    codex_session_id = entry.get("codex_session_id") or "<pending first Codex run>"
    sandbox = entry.get("sandbox") or codex_default_sandbox()
    used = entry.get("last_used_at") or entry.get("created_at") or "<unknown>"
    return (
        f"{marker} {index}. {entry.get('label', '<unnamed>')} [{entry.get('session_key', '?')}]\n"
        f"   sandbox={sandbox}\n"
        f"   codex_session_id={codex_session_id}\n"
        f"   last_used={used}\n"
        f"   messages={entry.get('message_count', 0)}"
    )


def describe_current_session(state: dict, chat_id: str) -> str:
    chat_state = codex_chat_state(state, chat_id)
    entry = current_session_entry(chat_state)
    if not entry:
        return (
            "This chat does not have a bound Codex session yet.\n"
            "Use /newsession to create one now, or send /codex and the bridge will create one automatically."
        )
    sandbox = entry.get("sandbox") or codex_default_sandbox()
    codex_session_id = entry.get("codex_session_id") or "<pending first Codex run>"
    return (
        f"Current Codex session: {entry.get('label', '<unnamed>')} [{entry.get('session_key', '?')}]\n"
        f"codex_session_id={codex_session_id}\n"
        f"sandbox={sandbox}\n"
        f"created_at={entry.get('created_at', '<unknown>')}\n"
        f"last_used_at={entry.get('last_used_at') or '<never>'}\n"
        f"messages={entry.get('message_count', 0)}"
    )


def list_sessions_text(state: dict, chat_id: str) -> str:
    chat_state = codex_chat_state(state, chat_id)
    ordered = ordered_session_keys(chat_state)
    if not ordered:
        return "No saved Codex sessions for this chat yet."

    current_key = current_session_key(chat_state)
    lines = ["Saved Codex sessions for this chat:"]
    for index, session_key in enumerate(ordered, start=1):
        entry = get_session_entry(chat_state, session_key)
        if not entry:
            continue
        lines.append(format_session_entry(entry, index=index, is_current=session_key == current_key))
    return "\n".join(lines)


def active_task_message(state: dict) -> str:
    pid = state.get("active_pid")
    if pid and is_pid_running(pid):
        return f"A task is already running with PID {pid}. Use /status or /stop first."
    return ""


def start_task(
    state: dict,
    chat_id: str,
    task: str,
    *,
    dry_run: bool = False,
    resume_id: str = "",
    engine: str = "turix",
    sandbox: str = "",
) -> str:
    conflict = active_task_message(state)
    if conflict:
        return conflict

    ensure_runtime_dirs()
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    mode = "dryrun" if dry_run else "resume" if resume_id else "run"
    reply_path = None
    session_key = ""
    codex_session_id = ""

    if engine == "codex":
        session_entry = ensure_current_chat_session(state, chat_id, sandbox=sandbox or codex_default_sandbox())
        session_entry["sandbox"] = sandbox or codex_default_sandbox()
        session_key = session_entry["session_key"]
        codex_session_id = str(session_entry.get("codex_session_id", "")).strip()
        mode = "codex"
        if session_entry["sandbox"] == "workspace-write":
            mode = "codexw"
        reply_path = LOG_DIR / f"{timestamp}-{mode}-reply.txt"
        command = build_codex_command(
            task,
            output_path=reply_path,
            sandbox=session_entry["sandbox"],
            resume_session_id=codex_session_id,
        )
        exec_cwd = str(codex_workdir_path())
    else:
        command = build_run_command(task, dry_run=dry_run, resume_id=resume_id)
        exec_cwd = str(workdir_path())

    log_path = LOG_DIR / f"{timestamp}-{mode}.log"
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=exec_cwd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )

    if engine == "codex":
        chat_state = codex_chat_state(state, chat_id)
        session_entry = get_session_entry(chat_state, session_key)
        if session_entry:
            session_entry["last_used_at"] = now_text()
            session_entry["last_log_path"] = str(log_path)
            session_entry["last_reply_path"] = str(reply_path) if reply_path else ""
            session_entry["last_prompt"] = task

    state.update(
        {
            "active_pid": process.pid,
            "active_chat_id": chat_id,
            "active_log_path": str(log_path),
            "active_task": task,
            "active_mode": mode,
            "active_engine": engine,
            "active_reply_path": str(reply_path) if reply_path else None,
            "active_sandbox": sandbox or None,
            "active_resume_id": resume_id,
            "active_session_key": session_key or None,
            "active_codex_session_id": codex_session_id or None,
            "last_started_at": now_text(),
            "completion_notified": False,
            "last_exit_code": None,
        }
    )
    save_state(state)

    if engine == "codex":
        session_entry = ensure_current_chat_session(state, chat_id, sandbox=sandbox or codex_default_sandbox())
        action = "Continuing" if codex_session_id else "Starting"
        return (
            f"{action} Codex session {session_entry.get('label', '<unnamed>')} "
            f"[{session_entry.get('session_key', '?')}] in {session_entry.get('sandbox', codex_default_sandbox())} mode."
        )
    if dry_run:
        return "Started TuriX dry run."
    if resume_id:
        return "Started TuriX resume task."
    return "Switched to TuriX mode and started the task."


def format_status(state: dict) -> str:
    pid = state.get("active_pid")
    if pid and is_pid_running(pid):
        lines = [
            "Task is running.",
            f"PID: {pid}",
            f"Engine: {state.get('active_engine', 'turix')}",
            f"Mode: {state.get('active_mode', 'run')}",
            f"Task: {state.get('active_task') or '<resume>'}",
            f"Log: {state.get('active_log_path')}",
        ]
        session_key = state.get("active_session_key")
        if session_key:
            lines.append(f"Session: {session_key}")
        return "\n".join(lines)
    return (
        "No active task.\n"
        f"Last exit code: {state.get('last_exit_code')}\n"
        f"Last log: {state.get('active_log_path') or '<none>'}"
    )


def update_session_after_completion(state: dict) -> None:
    if state.get("active_engine") != "codex":
        return

    chat_id = str(state.get("active_chat_id") or "")
    session_key = str(state.get("active_session_key") or "")
    if not chat_id or not session_key:
        return

    chat_state = codex_chat_state(state, chat_id)
    entry = get_session_entry(chat_state, session_key)
    if not entry:
        return

    log_path_raw = state.get("active_log_path")
    reply_path_raw = state.get("active_reply_path")
    if log_path_raw:
        log_path = Path(str(log_path_raw))
        entry["last_log_path"] = str(log_path)
        parsed_session_id = extract_session_id(log_path)
        if parsed_session_id:
            entry["codex_session_id"] = parsed_session_id
            state["active_codex_session_id"] = parsed_session_id
    if reply_path_raw:
        entry["last_reply_path"] = str(reply_path_raw)
    entry["last_used_at"] = now_text()
    entry["message_count"] = int(entry.get("message_count", 0)) + 1
    save_state(state)


def maybe_notify_completion(state: dict) -> None:
    pid = state.get("active_pid")
    chat_id = state.get("active_chat_id")
    engine = state.get("active_engine", "turix")
    if not pid or not chat_id:
        return
    if is_pid_running(pid):
        return
    if state.get("completion_notified"):
        return

    update_session_after_completion(state)

    if engine == "codex":
        reply_path = state.get("active_reply_path")
        reply_text = ""
        if reply_path and Path(str(reply_path)).exists():
            reply_text = Path(str(reply_path)).read_text(encoding="utf-8", errors="replace").strip()
        message = reply_text or "Codex finished, but no displayable final message was captured. Use /logs for details."
    else:
        message = "TuriX task finished. Use /status or /logs if you want details."

    try:
        send_message(chat_id, message)
    finally:
        state["completion_notified"] = True
        state["last_exit_code"] = "finished"
        state["active_pid"] = None
        save_state(state)


def handle_update(state: dict, update: dict) -> None:
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    if not chat_id:
        return

    allowlist = allowed_chat_ids()
    if allowlist and chat_id not in allowlist:
        send_message(chat_id, f"Chat {chat_id} is not allowed.")
        return

    text = message.get("text", "") or ""
    command, arg = parse_command(text)
    if not command:
        return

    if command in {"start", "help"}:
        send_message(chat_id, render_help())
        return
    if command == "chatid":
        send_message(chat_id, f"Current chat id: {chat_id}")
        return
    if command == "mode":
        send_message(chat_id, describe_chat_mode(state, chat_id))
        return
    if command == "session":
        send_message(chat_id, describe_current_session(state, chat_id))
        return
    if command == "sessions":
        send_message(chat_id, list_sessions_text(state, chat_id))
        return
    if command == "newsession":
        sandbox = get_chat_mode(state, chat_id).get("sandbox") or codex_default_sandbox()
        entry = create_chat_session(state, chat_id, label=arg, sandbox=sandbox)
        send_message(
            chat_id,
            (
                f"Created a new Codex session slot: {entry.get('label', '<unnamed>')} "
                f"[{entry.get('session_key', '?')}]. Send /codex or plain text in Codex mode to start using it."
            ),
        )
        return
    if command == "switchsession":
        if not arg:
            send_message(chat_id, "Usage: /switchsession <ref>")
            return
        entry = switch_chat_session(state, chat_id, arg)
        if not entry:
            send_message(chat_id, f"Session not found: {arg}")
            return
        send_message(chat_id, f"Switched to Codex session slot {entry.get('label', '<unnamed>')} [{entry.get('session_key', '?')}].")
        return
    if command == "renamesession":
        if not arg:
            send_message(chat_id, "Usage: /renamesession <label>")
            return
        entry = rename_current_chat_session(state, chat_id, arg)
        if not entry:
            send_message(chat_id, "This chat does not have a current Codex session slot yet.")
            return
        send_message(chat_id, f"Renamed current Codex session slot to {entry.get('label', '<unnamed>')}.")
        return
    if command == "dropsession":
        if not arg:
            send_message(chat_id, "Usage: /dropsession <ref>")
            return
        entry, was_current = drop_chat_session(state, chat_id, arg)
        if not entry:
            send_message(chat_id, f"Session not found: {arg}")
            return
        suffix = " Current session switched to the latest remaining slot." if was_current else ""
        send_message(chat_id, f"Forgot Codex session slot {entry.get('label', '<unnamed>')} [{entry.get('session_key', '?')}] from bridge state.{suffix}")
        return
    if command == "status":
        send_message(chat_id, format_status(state))
        return
    if command == "logs":
        log_path = state.get("active_log_path")
        count = 20
        if arg:
            try:
                count = min(max(int(arg), 1), 100)
            except ValueError:
                count = 20
        if not log_path:
            send_message(chat_id, "No log file recorded yet.")
            return
        send_message(chat_id, tail_lines(Path(str(log_path)), count))
        return
    if command == "stop":
        pid = state.get("active_pid")
        if not pid or not is_pid_running(pid):
            state["active_pid"] = None
            save_state(state)
            send_message(chat_id, "No active process to stop.")
            return
        ok, output = stop_pid_tree(pid)
        state["active_pid"] = None
        state["completion_notified"] = True
        state["last_exit_code"] = "stopped"
        save_state(state)
        status = "Stopped current process." if ok else "Failed to stop current process."
        send_message(chat_id, f"{status}\n{output}".strip())
        return
    if command == "resume":
        if not arg:
            send_message(chat_id, "Usage: /resume <agent_id>")
            return
        set_chat_mode(state, chat_id, engine="turix")
        send_message(chat_id, start_task(state, chat_id, "", resume_id=arg))
        return
    if command == "dryrun":
        if not arg:
            send_message(chat_id, "Usage: /dryrun <task>")
            return
        set_chat_mode(state, chat_id, engine="turix")
        send_message(chat_id, start_task(state, chat_id, arg, dry_run=True))
        return
    if command in {"run", "turix"}:
        set_chat_mode(state, chat_id, engine="turix")
        if not arg:
            send_message(chat_id, "Switched plain-text mode to TuriX.")
            return
        send_message(chat_id, start_task(state, chat_id, arg))
        return
    if command == "codex":
        sandbox = codex_default_sandbox()
        set_chat_mode(state, chat_id, engine="codex", sandbox=sandbox)
        ensure_current_chat_session(state, chat_id, sandbox=sandbox)
        if not arg:
            send_message(chat_id, f"Switched plain-text mode to Codex ({sandbox}).")
            return
        send_message(chat_id, start_task(state, chat_id, arg, engine="codex", sandbox=sandbox))
        return
    if command == "codexw":
        sandbox = "workspace-write"
        set_chat_mode(state, chat_id, engine="codex", sandbox=sandbox)
        ensure_current_chat_session(state, chat_id, sandbox=sandbox)
        if not arg:
            send_message(chat_id, "Switched plain-text mode to Codex (workspace-write).")
            return
        send_message(chat_id, start_task(state, chat_id, arg, engine="codex", sandbox=sandbox))
        return
    if command == "plain":
        mode = get_chat_mode(state, chat_id)
        if mode.get("engine") == "codex":
            sandbox = mode.get("sandbox") or codex_default_sandbox()
            ensure_current_chat_session(state, chat_id, sandbox=sandbox)
            send_message(chat_id, start_task(state, chat_id, arg, engine="codex", sandbox=sandbox))
            return
        send_message(chat_id, start_task(state, chat_id, arg))
        return

    send_message(chat_id, render_help())


def main() -> int:
    ensure_runtime_dirs()
    if "--check" in sys.argv:
        ok, message = preflight()
        print(message)
        return 0 if ok else 1

    ok, message = preflight()
    if not ok:
        print(message, file=sys.stderr)
        return 1

    state = load_state()
    offset = state.get("last_update_id")
    print("Telegram bridge started.")

    while True:
        maybe_notify_completion(state)
        try:
            updates = get_updates(offset)
        except urllib.error.URLError as exc:
            print(f"telegram polling error: {exc}", file=sys.stderr)
            time.sleep(5)
            continue
        except Exception as exc:
            print(f"bridge error: {exc}", file=sys.stderr)
            time.sleep(5)
            continue

        for update in updates:
            update_id = update.get("update_id")
            if update_id is not None:
                offset = int(update_id) + 1
                state["last_update_id"] = offset
                save_state(state)
            try:
                handle_update(state, update)
            except Exception as exc:
                chat_id = update.get("message", {}).get("chat", {}).get("id")
                if chat_id:
                    try:
                        send_message(chat_id, f"Command failed: {exc}")
                    except Exception:
                        pass


if __name__ == "__main__":
    sys.exit(main())
