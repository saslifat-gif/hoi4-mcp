# Economy and supported-choice reader — 2026-10-12

The installed MCP server adds `hoi4_peacetime_snapshot(request_id)` for political power, factories, fuel, strategic resources and available choices for research, national focuses, construction and production.

## Read contract

Use a new 32-character lowercase hexadecimal request ID for a fresh read. Repeat that same ID to poll its result. The game must advance for the daily callback. Pending or incomplete frames do not return fabricated values. Completed samples are immutable, explicitly dated snapshots; another ID is needed for newer state. Commands always revalidate when executed.

The economy sampler reads the installed engine's documented dynamic variables. It reports political power and daily change; total and available civilian/military factories and dockyards; fuel in thousands; and produced, consumed, imported, exported and surplus quantities for every installed resource definition. This version includes coal as well as oil, aluminium, rubber, tungsten, steel and chromium. Surplus can be negative. Consumption is the engine's reported consumption, not an inferred demand; a shortage can exist even when reported consumption is zero.

Construction states come from the engine's actual owned-state array. Its tagged scope references are decoded into state IDs, and enumeration must match the engine's owned-state count. Choices are limited to supported IDs/types and one level per request. `max_levels=1` is the supported request limit, not an estimate of all remaining slots. The engine eligibility check includes already queued construction; its generic free-slot quantity does not. Additional levels require fresh, separate requests. Dockyards additionally require the documented coastal predicate.

Research and focus choices use the pinned native validators on the previously verified game thread. Research availability additionally respects empty slots and the existing backend's template guard. An active national focus blocks replacement. The native module never invokes command execution, grants technologies or spends political power.

Construction and production choices pass the same engine guards used by the existing supported commands. Production retains the conservative installed-base equipment allowlist; active mod/DLC equipment overlays and complete normal-player equivalence remain unverified. These are guard-approved choices, not a promise that an action's outcome needs no read-back.

Economy log frames and native choice files share the session, immutable request ID, process/world binding and a single script callback. A frame must contain BEGIN, all scalar/resource rows, complete state enumeration and END. Native validation failure, changed bindings, altered source hashes, mixed dates, duplicates and invalid values cause explicit errors. Frame markers are protocol markers; the native sample clock comes from the native validator file. No script `date` value is misrepresented as game time.

## Live verification

The real MCP stdio server returned a committed sample dated 1937.08.29.24 from the protected Germany campaign:

- Political power 1358.344, daily change 2.324.
- Civilian factories 37 total / 15 available; military factories 28 / 8; dockyards 10 / 4.
- Seven strategic resources, including a rubber shortage of 5.
- 65 available research choices, 7 focuses, 57 construction choices and 9 production choices.
- Completed Infantry Weapons was excluded from research. Basic Machine Tools and Prioritize Economic Growth were available. Berlin allowed arms-factory construction and did not offer inland dockyards.
- Repeating the same request returned the identical immutable sample.

No screenshots, keyboard/mouse input or gameplay choices were executed by this validation. Installing the native observer requires process-memory hook writes; its validators and scripted reads do not directly write gameplay fields. Protocol metadata flags and temporary script variables support correlation/idempotency.

Twenty-three new simulated-frame regression tests passed on Mac and Windows. These cover malformed and partial frames, tagged state IDs, non-finite values, source binding, slot guards and supported factory limits. Existing research/controller/command and transport checks are separate from the live game result.

## Installation and scope

After the existing fresh-session preparation, game launch, binding and native backend installation, run `install_peacetime_reader.py --session-file <bound-session.json>` with the Windows venv Python. It verifies the shipped variable documentation and source hashes, then attaches the exact pinned observer module. The existing `run-native-mcp.cmd` entry exposes the new read tool. This does not register a new server in Codex automatically.

This remains an experimental, executable-pinned Germany single-player test interface. Laws, advisors, decisions and trade were explicitly excluded from this task's available-choice scope. Pause/speed commands and autonomous decision-making remain separate work.

The owned test process was stopped after validation. The original autosave bytes and timestamp were restored and verified, the temporary mod was deactivated, and the expired process binding was rejected. User/game settings were preserved.
