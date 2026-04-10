# codex_TuriX_telegrambot

这是一个面向 Windows 本地运行的 Telegram bridge skill，用来通过 Telegram 机器人和本地 Codex、TuriX 交互。

[English README](./README.md)

## 项目简介

这个仓库包含 `telegram-turix-bridge` skill 的公开脱敏版本。

它适合这些场景：

- 在 Telegram 里和本地 Codex 持续对话
- 在 Telegram 里触发本地 TuriX 桌面自动化
- 在同一个 bot 聊天中在 Codex 和 TuriX 之间切换
- 把 token、chat id、日志和运行状态保留在本地，不上传到仓库

这个 bridge 运行在本地 Windows 上，使用 Telegram long polling，不依赖单独的后端服务。

## 主要能力

- 通过 `codex exec` 把 Telegram 消息转给本地 Codex
- 通过本地 `run_turix.ps1` 把 Telegram 消息转给 TuriX
- 按 chat 持久保存 Codex 会话
- 支持线程风格别名命令：`/thread`、`/threads`、`/newthread`、`/switchthread`
- 提供会话管理命令：新建、查看、切换、重命名、删除
- Telegram 网络瞬时异常时自动重试，并对未送达消息进行补发
- 按 chat 记住当前模式
- 默认对话输出保持干净，调试信息通过 `/status` 和 `/logs` 查看
- 公开仓库不包含 token、chat id、运行日志和状态文件

## 仓库结构

```text
telegram-turix-bridge/
  SKILL.md
  agents/openai.yaml
  scripts/
    launch_bot.ps1
    telegram_turix_bridge.py
```

## 不包含的内容

- Telegram bot token
- 允许访问的 chat id
- 运行日志
- 状态文件
- 个人机器路径
- 私有部署细节

## 安装方式

把 skill 复制到本地 Codex skills 目录：

```powershell
Copy-Item -Recurse -Force .\telegram-turix-bridge "$HOME\.codex\skills\telegram-turix-bridge"
```

如果还要支持 TuriX，请先准备好本地 `turix-cua` skill，并确保它的 `run_turix.ps1` 存在。

## 必需环境变量

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

先执行预检查：

```powershell
powershell -ExecutionPolicy Bypass -File .\telegram-turix-bridge\scripts\launch_bot.ps1 -Check
```

再启动 bridge：

```powershell
powershell -ExecutionPolicy Bypass -File .\telegram-turix-bridge\scripts\launch_bot.ps1
```

## Telegram 命令

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

## 持续会话如何工作

- 每个 Telegram chat 都有自己的一组 Codex 会话槽位。
- 第一次发送 `/codex` 时，会为当前 chat 启动一个新的 Codex 会话。
- 之后在 Codex 模式下发送普通文本，会通过 `codex exec resume <session-id>` 继续同一个上下文。
- `/newsession` 会创建一个新的会话槽位，但不会删除旧会话。
- `/switchsession` 可以按序号、bridge 会话 id、标签名或 Codex session id 切回旧会话。
- `/thread` 这一组命令只是对同一套会话槽位的更直观别名。

## 网络稳定性

- Telegram API 调用在瞬时 SSL 或连接失败时会自动重试。
- 如果回复暂时发不出去，会先写入本地状态，后续循环恢复网络后自动补发。
- 临时的 Telegram 网络波动不应该再直接把整个 bridge 打死。

## 典型用法

开始一个持续 Codex 对话：

```text
/codex 解释一下当前项目结构
再用中文总结一遍
接下来最值得优先处理的风险是什么
```

按“线程”方式切换上下文：

```text
/newthread 发布说明
/codex 为最新的 bridge 改动起草一份发布说明
/threads
/switchthread 1
```

切换到 TuriX：

```text
/turix 打开 Edge 并访问 github.com
```

需要时再查看调试信息：

```text
/status
/logs 30
```

## 安全建议

- 不要把 `TELEGRAM_BOT_TOKEN` 提交到仓库
- 尽量使用私聊 bot，或严格设置 `TELEGRAM_ALLOWED_CHAT_ID`
- 默认把 `/codex` 保持在 `read-only`
- 只在可信私聊里使用 `/codexw`
- 不要提交 `runtime/`、日志或状态文件

## License

当前仓库还没有单独的许可证文件；如果准备长期公开分发，建议补充。
