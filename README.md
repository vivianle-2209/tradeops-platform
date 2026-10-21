# TradeOps - Trading Operations Analytics & Exception Management Platform

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://vivianle-2209-tradeops-platform-dashboardapp-qveqlz.streamlit.app/)

TradeOps is an end-to-end post-trade operations platform that simulates execution-to-clearing reconciliation, detects operational breaks, prioritises exceptions using deterministic severity and SLA rules, and escalates high-risk incidents through n8n and Jira.

The project was built to explore how trading operations, exception management, workflow automation, data engineering, and operational analytics fit together in a realistic end-to-end system.

## Live Demo

**Streamlit dashboard**

https://vivianle-2209-tradeops-platform-dashboardapp-qveqlz.streamlit.app/

The deployed application is backed by a scheduled GitHub Actions pipeline that refreshes the operational data automatically.

---

## What the Platform Does

TradeOps models a simplified post-trade workflow:

```text
Market Trade
    ↓
Execution Record
    ↓
Clearing Record
    ↓
Reconciliation
    ↓
Exception Detection
    ↓
Severity + SLA Assessment
    ↓
Operational Dashboard
    ↓
HIGH / CRITICAL Escalation
    ↓
n8n
    ↓
Jira Incident
```

The platform currently supports:

- multi-symbol US equity market-data ingestion
- execution record construction
- synthetic clearing generation
- controlled break injection
- deterministic reconciliation
- trade-break classification
- quantitative severity scoring
- SLA monitoring
- persistent break lifecycle tracking
- duplicate-dispatch prevention
- DuckDB analytical storage
- Streamlit operational dashboards
- n8n workflow automation
- Jira incident escalation
- scheduled cloud execution using GitHub Actions

---

# Architecture

```text
                         ┌──────────────────────┐
                         │ Alpaca Market Data   │
                         │      IEX Feed        │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      Ingestion       │
                         │   Multi-Symbol Data  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │     Cleaning         │
                         │  Normalised Trades   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Execution Enrichment │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Synthetic Clearing   │
                         │ + Injected Failures  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Reconciliation     │
                         │  Exception Detection │
                         └──────────┬───────────┘
                                    │
                                    ▼
                     ┌───────────────────────────┐
                     │ Severity + SLA + Lifecycle│
                     └─────────────┬─────────────┘
                                   │
                   ┌───────────────┴────────────────┐
                   │                                │
                   ▼                                ▼
        ┌──────────────────────┐        ┌──────────────────────┐
        │       DuckDB         │        │        n8n           │
        │ Operational Storage  │        │ Workflow Automation  │
        └──────────┬───────────┘        └──────────┬───────────┘
                   │                               │
                   ▼                               ▼
        ┌──────────────────────┐        ┌──────────────────────┐
        │      Streamlit       │        │ AI-Assisted Triage   │
        │  Operations Dashboard│        └──────────┬───────────┘
        └──────────────────────┘                   │
                                                   ▼
                                        ┌──────────────────────┐
                                        │ Deduplication / Gate │
                                        └──────────┬───────────┘
                                                   │
                                                   ▼
                                        ┌──────────────────────┐
                                        │        Jira          │
                                        │ Incident Management  │
                                        └──────────────────────┘
```

---

# Deployment Architecture

The deployed project separates the **backend pipeline** from the **frontend dashboard**.

```text
GitHub Actions
    │
    │ scheduled every 30 minutes
    ▼
run_pipeline.py
    │
    ├── fetch market data
    ├── build executions
    ├── generate clearing
    ├── reconcile
    ├── score severity
    ├── calculate SLA
    ├── update lifecycle
    ├── dispatch eligible incidents
    └── rebuild DuckDB
    │
    ▼
data/tradeops.duckdb
    │
    ▼
GitHub repository
    │
    ▼
Streamlit Community Cloud
```

GitHub Actions acts as the scheduled **worker**, while Streamlit acts as the **presentation layer**.

This avoids making the dashboard responsible for running background jobs.

---

# Market Universe

The current test universe contains seven US equities:

```text
AAPL
AMZN
GOOGL
META
MSFT
NVDA
TSLA
```

The market universe is configurable in:

```text
src/ingestion.py
```

---

# End-to-End Pipeline

The entire pipeline is orchestrated through:

```bash
python run_pipeline.py
```

Current processing stages:

```text
1. Market Data Ingestion
2. Data Cleaning
3. Execution Enrichment
4. Synthetic Clearing Generation
5. Reconciliation
6. Severity Scoring
7. SLA + Lifecycle Processing
8. DuckDB Loading
9. n8n Dispatch
```

The pipeline uses structured logging and reports the status and duration of each stage.

---

# 1. Market Data Ingestion

**File**

```text
src/ingestion.py
```

Trade data is retrieved from the Alpaca Market Data API using the IEX feed.

