# Fresh global-alert messages

`hoi4_notification_message(request_id, native_alert_kind)` generates one supported
alert's title/body on the game thread while paused. It reuses the existing callback
and durable time-request ledger. No keyboard, mouse, screenshots or gameplay-field
setters are used; native getter invocation updates its UI cache. The passive popup
snapshot remains read-only, with cache freshness unverified.

## Use and scope

Prepare a fresh protected session, install the native selection and updated time
backends, arm it and pause through the existing native time command. Read
`native_popup.native_alert_kind` from the popup snapshot, then pass that kind and a
new 32-character lowercase hex ID to `hoi4_notification_message`.

Poll with the same ID until `stage` is `alert_refreshed` or `rejected`. An intermediate
`execution_uncertain` receipt can precede completion: retain its ID and inspect
native status/errors if it persists. Never replace an uncertain execution's ID.
Completed `raw_title`, `raw_body`, `native_tick` and `generated_unix_ms` describe output
at engine generation. Formatting codes are retained; repeat IDs return the original
receipt without rebuilding text. Use a new ID for a new observation after completion.

Freshness is at the generation tick, not later game state or future turns. A tick
change during generation is rejected. Supported kinds are the pinned build's native
0–81 enum; only an unambiguous engine-local shown global-alert owner is eligible.
Running, hidden, ambiguous, oversized and unsupported results are rejected. The
existing per-process request limit applies. Other owners, option IDs, physical
visibility and complete tooltip formatting remain unresolved.

## Validation on 14 October 2026

20 affected offline tests passed on Mac, including compiled C serialization and pause
fixtures with simulated memory/callbacks. Nine affected Python tests passed on
Windows. Real MCP checks passed for research/factory generation, running/hidden
rejection, pause, generation timestamps, unchanged tick, duplicate receipt identity
and no input. The research message included four idle slots, absent from its earlier
passive cache. The first supervisor stopped on an intermediate receipt; the same IDs
were reconciled without repeating the action. The final tick-consistency binary was
verified in a separate fresh protected process.

Both owned campaigns were closed, original autosave bytes/timestamp and targeted
save-format/mod settings restored, other settings updates preserved, and request IDs
retained. See [sanitized results](FRESH_NOTIFICATION_VALIDATION_20261014.json).

## Build and lean measurement

Built with the existing Zig 0.14.1 toolchain:

```sh
zig cc -target x86_64-windows-gnu -fms-extensions -shared native_time.c -o hoi4-native-time.dll -lbcrypt
```

Tested DLL SHA256: `42dc6c4430a6e20effdcee4701d8ab6c952642d213bc4f06c72026ec0e866653`.
Installers import this pin from `time_controller.py`; old saved test sessions must not
resume with a changed backend. Preserve their ledgers and prepare a new bound process.
A locally rebuilt DLL needs its own validation and pin.

Runtime scope: 6,182 → 6,250 lines (+68). Tests: 2,562 → 2,635 (+73).
The 55-line helper reuses the existing callback, arming and receipt channel. There is
no size reduction, additional DLL or new dependency. The replaced time DLL is
577,536 bytes (previously 179,712).
