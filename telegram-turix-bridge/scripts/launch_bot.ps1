param(
    [switch]$Check
)

$ErrorActionPreference = "Stop"

$BotScript = Join-Path $PSScriptRoot "telegram_turix_bridge.py"

function Resolve-PythonCommand {
    if ($env:TELEGRAM_BRIDGE_PYTHON) {
        $cmd = Get-Command $env:TELEGRAM_BRIDGE_PYTHON -ErrorAction SilentlyContinue
        if ($cmd) {
            return @($cmd.Source)
        }
        if (Test-Path -LiteralPath $env:TELEGRAM_BRIDGE_PYTHON) {
            return @($env:TELEGRAM_BRIDGE_PYTHON)
        }
        throw "TELEGRAM_BRIDGE_PYTHON does not point to a valid Python executable."
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return @($pythonCmd.Source)
    }

    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        return @($pyCmd.Source, "-3")
    }

    throw "No usable Python executable found. Set TELEGRAM_BRIDGE_PYTHON first."
}

function Ensure-DefaultEnv {
    if (-not $env:TURIX_RUNNER) {
        $env:TURIX_RUNNER = Join-Path $HOME ".codex\skills\turix-cua\scripts\run_turix.ps1"
    }
    if (-not $env:TURIX_WORKDIR) {
        $env:TURIX_WORKDIR = (Get-Location).Path
    }
    if (-not $env:CODEX_WORKDIR) {
        $env:CODEX_WORKDIR = $env:TURIX_WORKDIR
    }
    if (-not $env:CODEX_CLI) {
        $env:CODEX_CLI = "codex"
    }
}

Ensure-DefaultEnv

if (-not $env:TELEGRAM_BOT_TOKEN) {
    throw "Set TELEGRAM_BOT_TOKEN before launching the Telegram bridge."
}

$pythonCommand = @(Resolve-PythonCommand)
$args = @($BotScript)

if ($Check) {
    $args += "--check"
}

if ($pythonCommand.Count -gt 1) {
    & $pythonCommand[0] @($pythonCommand[1..($pythonCommand.Count - 1)] + $args)
}
else {
    & $pythonCommand[0] @args
}
