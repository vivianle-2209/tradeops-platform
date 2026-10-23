# TradeOps refactor review

The refactor is implemented for local review. The real pipeline has not been run.
There have been no Alpaca, n8n or Jira requests, no changes to those services, and
no Git commits, staging operations or pushes by this refactor.

## Before and after

| Concern | Before | After |
| --- | --- | --- |
| Identity | Batch-relative trade and break IDs | Permanent scoped trade/incident identities; separate run/snapshot/event IDs |
| Source coverage | One page, rolling lookback | All pages, overlap, per-symbol checkpoints, bounded catch-up and explicit backfill |
| State | CSV snapshots and independent lifecycle CSV | Persistent typed execution, clearing and incident state in DuckDB |
| Resolution | Incident disappeared from window | Corrected counterpart evidence or reasoned operator resolution |
| SLA | Vulnerable to ID reuse/window resets | Persistent lifetime first-seen; shared worker/dashboard rule; recurrence episodes |
| Commit | Independent table replacement/history appends | One transaction for source, incidents, history, checkpoints and outbox |
| Replay | Duplicate snapshots and regenerated demo evidence | Committed run replay is a no-op; deterministic synthetic records |
| Delivery | Current HIGH/CRITICAL rows and a dispatch CSV | Durable versioned outbox, per-event acknowledgement, backoff and ordering |
| Updates | Downgrades/resolutions filtered out | Initial escalation threshold separate from subsequent lifecycle updates |
| Exposure | Quantity-only proxy, summed across exception rows | Separate exception impact, trade proxy and deduplicated monetary aggregation |
| History UI | Full raw histories loaded by page | Shared parameterized SQL, scoped summaries/trends, bounded caches, selected-snapshot detail |
| CI | Live pipeline without tests | Offline test gate; publish durable outbox before HTTP; persist retry outcomes |

## Dependency order used

1. Reinspect working tree, source dependencies, current schemas and CSV boundaries.
2. Establish IDs, run context, configuration and typed contracts.
3. Implement deterministic demo data, reconciliation, persistent lifecycle and SLA.
4. Implement explicit schema/versioning and the transactional persistence boundary.
5. Connect paginated ingestion/checkpoints, stable run replay and explicit outcomes.
6. Add same-transaction outbox creation, delivery retries and downstream updates.
7. Correct financial aggregation and historical/dashboard data access.
8. Add offline tests, CI gating, documentation and final state verification.

No migration has been applied to the user's reset database. Schema initialization
is lazy and occurs on the first intentional worker write. The first successful
data-bearing run creates Snapshot #1. No-data runs before that point can record
status/checkpoints but do not create an artificial historical snapshot.

## Validation

- Full suite: **63 passed** (`python -m pytest -q`).
- Tests use temporary databases and mocked source/destination clients.
- Tests prohibit opening the real database, all real HTTP requests, and external
  socket connections. Windows asyncio loopback IPC is permitted for AppTest.
- Covered rollback after current-state/incident/outbox changes, idempotent run replay,
  first snapshot numbering, archives, checkpoints, partial failures, lifecycle,
  reopening, SLA, event ordering/retries/downgrades/resolution, exposure and scoped SQL.
- Streamlit AppTest covered an empty initialized database, historical rendering,
  and the shared current-data/SLA/metric boundary.
- Python compilation and Git diff whitespace checks passed.
- Real database SHA-256 remains
  `89897197ff622c607bcb752f9206dd35ad0b344145f4f93f3c881bd1b5fa40c5`.
- Real tables `executions`, `clearing_records`, `reconciliation_results` and
  `trade_breaks` each contain **0 rows**. There are no history/run/outbox tables yet.
- All **3** existing reset-backup files retain their original fingerprints.
- The missing DuckDB Python timestamp dependency `pytz` was declared and installed
  in the local virtual environment. Package installation was separate from tests.

## Files changed by this refactor

These are the substantive source/document/configuration changes. Previously staged
changes remain staged as they were; this refactor's edits were not staged.

