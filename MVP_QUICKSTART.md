# Peacetime MVP v0.1.0

Windows, Python3.10+, AC power and the pinned HOI4 build in README are required.
Close the existing game and remain logged into your Windows desktop. Existing
settings.txt and save games/autosave.hoi4 are required by the recovery helper.

1. Extract the release ZIP into a new directory.
2. Create the Python environment and install requirements-mcp.txt as shown in README.
3. Run `powershell -ExecutionPolicy Bypass -File .\Start-Mvp.ps1 -Python .\.venv\Scripts\python.exe`.

Live validation on 14 October 2026 verified three research assignments and one
economic focus, followed by paused/disarmed exit and save/profile restoration.
See [validation](MVP_VALIDATION.json).

The temporary campaign starts automatically. The demo fills empty research slots
and selects the supported economic-growth focus, using normal engine rules and
readback. It performs at most four verified selections. Economic construction
and production commands are available through the separate MCP bridge; the
built-in AI does not plan those actions.

The launcher closes the campaign and restores the original profile after the run,
including on ordinary startup/test errors. Each session retains its report,
request ledgers, recovery copies and private test autosave. If the launcher is
force-killed or recovery fails, keep the session and run the existing recovery
command from README. Never replace an unresolved request with a new ID.

Military control, laws/advisors/trade/decisions, complete notification coverage
and continuation after loading a save are later work. The autonomous full
campaign test remains uncompleted.

## 简体中文

此 MVP 可自动启动德国临时战役，填充空闲研究槽并选择已支持的经济国策。
AI 最多验证四个操作，结束后暂停、解除授权、关闭临时游戏并恢复原配置。
建设和生产可通过 MCP 使用，但内置 AI 尚不自动规划这些操作。
请接通电源并保持 Windows 桌面登录；当前版本不支持战争 AI 或读档续跑。
发生错误时保留 sessions 中的记录和原请求 ID，按 README 执行恢复。