The ingestion layer supports:

- multiple symbols
- configurable time windows
- API authentication through environment variables
- per-symbol retrieval
- combined output
- request timeout handling

Output:

```text
data/raw/market_trades_raw.csv
```

---

# 2. Data Cleaning

**File**

```text
src/cleaning.py
```

Raw market records are converted into a standard internal TradeOps schema.

The stage performs:

- timestamp parsing
- numeric conversion
- symbol standardisation
- venue standardisation
- invalid-record filtering
- duplicate removal
- deterministic sorting
- internal trade-ID generation
- execution-notional calculation

Example internal ID:

```text
TRD-000001
```

Output:

```text
data/cleaned/market_trades_cleaned.csv
```

---

# 3. Execution Enrichment

**File**

```text
src/enrich_executions.py
```

Clean market trades are transformed into internal execution records.

Additional fields include:

```text
trade_id
symbol
side
account_id
trader_id
order_id
venue
currency
execution_notional
record_source
```

Output:

```text
data/processed/executions.csv
```

---

# 4. Synthetic Clearing

**File**

```text
src/generate_clearing.py
```

Clearing records are generated from the execution population.

Controlled operational failures are deliberately injected to test the downstream reconciliation and exception-management logic.

Example scenarios include:

```text
QUANTITY_MISMATCH
PRICE_MISMATCH
SIDE_MISMATCH
ACCOUNT_MISMATCH
CURRENCY_MISMATCH
SETTLEMENT_FAILED
LATE_CLEARING
MISSING_CLEARING_RECORD
MISSING_EXECUTION_RECORD
DUPLICATE_CLEARING_RECORD
```

Output:

```text
data/processed/clearing.csv
```

---

# 5. Reconciliation Engine

**File**

```text
src/reconciliation.py
```

The reconciliation engine compares execution and clearing records.

Each trade is classified as either:

```text
MATCHED
```

or one or more operational exceptions.

Outputs:

```text
data/processed/reconciliation_results.csv
data/processed/trade_breaks.csv
```

## Break Identity

Every exception receives a `break_id`.

A logical incident is identified using:

```text
dedup_key = trade_id:exception_type
```

Example:

```text
TRD-000842:PRICE_MISMATCH
```

This key is reused by TradeOps and the downstream automation layer to identify the same incident across repeated pipeline runs.

---

# 6. Deterministic Severity Scoring

**File**

```text
src/severity.py
```

TradeOps assigns a deterministic severity score to each break.

Severity levels:

| Score | Severity |
|---:|---|
| 75–100 | CRITICAL |
| 50–74 | HIGH |
| 30–49 | MEDIUM |
| 0–29 | LOW |

Scoring can incorporate:

- exception type
- affected notional
- settlement failure
- mismatch magnitude
- latency
- operational impact

Output:

```text
data/processed/trade_breaks_scored.csv
```

## Source-of-Truth Principle

TradeOps remains authoritative for:

```text
exception_type
severity
severity_score
```

AI is used to assist investigation and root-cause triage, but it cannot override deterministic operational classifications.

---

# 7. SLA Monitoring

**File**

```text
src/sla.py
```

Each severity level receives an operational SLA.

| Severity | SLA |
|---|---:|
| CRITICAL | 15 minutes |
| HIGH | 30 minutes |
| MEDIUM | 60 minutes |
| LOW | 240 minutes |

Possible states include:

```text
WITHIN_SLA
AT_RISK
BREACHED
CLOSED
```

Output:

```text
data/processed/trade_breaks_sla.csv
```

The Streamlit dashboard can also re-age open incidents using the current wall-clock time.

---

# 8. Persistent Break Lifecycle

TradeOps keeps lifecycle state across pipeline executions.

Important fields include:

```text
dedup_key
first_seen_at
last_seen_at
break_status
resolved_at
```

Lifecycle behaviour:

```text
New break
→ first_seen_at = current time
→ status = OPEN

Same break appears again
→ preserve first_seen_at
→ update last_seen_at

Break disappears
→ status = RESOLVED
→ set resolved_at
```

Persistent state:

```text
data/state/break_lifecycle.csv
```

This prevents an unresolved break from becoming artificially “new” every time the pipeline runs.

---

# 9. Dispatch State & Deduplication

TradeOps does not repeatedly send unchanged incidents to n8n.

Persistent dispatch state tracks fields such as:

```text
dedup_key
last_dispatched_at
last_dispatched_severity
last_dispatched_sla_status
last_dispatched_break_status
dispatch_attempts
dispatch_status
last_dispatch_error
```

A break is dispatched when:

- it is new
- a previous dispatch failed
- severity changes
- SLA status changes
- break lifecycle status changes

Unchanged events are skipped.

Only active:

```text
HIGH
CRITICAL
```

breaks are currently eligible for downstream escalation.

---

