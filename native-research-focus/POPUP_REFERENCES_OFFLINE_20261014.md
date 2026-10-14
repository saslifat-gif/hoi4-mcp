# Popup script references — 14 October 2026

Installed and tested on Windows; native event identity and live icon-only alert
messages remain unverified. No game launch, input, screenshots or new native
addresses were used in this round. Previous campaign recovery passed: original
save bytes/timestamp and targeted profile settings restored; no HOI4 process remains.

Call `hoi4_popup_snapshot(kind="all", include_script_references=True, language="en")`.
Use `language="zh"` for Simplified Chinese. The default performs native GUI reads
without an installed-script scan. Source enrichment scans loose base `events`,
`localisation` and `interface/alerts.gui` on each call. DLC, mods and runtime source
precedence remain unresolved; script references never prove active game identity.

Events gain `event_id_candidates` only from an exact title, body and ordered
option-label match against literal localized definitions. Duplicate event matches,
duplicate localization keys, repeated/conditional script fields and dynamic text
remain unresolved. `event_id` stays null; `event_id_verified` stays false.

Notifications gain `notification_text_references` through explicit GUI
`pdx_tooltip` keys on returned icon/button names in the matching outer window,
including nested panels. Dynamic templates retain raw text without fabricated
values. Runtime binding stays unverified and `icon_only` remains unchanged.
The actual installed alerts GUI contains **zero static tooltip bindings**. Thus
this route currently provides no message text for that game's icon-only alerts;
reading their dynamic callbacks/native owners is still required. Frame numbers
are never interpreted as alert IDs.

## Validation

The initial offline round passed 191 focused tests. The continuation reproduced
and corrected lost nested-window binding and repeated event option-name failures.
All 28 affected reference/adapter tests now pass on Mac and Windows; the unchanged
166 backend tests also passed on Windows before the source-only correction.
Actual installed source scans passed in both languages: 6,967 event definitions,
129,541 English keys and 129,562 Chinese keys, in approximately 2.3/3.5 seconds.
This is source verification, not a new live popup/MCP identity test.

## Lean measurement

Initial feature round: +73 runtime lines, +50 test lines. Continuation fixes:
+4 runtime lines and +9 test lines. Runtime scope is now 6,113 lines; tests 2,500.
No size reduction, dependency or native offset was added. Existing parser reused.

The subsequent [native reader](NATIVE_POPUP_READER.md) now supplies verified event IDs and global-alert cache strings; the static-reference limits above still apply.
