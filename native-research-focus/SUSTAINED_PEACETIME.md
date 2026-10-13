# Sustained Germany policy runner

Implemented locally on 13 October 2026. All 20 offline policy/runner tests pass
after removing one duplicate uncertainty test;
the sustained runner has not yet been tested in a live HOI4 campaign.

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

Next live check: observe a research completion followed by a new supported
assignment, ensure existing slots/focus remain intact, and verify shutdown and
profile restoration. Keep the sustained-campaign Notion item unchecked until that
live check passes.