# 10. DuckDB Analytical Storage

**File**

```text
src/load_database.py
```

Pipeline outputs are loaded into:

```text
data/tradeops.duckdb
```

Core tables include:

```text
executions
clearing_records
reconciliation_results
trade_breaks
```

DuckDB provides a lightweight analytical store for the Streamlit application.

The scheduled cloud pipeline refreshes the DuckDB snapshot and persists it back to the repository for the deployed dashboard.

---

# Streamlit Operations Dashboard

**Entry point**

```text
dashboard/app.py
```

The application contains five primary views:

```text
Overview
Exception Queue
SLA & Risk
Trade Investigation
Jira Incidents
```

## Overview

Provides system-level trading-health metrics including:

- Total Trades
- Matched Trades
- Broken Trades
- Break Rate
- Critical Breaks
- Affected Notional
- SLA Breaches
- At-Risk Incidents
- Average Break Age
- Average Clearing Latency
- Open Breaks

It also provides symbol-level trading activity and exposure views.

---

## Global Market Scope

The dashboard allows users to scope analysis by one or more symbols.

```text
AAPL  AMZN  GOOGL  META  MSFT  NVDA  TSLA
```

The selected market scope propagates through:

- KPI calculations
- reconciliation metrics
- exception counts
- risk analysis
- investigation views
- Jira incident filtering where symbol metadata is available

---

## Exception Queue

The Exception Queue acts as an operational worklist.

Users can review breaks by:

- trade
- symbol
- exception type
- severity
- SLA state
- break state
- affected notional

Individual trades can then be opened in the investigation view.

---

## SLA & Risk

The SLA & Risk page focuses on operational exposure.

It provides views such as:

- SLA-state distribution
- severity distribution
- break ageing
- symbol-level risk
- highest-risk breaks
- exposure concentration
- breached / at-risk queues

---

## Trade Investigation

The investigation view provides drill-down into a single trade.

It brings together:

```text
Execution Record
Clearing Record
Reconciliation Result
Break Details
Severity
SLA
Lifecycle
```

This provides an auditable explanation of why a trade was classified as a break.

---

# n8n + Jira Integration

**File**

```text
src/send_to_n8n.py
```

Eligible incidents are sent to an n8n webhook.

The payload includes:

```text
identity
trade details
reconciliation evidence
financial exposure
clearing information
risk classification
SLA information
lifecycle information
```

n8n then performs downstream workflow automation including:

```text
TradeOps event
    ↓
Deduplication
    ↓
AI-assisted root-cause triage
    ↓
Confidence / control logic
    ↓
Jira create or update
    ↓
Incident registry
    ↓
Audit trail
```

TradeOps remains authoritative for deterministic exception and severity fields.

---

# Jira Incident Dashboard

The Streamlit application also exposes an incident-registry view sourced from the n8n/Jira integration.

The registry is designed to display:

```text
Jira Ticket
Trade ID
Symbol
Break Type
Severity
TradeOps Status
Jira Status
Jira Priority
Jira Assignee
First Seen
Last Seen
```

The historical Jira registry is intentionally separate from the current TradeOps break snapshot.

Therefore:

```text
Total historical Jira incidents
```

does not necessarily equal:

```text
Current open TradeOps breaks
```

### Current Integration Note

The current incident registry successfully retrieves historical Jira/TradeOps records, while richer Jira metadata synchronisation such as status, priority, assignee, and lifecycle mapping is still being refined.

---

# GitHub Actions Automation

Workflow:

```text
.github/workflows/tradeops-pipeline.yml
```

The pipeline runs:

```text
every 30 minutes
```

and can also be triggered manually.

The workflow:

```text
Checkout repository
→ Set up Python
→ Install dependencies
→ Run TradeOps pipeline
→ Upload runtime artifacts
→ Persist DuckDB and lifecycle state
→ Push refreshed state to main
```

Runtime artifacts are retained temporarily for debugging.

Persistent operational state includes:

```text
data/tradeops.duckdb
data/state/break_lifecycle.csv
data/state/dispatch_state.csv
```

This allows the deployed Streamlit dashboard to receive refreshed data without requiring a local Windows machine to remain online.

---

# Project Structure

```text
tradeops-platform/
│
├── .github/
│   └── workflows/
│       └── tradeops-pipeline.yml
│
├── dashboard/
│   ├── app.py
│   ├── app_pages/
│   │   ├── overview.py
│   │   ├── exception_queue.py
│   │   ├── sla_risk.py
│   │   ├── trade_investigation.py
│   │   └── jira_incidents.py
│   │
│   └── tradeops_ui/
│       ├── components.py
│       ├── data.py
│       ├── formatting.py
│       ├── investigation.py
│       ├── sidebar.py
│       ├── tables.py
│       ├── charts.py
│       └── theme.py
│
├── data/
│   ├── raw/
│   ├── cleaned/
│   ├── processed/
│   ├── state/
│   └── tradeops.duckdb
│
├── src/
│   ├── ingestion.py
│   ├── cleaning.py
│   ├── enrich_executions.py
│   ├── generate_clearing.py
│   ├── reconciliation.py
│   ├── severity.py
│   ├── sla.py
│   ├── load_database.py
│   ├── query_database.py
│   └── send_to_n8n.py
│
├── run_pipeline.py
├── requirements.txt
├── .gitignore
└── README.md
```

