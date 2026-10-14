# HOI4 MCP

Experimental game-side commands and structured observations for Hearts of Iron IV.
An AI can request supported actions through MCP without keyboard or mouse input.
This repository contains a generated-mod bridge, an external Python service and
source-built native Windows modules. It is not a standalone Steam Workshop mod
or a complete autonomous HOI4 player.

## Current scope

- Structured research progress/completion, focuses, resources, factories, fuel and political power.
- Read-only event/popup text, native event IDs, event-definition option indices/name keys, world-tension popup scanning and global-alert cached messages; see [reader scope and validation](native-research-focus/NATIVE_POPUP_READER.md).
- Ordinary research/focus selection, construction requests and new supported land-equipment production lines.
- Native pause/resume and game speed controls.
- Engine-generated global-alert messages while paused, with durable IDs and generation ticks; see [fresh reader](native-research-focus/FRESH_NOTIFICATION_READER.md).
- A bounded Germany research/focus policy with durable request IDs and readback.
- Experimental queued construction capacity and multi-level construction commands.

Research/focus selection, scripted construction/production, pause/speed and a
four-action AI loop were live-tested in earlier protected Germany campaigns.
Queued capacity and construction requests of one to five levels passed protected
live validation on 13 October 2026, including independent native-save comparison
and request-ledger retention. See [results](native-research-focus/QUEUED_CAPACITY_VALIDATION_20261013.md).
A five-minute sustained research/focus run also passed, including three research
completion/refill cycles. See [runner validation](native-research-focus/SUSTAINED_PEACETIME.md).
Offline tests do not prove compatibility with another game version or a full campaign.

Only Windows, an owned Germany single-player test campaign and executable SHA256
`7dc947be34970da1e1c787bcddbe7f62b610ff258aebf8f06aa8b348f3a031d5`
are supported. Other versions are rejected; changing that hash alone does not port
native addresses or command layouts. Military orders, diplomacy, event choices,
laws/advisors/trade and save/load continuation are not implemented.

## Install Python dependencies

Use Python 3.10 or newer. From the repository root on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-mcp.txt
$env:PYTHONPATH = "$PWD;$PWD\native-research-focus"
$py = "$PWD\.venv\Scripts\python.exe"
```

The four included DLLs are built from the native C sources in this repository.
Installers verify their exact hashes. No HOI4 executable, installed scripts,
localization, saves, decompiler output or private runtime credentials are included.
Native attachment loads these modules into the owned game process and hooks
verified native callbacks; it uses process-memory writes, but no input simulation
or direct setters for country/research/focus gameplay fields.
Use normal Python for the protected campaign workflow: some preparation and
recovery helpers still use assertions. The native loader now uses explicit errors
for its process, module, PE image and initialization checks. Use only a disposable
campaign and preserve your saves first.

## Prepare a protected campaign

Set paths to your own installed game and its user-data folder. Existing
`settings.txt` and `save games/autosave.hoi4` are required by this helper:

```powershell
& $py native-research-focus/prepare_queued_capacity_session.py --game-root 'C:\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV' --user-root "$HOME\Documents\Paradox Interactive\Hearts of Iron IV"
```

Keep the printed session directory. Launch a temporary Germany campaign with
its generated mod enabled and debug logging. No game is automatically launched
by preparation. Set `$session` to its `session.json`; after its matching READY
log entry appears, bind its actual new process ID:

```powershell
& $py bind_session.py --session-file $session --pid ACTUAL_GAME_PID
& $py direct_bridge.py --session-file $session --port 18768 --token-file .commands-token
```

The bridge binds only to loopback and starts disarmed. An MCP client launches
`direct_mcp_server.py --url http://127.0.0.1:18768 --token-file .commands-token`.
Its tools include `hoi4_status`, `hoi4_arm`, `hoi4_snapshot`, `hoi4_construct`,
`hoi4_produce`, `hoi4_receipt` and `hoi4_deliver`.

For native research/focus controls, install `native-research-focus/install_native_session.py`
with `--session-file $session`, wait for its matching native callback, then run
`native-research-focus/run-native-mcp.cmd --session-file $session` from your MCP client.
The experimental peacetime choices and time modules have separate installers;
install only after the bound native callback is ready. These are prototype tools,
not an automatic all-in-one launcher.

## Request and recovery contract

Use a unique 32-character lowercase hex request ID for each intended action.
Repeat the same ID after a timeout or uncertain receipt; do not invent a new ID.
A queued request is not proof of an executed action. A scripted ACK is not proof
of construction insertion or production output. Inspect the relevant state.
Ledger operations lock and reload shared state to preserve request IDs and receipts
across readers. A conflicting writer fails before publication; retain the same ID.
Busy research slots and active focuses are protected. Read snapshots are immutable
and dated; mutations revalidate eligibility when executed.

Always end the owned test game and restore its protected profile with
`native-research-focus/restore_queued_capacity_session.py SESSION_FILE`.
Recovery checks ownership, preserves the private test save, restores the original
autosave bytes/timestamp and original save-format setting, and removes only the
owned mod selection. Keep pending IDs and recovery files if recovery refuses.
The live queued-capacity driver additionally needs text autosaves and AC power.

## Offline checks

```powershell
$env:PYTHONPATH = "$PWD;$PWD\native-research-focus"
& $py -m unittest discover -s . -p 'test_*.py'
& $py -m unittest discover -s native-research-focus -p 'test_*.py'
```

Publication check on 13 October 2026: 173 offline checks passed on macOS, plus
2 MCP/HTTP transport checks under Python 3.13 (175 total). Windows game testing
was not performed during this publication.

These checks use fixtures, simulated Windows APIs and a real MCP/HTTP transport
with simulated engine logs. The pause adapter test also requires a local C compiler
with address/undefined sanitizers; it is intended for macOS/Linux development.
None of these tests starts HOI4. Live campaigns remain a separate validation gate.
See `native-research-focus/SUSTAINED_PEACETIME.md` for the bounded research/focus runner.

## 简体中文

这是实验性的 HOI4 游戏侧 MCP 接口，通过结构化命令与状态读取工作，不使用键盘鼠标。
项目包含模组生成器、外部 Python 服务及原生 Windows 模块，不能作为普通创意工坊模组单独运行。
目前只支持指定版本的德国单人临时测试战役；多级建设与持续 AI 尚待真实游戏验证。
请先备份存档，明确区分离线测试、游戏日志回执和真实游戏状态验证。
