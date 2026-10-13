# Verified native research reader — 2026-10-12

`hoi4_native_snapshot` now reports research completion, unlocked levels, slot assignment and progress percentages from native game data. It uses no screenshots or keyboard/mouse input. The reader itself performs only process-memory reads.

## Meaning of the fields

- `completed`: the technology has reached its native maximum level. This is checked against the engine's completed-technology array on every snapshot.
- `unlocked`: at least one level has been researched. Repeatable technologies can be unlocked while additional levels remain.
- `researched_levels`, `max_levels`: native counters used by research eligibility and completion routines.
- `researching`, `research_slots`: current slot assignments; slots are 1-based.
- `progress_fraction`, `progress_percent`: progress toward the current/next level, using the same point threshold as the engine's completion routine. Fully completed technologies report 100%, including after the native points counter resets to zero.
- `progress_scope`: `next_level` or `all_levels_complete`. An idle repeatable technology can show `available_next_level` with 0% next-level progress.
- `progress_raw`, `completion_threshold_raw`: native fixed-point values retained for verification. Remaining time is not estimated from them because research speed and penalties can change.
- Negative-cost sentinel definitions have no research percentage (`null`). They still have verified completion/level information. An assigned technology with an invalid threshold causes an explicit error.

## Consistency and lifetime checks

Each read checks the process lifetime, bound world, technology ownership, definition indices and native vtables. It samples slot assignments, levels, progress, cost settings and the completed list, then checks them again. A completion tick, definition reload or simulation tick change causes a bounded retry. Persistent inconsistency fails explicitly; it never returns a fabricated zero or a mixed snapshot. The game process is checked again before returning.

This remains pinned to the existing supported executable and authorized Germany single-player test binding. The native selection backend is unchanged.

## Validation

Live testing used the real MCP stdio server and the actual HOI4 engine:

- All 552 loaded technology records were decoded. The reader agreed with the native completed list: 55 completed technologies, no unknown completion flags.
- Infantry Weapons read as completed/unlocked at 100%; the engine's `has_tech` predicate independently returned yes.
- Basic Machine Tools initially read as unresearched. After native selection, it read as researching in slot 1 with a numeric percentage. The engine independently returned `has_tech = no` while it remained in progress.
- A later MCP snapshot verified that its percentage increased normally. Exact values and predicate log lines are recorded in `RESEARCH_LIVE_VALIDATION.json`.

Twenty focused regression tests cover completion-counter reset, repeatable levels, partial progress, invalid costs, the negative-cost sentinel, empty slots, ownership, changed world, a completion during reading, definition changes and persistent snapshot inconsistency. These are simulated-memory tests, distinct from the live checks. The existing native-controller and command tests remain applicable.

The zero-counter completion transition is verified by the native completion routine and simulated-memory regression. This test did not wait for a newly selected technology to finish naturally. Existing completed technologies and active progression were live-verified.

The previous speculative `+0x1e8` completion flag is no longer used by the reader. Its raw enum/flag fields have been replaced by verified levels and completion-list agreement.
