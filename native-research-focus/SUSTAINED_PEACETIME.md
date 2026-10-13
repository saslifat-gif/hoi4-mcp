# Sustained Germany policy runner

Live-verified on 13 October 2026 in a protected Germany campaign on the pinned
Windows executable. A five-minute run verified five new selections and three
research completion/refill cycles: Basic Machine Tools → Mechanical Computing,
Electronic Mechanical Engineering → Improved Machine Tools, and Construction I
→ Construction II. The economic-growth focus was also selected and verified.
Existing busy research slots and active focuses were preserved.

The first attempt stopped on a changing research sample at maximum speed. The
runner now waits only for the typed `SnapshotChanged` condition; invalid reads
still stop it. The retained action was reconciled with its original ID before
resuming. All 41 affected research, policy and runner tests passed on macOS and
Windows. Both failed reports and the successful report were retained privately.
The bounded run paused/disarmed on exit; the owned game was closed and recovery
verified original autosave bytes/timestamp, restored the save-format setting and
removed only the owned mod entry. No keyboard or mouse was used. This live check
used the Python runner and native command backend, not a separate MCP wire test.

The policy fills empty research slots from its existing economic technology
priorities and selects its existing supported German economic focus. It waits
when no supported choice is available, requests a fresh observation on the next
poll, and resumes selection when research completes. It never replaces busy slots
or an active focus. It stops on rejection, uncertainty or failed readback, retaining
any unresolved intent and its original request ID.

This does not yet plan construction, production, trade or additional focus paths.
The maximum is 16 verified selections per run; the underlying native process
request limit also still applies. Continuing across saved games is not supported.

## Run in a protected temporary campaign

Require AC power, an already bound/armed native session, and installed time and
peacetime readers. Resume game time and set speed through the existing time MCP,
then use the Windows environment's existing Python with both command directories
on PYTHONPATH:

```
python peacetime_run.py --session-file SESSION_FILE --seconds 300 --action-budget 16
```

The default poll interval is five seconds. Duration accepts 1–3600 wall-clock
seconds. The runner checks AC before starting and before every step, stops issuing
new choices on exit, and retains pending requests. It does not manage game pause,
speed or shutdown: the test supervisor must pause through the native time interface
and perform the existing owned-session recovery even when the runner fails.

MCP clients can instead call `hoi4_ai_start` with `wait_for_choices=true` and poll
`hoi4_ai_step`. Those calls retain the existing explicit stop/time-control contract;
the caller supplies a duration limit and power checks. The default remains stop
at idle for compatibility with bounded tests.

This completes the scoped sustained research/focus validation. Economy planning,
additional focus paths, events, military play and save/load continuation remain
outside this runner's scope. See `SUSTAINED_VALIDATION_20261013.json` for sanitized
live results.
