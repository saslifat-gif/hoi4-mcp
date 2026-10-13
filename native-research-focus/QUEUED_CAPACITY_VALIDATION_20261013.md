# Queued construction live validation — 13 October 2026

Passed in a protected Germany single-player campaign on the pinned Windows executable, using actual MCP requests without keyboard or mouse.

With five shared slots available, one civilian factory was accepted, an oversized five-level request rejected, and four military factories accepted. Both factory types were rejected on the full shared queue. Two dockyards and five civilian factories in another state were accepted. Independent native monthly-save quantities matched queue readback.

The first run exposed stale bridge state overwriting completed snapshot IDs in the shared ledger. Operations now lock and reload the current ledger before updating. The rerun passed every queue check and retained all original read and action IDs. Two new regressions cover stale readers and competing writers; 78 affected tests passed on macOS and Windows, plus two MCP transport tests using simulated engine logs.

Both test games were closed. Recovery verified original autosave bytes and timestamp, restored the original save-format setting, and removed only the owned mod entry, preserving other settings updates. The reminder remains paused.

See [sanitized live results](QUEUED_CAPACITY_VALIDATION_20261013.json). This validates the three supported building types and one to five levels on the pinned game. Sustained autonomous peacetime play remains pending.
