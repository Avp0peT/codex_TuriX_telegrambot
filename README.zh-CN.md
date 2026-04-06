# codex_TuriX_telegrambot

这是一个面向 Windows 的 Telegram 桥接 skill，可以让你通过 Telegram 机器人与本地 Codex 和本地 TuriX 交互。

[English README](./README.md)

## 项目简介

这个仓库包含一个公开可发布、已脱敏的本地 Codex skill，名字叫 `telegram-turix-bridge`。

它适合这些场景：
- 在 Telegram 里和本地 Codex 对话
- 在 Telegram 里触发本地 TuriX 桌面自动化
- 在同一个机器人聊天里在 Codex 和 TuriX 之间切换
- 把 token、chat id、日志、运行状态保留在本地，不上传到仓库

这个桥接器运行在本地 Windows 上，使用 Telegram 长轮询，不依赖独立服务器。

## 功能特性

- 通过 `codex exec` 把 Telegram 消息转给本地 Codex
- 通过本地 `run_turix.ps1` 把 Telegram 消息转给 TuriX
- 按聊天记住当前模式
  发过 `/codex` 后，后续普通文本默认继续走 Codex
  发过 `/codexw` 后，后续普通文本默认继续走 Codex 写入模式
  发过 `/run` 或 `/turix` 后，普通文本切回 TuriX
- 默认对话输出更干净
  正常聊天只显示正常回复
  调试信息通过 `/status` 和 `/logs` 单独查看
- 公开仓库可安全发布
  不包含 token、chat id、运行日志、运行状态和个人机器信息

## 仓库结构

```text
telegram-turix-bridge/
  SKILL.md
  agents/openai.yaml
  scripts/
    launch_bot.ps1
    telegram_turix_bridge.py
```

## 仓库中包含的内容

- 一个可被 Codex 自动发现的 skill 目录 `telegram-turix-bridge/`
- 一个基于 Python 标准库实现的 Telegram bridge
- 一个适用于 Windows 的 PowerShell 启动脚本
- 面向公开使用的安装与配置说明

## 仓库中刻意不包含的内容

- Telegram bot token
- 允许访问的 chat id
- 运行日志
- 本地状态文件
- 个人机器路径
- 私有部署细节

## 安装方式

把 skill 复制到本地 Codex skills 目录：

```powershell
Copy-Item -Recurse -Force .\telegram-turix-bridge "$HOME\.codex\skills\telegram-turix-bridge"
```

如果你还希望支持 TuriX，请先准备好本地 `turix-cua` skill，并确认它的 `run_turix.ps1` 存在。

## 必填环境变量

```powershell
$env:TELEGRAM_BOT_TOKEN = "123456:bot-token"
```

## 推荐环境变量

```powershell
$env:TELEGRAM_ALLOWED_CHAT_ID = "123456789"
$env:TURIX_RUNNER = "$HOME\.codex\skills\turix-cua\scripts\run_turix.ps1"
$env:TURIX_WORKDIR = "D:\work"
$env:CODEX_WORKDIR = "D:\work"
```

## 可选环境变量

```powershell
$env:CODEX_CLI = "codex"
$env:CODEX_SANDBOX = "read-only"
$env:TELEGRAM_BRIDGE_PYTHON = "python"
$env:TELEGRAM_POLL_TIMEOUT = "30"
```

## 启动方式

先做预检查：

```powershell
powershell -ExecutionPolicy Bypass -File .\telegram-turix-bridge\scripts\launch_bot.ps1 -Check
```

再启动 bridge：

```powershell
powershell -ExecutionPolicy Bypass -File .\telegram-turix-bridge\scripts\launch_bot.ps1
```

## Telegram 支持的命令

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

## 常见使用方式

先切到 Codex 对话模式：

```text
/codex 解释一下当前项目结构
再用中文总结一下
```

再切回 TuriX：

```text
/turix 打开 Edge 并访问 github.com
```

需要调试时再看状态：

```text
/status
/logs 30
```

## 安全建议

- 不要把 `TELEGRAM_BOT_TOKEN` 提交到仓库
- 尽量使用私聊 bot，或严格设置 `TELEGRAM_ALLOWED_CHAT_ID`
- 默认把 `/codex` 保持在 `read-only`
- 只有在可信私聊中才使用 `/codexw`
- 不要提交 `runtime/`、日志或状态文件

## License

当前仓库还没有单独的许可证文件；如果你准备长期公开分发，建议后续补上。
