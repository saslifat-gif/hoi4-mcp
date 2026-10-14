# Native event IDs and global-alert messages

`hoi4_popup_snapshot(kind="all")` now returns native IDs for supported event owners
and native cached title/body fields for supported global alerts. No screenshot,
input, native callback invocation, new DLL or process-memory write is needed by
these reads. The existing executable hash remains the compatibility boundary.

## Bindings and output

Event GUI roots must point to a pinned `CEventWindow` tooltip owner whose container
points back to the requested root. Its current-event pointer must identify a pinned
`CEvent`. The canonical ID comes from that object's string field, rather than a
localized title match. Returned `event_id_verified: true` means this native ownership
chain was verified. Option IDs/effects and enabled state remain unresolved.

Global-alert roots must bind back to a pinned `CGlobalAlertIcon`. The reader follows
the exact vector, record stride, native alert kind and context-key comparisons used
by the engine's tooltip lookup. A unique matching cache entry yields
`native_popup.status: native_cached_text` and `native_popup.fields.title/body`, each
with plain text, raw text and formatting runs. The numeric kind is the native enum
for this build; no icon frame is interpreted as an alert type.

Cache headers, context keys, owner bindings and text payloads are sampled and
rechecked. Missing/duplicate cache matches remain explicit; changed bindings fail
with the existing bounded read-only retry. Unsupported owners remain unresolved.
Cache freshness, complete message coverage and physical visibility are **not**
verified. Cache strings may contain untranslated localization keys or stale values.
The reader does not invoke the engine to refresh them. Event and alert surfaces are
separate samples, not one atomic game frame. Existing `content_status` describes GUI
text widgets; an icon-only window can additionally have native cached message data.

## Verification on 14 October 2026

207 focused regressions passed on Mac and Windows. Eleven new native-memory fixture
tests cover identity binding, pinned implementation/type checks, missing events,
cache context mismatches, ambiguous entries, extent checks and snapshot mutation;
two integration regressions preserve native metadata through summary/reference code.
Mac tests simulate process memory; Windows also exercised the actual reader.

A fresh protected Germany campaign passed real MCP checks: exact authored native
event ID `codex_reader.1`, bound messages from 16 global-alert containers, research
alert title/body, explicit freshness limits, read-only output and native pause.
The first fixture expired before the first MCP assertion; its failed evidence was
retained. A second harmless fixture used a recorded one-shot ID and the existing
game-side pause command. Original save bytes/timestamp, save-format setting and mod
selection were restored afterward; the owned game/task were closed, and request
identities retained. Other settings changes were preserved.
See [sanitized results](NATIVE_POPUP_VALIDATION_20261014.json).

## Lean measurement

Runtime scope: 6,113 to 6,182 lines (+69). Test scope: 2,500 to 2,562 (+62).
The new native reader is 65 lines and reuses the existing process reader, string
validation, formatting parser and snapshot retry. No size reduction, dependency or
new native DLL was introduced. The supported event-ID path now uses direct native
identity instead of requiring a script/localization scan.