---

# Running Locally

## 1. Clone the repository

```bash
git clone https://github.com/vivianle-2209/tradeops-platform.git
cd tradeops-platform
```

## 2. Create a virtual environment

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure environment variables

Create a local `.env` file containing the required integration credentials.

Example variable names:

```text
ALPACA_API_KEY
ALPACA_SECRET_KEY
N8N_WEBHOOK_URL
```

Do not commit credentials to Git.

## 5. Run the pipeline

```bash
python run_pipeline.py
```

## 6. Launch the dashboard

```bash
python -m streamlit run dashboard/app.py
```

---

# Design Decisions

## Why Python?

Python provides a strong ecosystem for:

- tabular data processing
- APIs
- analytics
- database interaction
- automation
- dashboard development

---

## Why DuckDB?

DuckDB is used because this project primarily performs analytical processing over structured tabular data.

It provides:

- fast local analytics
- SQL querying
- simple deployment
- minimal infrastructure
- direct integration with Pandas

For a production multi-user system, the storage layer could be replaced with PostgreSQL, a cloud warehouse, or another persistent shared database.

---

## Why Streamlit?

Streamlit provides a lightweight way to build an operational analytics interface directly on top of Python data logic.

In this architecture, Streamlit is deliberately used as the **frontend**, not as the scheduler.

---

## Why GitHub Actions?

The original local prototype used Windows Task Scheduler.

The deployed architecture now uses GitHub Actions so the pipeline can run independently of the developer's computer.

This creates a clearer separation:

```text
run_pipeline.py = what runs

GitHub Actions = when and where it runs

DuckDB = where analytical state is stored

Streamlit = how users view the data

n8n = workflow automation

Jira = incident management
```

---

## Why n8n?

n8n is used for the workflow-orchestration layer rather than embedding all incident-management logic directly into Python.

This makes the downstream process easier to visualise and separates:

```text
deterministic trading logic
```

from:

```text
workflow automation and AI-assisted triage
```

---

# Controls & Reliability

The platform includes several operational controls:

- deterministic severity classification
- canonical deduplication keys
- persistent incident lifecycle state
- persistent dispatch state
- automatic retry for failed dispatches
- HIGH / CRITICAL escalation gating
- SLA monitoring
- separation of deterministic logic and AI reasoning
- auditable reconciliation evidence
- scheduled cloud execution
- pipeline-stage logging
- GitHub Actions artifacts for debugging

---

# Current Limitations

TradeOps is an educational and portfolio project, not a production trading or clearing system.

Current limitations include:

- clearing data is synthetically generated
- operational failures are deliberately injected
- market data is sourced from the Alpaca IEX feed
- DuckDB is used as a lightweight persistence layer
- GitHub is temporarily used to distribute the refreshed database snapshot
- historical Jira test incidents remain in the registry
- richer Jira metadata synchronisation is still being refined
- execution IDs are generated by the simulated internal pipeline rather than received from a production OMS/EMS
- the platform does not model every stage of real clearing, settlement, custody, or regulatory reporting

---

# Future Improvements

Potential extensions include:

```text
Real external clearing data
PostgreSQL / cloud database persistence
Production-grade message queues
Event-driven processing
Better incident lifecycle reconciliation
Bidirectional Jira status synchronisation
More robust observability
Metrics and alerting
Authentication and role-based access
Containerisation
Automated tests
CI quality gates
Historical break analytics
Trade-level lineage
Microstructure analytics
```

---

# What This Project Demonstrates

TradeOps demonstrates practical experience across:

**Data Engineering**
- API ingestion
- data cleaning
- pipeline orchestration
- schema design
- analytical storage

**Trading Operations**
- execution / clearing reconciliation
- break detection
- exception classification
- SLA monitoring
- operational incident management

**Software Engineering**
- modular Python architecture
- state management
- logging
- error handling
- cloud scheduling
- deployment

**Analytics**
- operational KPIs
- risk exposure
- break ageing
- symbol-level analysis
- investigation workflows

**Automation**
- n8n orchestration
- incident deduplication
- Jira escalation
- AI-assisted triage

---

# Disclaimer

This project is for educational, portfolio, and engineering demonstration purposes only.

It does not execute trades, provide investment advice, or represent a production brokerage, exchange, clearinghouse, or settlement platform.