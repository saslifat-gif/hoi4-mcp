# Read-only popup and notification reader

Call `hoi4_popup_snapshot(kind="all")` through the existing native MCP server.
`kind` can also be `events`, `popups` or `notifications`.
The configured session must identify the current owned game process and game root.
The reader does not require command arming or native command-module initialization.
It uses Windows process-memory reads, with the same pinned executable version as
this project. It sends no input, takes no screenshots and performs no process writes.

## Returned data

Each surface has its own timestamps, truncation flag and ordered window list.
Supported event and generic popup layouts expose title, description, text fields,
button captions and event option labels. Native formatting and duplicate text are
preserved. Known descendant panels are grouped; separate same-name windows remain
separate. Hidden descendants are excluded, and unresolved widget states are reported.
Notifications cover the global-alert and diplomatic-request container layouts.
Icon metadata is retained; alerts without decoded message text report `icon_only`.

Engine-local shown flags do not prove physical screen visibility. Samples are not
an atomic game frame. Complete child coverage and universal popup coverage are not
claimed. Supported event IDs and global-alert cached messages now have native bindings;
see [native reader validation](NATIVE_POPUP_READER.md). Option IDs, effects, enabled
state, cache freshness and unsupported owners remain unresolved. A bounded retry handles
observed GUI-registry changes; unsupported builds and identity failures still fail.

## Verification

180 focused tests passed on both Mac and Windows: 14 adapter tests and 166 native
GUI backend fixtures. Mac tests simulate memory; they do not run the Windows reader.
A real Windows MCP check read exact authored event title/body/option text and exact
generic popup title/body/button text, plus real global alerts and an authored
diplomatic-request layout fixture. It returned one event, one popup and 15
notification containers without truncation. No diplomatic request was submitted.
See [sanitized results](POPUP_VALIDATION_20261013.json).

The final owned campaign recovery passed on 14 October 2026. HOI4 was already
closed; the original autosave bytes and timestamp, save-format setting and mod
selection were restored. Other settings updates and request IDs were preserved.
Private process data, request IDs, saves and copied installed GUI files are excluded
from this repository.

## Lean measurement

This round adds 85 authored runtime lines and 76 test lines. It reuses 1,036 runtime
lines and 1,223 test lines from the existing read-only GUI implementation. Shipping
scope grows from 4,915 to 6,036 runtime lines and 1,142 to 2,441 test lines; this is
feature coverage, not a code-size reduction. No new dependency or native DLL is added.