| File | Change |
| --- | --- |
| `README.md` | Current architecture, Mermaid diagram, IDs, contracts, state/history, failure semantics, configuration, operating commands and limits |
| `REFACTOR_REVIEW.md` | This implementation/validation handoff |
| `run_pipeline.py` | In-process orchestration, explicit outcomes, committed-run replay, backfill and split persistence/delivery modes |
| `requirements.txt` | Declare requests and DuckDB's Python timezone dependency |
| `requirements-dev.txt` | Runtime dependencies plus pytest |
| `pytest.ini` | Suite discovery and warning policy |
| `.github/workflows/tradeops-pipeline.yml` | Offline test gate, pre-delivery state publication, independent retries and final delivery-state publication |
| `src/__init__.py` | Importable worker/domain package |
| `src/config.py` | Central defaults, credentials boundary and setting validation |
| `src/contracts.py` | Scoped IDs, run context/statuses, typed table schemas and validation |
| `src/storage.py` | Versioned DDL, safe empty-baseline initialization, transaction and typed-write helpers |
| `src/metrics.py` | Trade-grain monetary totals and deterministic group attribution |
| `src/analytics.py` | Shared parameterized/scoped historical SQL and summary aggregation |
| `src/events.py` | Existing payload sections plus complete evidence, meaningful-change detection and stable versioned events |
| `src/cleaning.py` | Stable source identity, overlap deduplication and invalid-input rejection |
| `src/enrich_executions.py` | Per-trade deterministic simulated execution attributes |
| `src/generate_clearing.py` | Per-trade deterministic simulated clearing and controlled breaks |
| `src/reconciliation.py` | Complete evidence, explicit nulls, stable breaks, corrected exposure and proof-of-correction rules |
| `src/severity.py` | Typed empty result handling and nullable clearing-status safety |
| `src/sla.py` | Pure durable lifecycle/ageing rules, conservative reopening and shared SLA classification |
| `src/ingestion.py` | Pagination, persisted-position reads, overlap/catch-up/replay and explicit symbol outcomes |
| `src/load_database.py` | Transactional operational/incident/history/checkpoint/outbox persistence, failure metadata and operator resolution |
| `src/send_to_n8n.py` | Durable ordered outbox dispatch, per-event acknowledgement, backoff and stable idempotency keys |
| `src/query_database.py` | Read-only diagnostics with no import-time database effects |
| `dashboard/app.py` | Canonical symbol scope and persisted worker-status feedback |
| `dashboard/app_pages/exception_queue.py` | Canonical symbol display for all incident types |
| `dashboard/app_pages/historical_operations.py` | Shared cached/scoped SQL access; preserve existing page charts/layout |
| `dashboard/app_pages/jira_incidents.py` | Canonical symbol fallback and explicit registry-unavailable state |
| `dashboard/app_pages/overview.py` | Deduplicated exposure, canonical symbols and empty-chart handling |
| `dashboard/app_pages/sla_risk.py` | Deduplicated exposure/concentration and full known gross notional |
| `dashboard/tradeops_ui/data.py` | Transaction-consistent current reads, shared SLA/metrics, cached historical query boundary and explicit registry errors |
| `dashboard/tradeops_ui/charts.py` | Trade-grain monetary grouping |
| `dashboard/tradeops_ui/investigation.py` | Canonical symbol in trade selector; side evidence remains separate |
| `dashboard/tradeops_ui/tables.py` | Canonical symbol column label |
| `tests/conftest.py` | Network/production-DB guards, temporary settings and fake clients |
| `tests/test_identity_contracts.py` | Identity, scope, replay and validation |
| `tests/test_state_and_database.py` | Transactions, schema safety, first-run history, persistent incidents and SLA |
| `tests/test_ingestion.py` | Pages, checkpoint timing, overlap, backfill and failures |
| `tests/test_outbox.py` | Escalation, meaningful updates, resolution, retry identity/backoff and ordering |
| `tests/test_metrics_analytics.py` | Impact formulas, deduplication, orphan evidence and scoped/timezone-aware history |
| `tests/test_pipeline.py` | Orchestrator outcomes, failure isolation, no-data replay and full mocked flow |
| `tests/test_dashboard.py` | Headless Streamlit and shared dashboard data checks |

Ignored diagnostic artifacts: `logs/refactor_baseline.json` records the starting
database/backup fingerprints; mocked orchestrator tests also append to
`logs/pipeline.log`. Python/pytest cache files are generated by validation.

The deleted lifecycle/dispatch CSVs, reset database changes relative to Git, and
`data/reset_backup/` already existed before this task. They were not created,
deleted, reset or overwritten by this refactor. The reset script shown in the IDE
was not present on disk during inspection and was not created or changed here.
No secrets or theme configuration were changed. The existing UI colors/layout
remain; canonical symbols, empty states and worker-error feedback are the minor
backend-required adjustments.

## Remaining assumptions before intentional live use

1. n8n must permit versioned UPDATE/RESOLVED events for the same `dedup_key`, and
   should deduplicate repeated `event_id`. The remote workflow was not inspected
   or modified. An HTTP success means webhook acceptance, not Jira completion.
2. Delivery is at least once. The unavoidable accept-before-ack crash window is
   handled with stable IDs, not a claim of atomic exactly-once HTTP delivery.
3. Operate one writer. GitHub concurrency controls scheduled runs; do not overlap
   a local worker. Git-distributed binary state remains a demo deployment compromise.
4. Keep the requested 30-minute schedule, but it cannot enforce prompt escalation
   within a 15-minute critical SLA. The dashboard live clock is read-only.
5. Clearing is simulated once per new trade. Correction requires supplied clearing
   evidence or explicit resolution; replay does not randomly repair incidents.
6. Reopened incidents retain lifetime first-seen and SLA age; episode timestamps
   separately describe recurrence. Historical counts are state observations.
7. No FX conversion, retention deletion or production authentication was added.
   Long-term archival policy and multi-writer infrastructure remain future work.
