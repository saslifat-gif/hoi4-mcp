# Native event-definition options and additional popup surface

`hoi4_popup_snapshot` now includes `native_options` for a verified `CEventWindow`.
Each item contains `native_index`, `name_key`, `identity_verified`,
`availability_verified: false` and `effects_verified: false`.
`option_ids_verified` describes these definition identities; always retain the
explicit `option_identity_scope: event_definition_not_displayed_choices`.
An event ID and native index identify an option; its localization key can repeat.
Never equate this list with visible, enabled or legal commands. No option selection
command is added.

The pinned current `CEvent` supplies its option pointer vector at +0x368. Objects
must have the verified `CEventOption` type/vtable, with the name key at +0x178 and
selection index at +0x1f0. Owner, vector, extent, type, string and index bindings are
read and rechecked with the existing snapshot guard/retry. Nothing is inferred from
button captions or script-reference matching. All reads remain free of screenshots,
input, native callbacks and process-memory writes.

`kind="world_tension"` now scans the installed
`interface/worldtensionwindowpopup.gui` surface, also included in `kind="all"`.
It uses existing container/text traversal. Its owner-specific data, tooltip getter,
physical visibility and live content-bearing verification remain unresolved.
Existing raw text, known formatting runs and unknown-control records are preserved;
complete tooltip formatting and other notification-owner messages remain pending.

## Validation on 14 October 2026

47 affected offline tests passed on Mac and Windows. Four new memory fixtures cover
option identities, extent/type failures and a changed vector; two summary/surface
fixtures verify the public scope and the additional surface query.

Eight actual MCP checks passed in a protected Germany campaign: native event ID,
two exact option-name keys, indices 0/1, visible literal-key labels, explicit
availability/effect limits, world-tension surface sampling, native pause and read-only
snapshot output. World-tension text was not shown, so only its scan was live exercised.
The fixture's English localization did not load in the active language; identical
captions were not live verified. That failed caption assertion remains private.
An earlier fixture used the wrong namespace directive and was recovered; a wrong
string offset was rejected by the reader and corrected against actual option data.
The corrected event expired during inspection, then a recorded one-shot replay and
native pause were reconciled with their original IDs. Neither reader mutation nor
input was used to read the final options.

Both owned campaigns were closed. Original autosave bytes/timestamp and targeted
save-format/mod settings were restored, other settings updates preserved, and replay
IDs/receipts and failed evidence retained privately. No installed game code, private
ABI report, save or user profile is included in this publication.
See [sanitized results](EVENT_OPTIONS_VALIDATION_20261014.json).

## Lean measurement

Runtime scope: 6,250 -> 6,266 lines (+16). Test scope: 2,635 -> 2,667 (+32).
The existing process reader, string decoder, container traversal and snapshot retry
are reused. No code-size reduction, dependency or native DLL was added.
