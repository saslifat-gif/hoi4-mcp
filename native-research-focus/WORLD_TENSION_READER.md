# World-tension panel without input

`hoi4_world_tension_window(request_id, shown)` opens or closes the panel through its
ordinary native UI handler on the game thread. It requires a paused, armed, bound
Germany test session and the updated time backend. This changes UI state, not
through keyboard/mouse input or direct gameplay-field setters. Native UI writes are
explicit. Use a new 32-hex ID for each new intent; repeat an existing ID only to
reconcile it. The existing process request budget applies.

Read `hoi4_popup_snapshot(kind="world_tension")` after opening. Its title comes from
the installed `window_name` widget, with deeper row traversal than the former
three-level scan. A pinned `CWorldTensionPopUpWindow` ownership chain adds
`native_popup.status: native_window_state`, native local show state and explicit
physical-visibility limits. Passive snapshots perform no callback, memory write or
input and need no arming. Complete row/child coverage, current tooltip-buffer
freshness and physical screen visibility are still not guaranteed.

## Close fade and durable receipts

The installed panel has a 200 ms close fade. Its immediate native callback can
return `execution_uncertain` / `window_state_unverified` while the local shown flag
is still set. Keep its ID and repeat `hoi4_world_tension_window` with the same payload.
That request is not applied again. The reader checks the pinned current owner and
records `window_observed` once its state matches the intent. This describes a later
read-only state observation, not a replacement native receipt or causal proof.

The original native receipt stays intact. The separate observation records its
capture time and widget binding, then remains immutable on further reads. Observation
writes use the existing request transaction; ambiguous/truncated reads and changed
bindings do not complete uncertain intent. Repeating a completed open ID after closing
returns its old receipt and does not reopen the panel. Read a new snapshot for current
state. `hoi4_time_receipt` can read an existing observation; first-time fade
reconciliation uses the window tool with the original ID.

## Verification on 14 October 2026

215 affected offline tests passed on Mac and 214 Python tests passed on Windows.
Mac also compiled/executed the C window-state fixture under address/undefined-behavior
sanitizers; its fake callbacks test idempotency, failed changes/bindings and failure
stage mapping. Neither simulated memory nor these counts prove complete UI coverage.

A fresh protected Germany process passed 14 actual MCP checks: running rejection,
native opening, pinned owner/show-state binding, title matching installed English or
Simplified Chinese localization, controls and empty-state message text, closing,
immutable duplicate/observation receipts, preserved native evidence, unchanged
paused clock and read-only snapshot output. Seven text fields were read. Nonempty
tension/war row content, other notification-owner messages and complete tooltip
formatting remain pending. See [sanitized results](WORLD_TENSION_VALIDATION_20261014.json).

An earlier live run exposed the fade behavior. Its owned 15-minute safety task
terminated that process before final reconciliation; its close ID/uncertain native
receipt remain private and unresolved, never replaced or replayed. Its original
profile was restored before preparing the final fresh process. Both campaigns are
now stopped/recovered, their tasks removed, original autosave bytes/timestamp and
targeted save-format/mod selection restored, unrelated settings updates preserved.
No private ABI report, save, request ledger or installed-game code is published.

## Build and lean measurement

The existing time DLL was replaced, with no added DLL or dependency. The existing
Zig 0.14.1 toolchain builds it using the same command:

```sh
zig cc -target x86_64-windows-gnu -fms-extensions -shared native_time.c -o hoi4-native-time.dll -lbcrypt
```

Tested SHA256: `22d2ecba6394a5b0dedc1f437ad41ea812852d0a5eaead3d1829543cdb70d8c5`.
The installer imports this pin from `time_controller.py`. Preserve exited/older
session ledgers and prepare a fresh process rather than changing their backend.

Runtime: 6,266 -> 6,330 lines (+64). Tests: 2,667 -> 2,743 (+76).
DLL: 577,536 -> 582,144 bytes (+4,608). There is no size reduction this round.
The game-thread hook, request ledger, snapshot guards and string reader were reused.
