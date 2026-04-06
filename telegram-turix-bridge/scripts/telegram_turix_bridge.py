import json
import os
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


def ensure_runtime_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else default


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
    candidates = [raw]
    if raw.lower() == "codex":
        candidates.extend(["codex.cmd", "codex.exe"])
    for candidate in candidates:
        if Path(candidate).exists():
            return str(Path(candidate))
        found = shutil.which(candidate)
        if found:
            return found
    return None


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


def build_codex_command(prompt: str, *, output_path: Path, sandbox: str) -> list[str]:
    cli = codex_cli_resolved() or codex_cli()
    return [
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
        prompt,
    ]


def render_help() -> str:
    return (
        "Telegram TuriX Bridge commands:\n"
        "/chatid - show current chat id\n"
        "/mode - show the current plain-text mode\n"
        "/codex <prompt> - ask Codex in read-only mode\n"
        "/codexw <prompt> - ask Codex with workspace-write sandbox\n"
        "/run <task> - start a TuriX task\n"
        "/turix <task> - switch plain text back to TuriX\n"
        "/dryrun <task> - validate the TuriX launch command\n"
        "/resume <agent_id> - resume a TuriX task\n"
        "/status - show active process details\n"
        "/logs [N] - show recent log lines\n"
        "/stop - stop the active process\n"
        "Plain text follows the current chat mode."
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
        issues.append(f"missing TuriX workdir: {workdir}")
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
    active_pid = state.get("active_pid")
    if is_pid_running(active_pid):
        return "Another task is already running. Use /status or /stop first."

    ensure_runtime_dirs()
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    mode = "dryrun" if dry_run else "resume" if resume_id else "run"
    reply_path = None

    if engine == "codex":
        mode = "codexw" if sandbox == "workspace-write" else "codex"
        reply_path = LOG_DIR / f"{timestamp}-{mode}-reply.txt"
        command = build_codex_command(task, output_path=reply_path, sandbox=sandbox or codex_default_sandbox())
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
            "last_started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "completion_notified": False,
            "last_exit_code": None,
        }
    )
    save_state(state)

    if engine == "codex":
        if sandbox == "workspace-write":
            return "Switched to Codex write mode. Working on it."
        return "Switched to Codex chat mode. Working on it."
    if dry_run:
        return "Started TuriX dry-run check."
    if resume_id:
        return "Started TuriX resume."
    return "Switched to TuriX mode. Task started."


def format_status(state: dict) -> str:
    pid = state.get("active_pid")
    if pid and is_pid_running(pid):
        return (
            "Task is running.\n"
            f"PID: {pid}\n"
            f"Engine: {state.get('active_engine', 'turix')}\n"
            f"Mode: {state.get('active_mode', 'run')}\n"
            f"Task: {state.get('active_task') or '<resume>'}\n"
            f"Log: {state.get('active_log_path')}"
        )
    return (
        "No active task.\n"
        f"Last exit code: {state.get('last_exit_code')}\n"
        f"Last log: {state.get('active_log_path') or '<none>'}"
    )


def maybe_notify_completion(state: dict) -> None:
    pid = state.get("active_pid")
    chat_id = state.get("active_chat_id")
    if not pid or not chat_id:
        return
    if is_pid_running(pid):
        return
    if state.get("completion_notified"):
        return

    engine = state.get("active_engine", "turix")
    if engine == "codex":
        reply_path = state.get("active_reply_path")
        reply_text = ""
        if reply_path and Path(reply_path).exists():
            reply_text = Path(reply_path).read_text(encoding="utf-8", errors="replace").strip()
        message = reply_text or "Codex finished, but no displayable reply was captured. Use /logs for details."
    else:
        message = "TuriX task finished. Use /status or /logs if you need details."

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
        send_message(chat_id, tail_lines(Path(log_path), count))
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
        if not arg:
            send_message(chat_id, "Usage: /run <task>")
            return
        set_chat_mode(state, chat_id, engine="turix")
        send_message(chat_id, start_task(state, chat_id, arg))
        return
    if command == "codex":
        if not arg:
            send_message(chat_id, "Usage: /codex <prompt>")
            return
        set_chat_mode(state, chat_id, engine="codex", sandbox=codex_default_sandbox())
        send_message(
            chat_id,
            start_task(state, chat_id, arg, engine="codex", sandbox=codex_default_sandbox()),
        )
        return
    if command == "codexw":
        if not arg:
            send_message(chat_id, "Usage: /codexw <prompt>")
            return
        set_chat_mode(state, chat_id, engine="codex", sandbox="workspace-write")
        send_message(
            chat_id,
            start_task(state, chat_id, arg, engine="codex", sandbox="workspace-write"),
        )
        return
    if command == "plain":
        mode = get_chat_mode(state, chat_id)
        if mode.get("engine") == "codex":
            reply = start_task(
                state,
                chat_id,
                arg,
                engine="codex",
                sandbox=mode.get("sandbox") or codex_default_sandbox(),
            )
        else:
            reply = start_task(state, chat_id, arg)
        send_message(chat_id, reply)
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
            except Exception:
                chat_id = (
                    update.get("message", {})
                    .get("chat", {})
                    .get("id")
                )
                if chat_id:
                    try:
                        send_message(chat_id, "Command failed. Use /status or /logs for details.")
                    except Exception:
                        pass


if __name__ == "__main__":
    sys.exit(main())
