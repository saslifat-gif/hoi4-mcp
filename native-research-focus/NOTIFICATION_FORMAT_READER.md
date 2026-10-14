# Native notification popups and bitmap-font tokens

`hoi4_popup_snapshot(kind="notification_popups")` reads the installed
`interface/notifications/` surface. The pinned native owners for timed-idea expiry,
external focus completion and legacy diplomatic messages bind their own notification
entry. Each entry retains its own title/message; nested panels and notification-center
containers do not combine different owners into one message. Passive snapshots invoke
no native callback, memory write, screen capture or keyboard/mouse input.

The shared text parser follows the supported build's native bitmap-font grammar:

- Color selectors nest; a reset resumes the preceding selector.
- Named icons consume ASCII letters, digits, underscores and pipes, up to 128 characters.
  A closing icon marker is optional. Whitespace/control characters terminate the token.
- Flag tokens carry the following three characters. Their flag asset identity remains unverified.
- Native atlas tokens retain atlas index/frame references. Atlas assets remain unverified.
- Unknown or malformed controls remain explicit, and the original raw text remains available.

Plain text and ordered formatting runs now use one parser. Color selectors do not
establish gameplay eligibility; RGB/font assets and physical rendering are not inferred.
Complete tooltip asset/geometry coverage, active tooltip freshness and regional/theater
messages remain pending. The existing native DLL is unchanged.

## Verification

239 focused tests pass on both Mac and Windows. Regressions cover three owner
bindings, distinct notification entries, token boundaries, nested colors, flags,
atlas payloads and malformed/unknown controls.

Two protected real-MCP campaigns collectively read all three native popup owner types.
Idea expiry was captured in the first campaign; a controlled second campaign captured
external-focus and legacy war messages using a shipped side-message effect. A persistent
authored event verified native event identity, nested colors, flags, icons, readable plain
text and unchanged paused clock. The combined 12-check result explicitly records that
all three owners were not captured in one campaign.

Incomplete attempts are retained: startup notifications expired before sampling;
running GUI churn required a paused controlled read; the final idea repeat did not run
because the owned 15-minute task had stopped the process. Native receipts and IDs were
preserved, including a later read-back confirming the first pause receipt. Both original
profiles/autosaves were restored, no HOI4 process remains, and both owned tasks were
removed. Private ABI reports, installed game code, saves and request ledgers are excluded.
See [sanitized evidence](NOTIFICATION_FORMAT_VALIDATION_20261014.json).

## Lean measurement

Runtime: 6,359 -> 6,382 lines (+23). Tests: 2,773 -> 2,800 (+27).
Code-size reduction: 0%. No new dependency or native DLL. Existing process reads,
string guards, snapshot retries and owner binding are reused; duplicated plain-text
icon/color matching is replaced by the shared token parser.
