# TradeOps - Trading Operations Analytics & Exception Management Platform

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://vivianle-2209-tradeops-platform-dashboardapp-qveqlz.streamlit.app/)

TradeOps is an end-to-end trading operations analytics and exception-management platform that simulates post-trade reconciliation, detects operational breaks, scores exception severity, monitors SLA exposure, and escalates high-severity incidents into Jira through an n8n automation workflow.

The project is designed to reproduce core workflows found in trading operations, middle-office, and post-trade exception-management environments while keeping deterministic operational logic separate from AI-assisted triage.

---

## Live Demo

### Streamlit Dashboard

https://vivianle-2209-tradeops-platform-dashboardapp-qveqlz.streamlit.app/

> The deployed dashboard may require Streamlit access depending on deployment settings.

---

# Project Objectives

TradeOps demonstrates how an operational trading workflow can be designed from market-data ingestion through incident escalation.

The platform:

- retrieves historical equity trade data
- supports multiple securities
- normalizes raw market-data records
- constructs internal execution records
- generates synthetic downstream clearing records
- injects controlled operational errors
- reconciles execution and clearing data
- detects post-trade exceptions
- scores exception severity quantitatively
- tracks SLA exposure
- preserves break lifecycle state
- surfaces operational risk through Streamlit
- routes HIGH and CRITICAL incidents to n8n
- uses AI for root-cause triage
- prevents duplicate Jira incidents
- exposes escalated incidents back to the dashboard
- maintains an operational audit trail

The project focuses on system design, controls, exception handling, automation, and operational analytics rather than replicating a production brokerage or clearinghouse exactly.

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
                         │     Ingestion        │
                         │   Multiple Symbols   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    Data Cleaning     │
                         │ Normalized Trade Set │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Execution Enrichment │
                         │ Account / Side / ID  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Synthetic Clearing   │
                         │ + Controlled Errors  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Reconciliation     │
                         │   Exception Engine   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │ Severity + SLA + Lifecycle   │
                    └──────────────┬───────────────┘
                                   │
                  ┌────────────────┴────────────────┐
                  │                                 │
                  ▼                                 ▼
       ┌──────────────────────┐          ┌──────────────────────┐
       │       DuckDB         │          │        n8n           │
       │ Operational Storage  │          │ Automation Workflow  │
       └──────────┬───────────┘          └──────────┬───────────┘
                  │                                 │
                  ▼                                 ▼
       ┌──────────────────────┐          ┌──────────────────────┐
       │      Streamlit       │          │ AI Root-Cause Triage │
       │   Ops Dashboard      │          └──────────┬───────────┘
       └──────────────────────┘                     │
                                                   ▼
                                        ┌──────────────────────┐
                                        │  Deduplication Gate  │
                                        └──────────┬───────────┘
                                                   │
                                                   ▼
                                        ┌──────────────────────┐
                                        │        Jira          │
                                        │ Incident Escalation  │
                                        └──────────────────────┘
```

---

# Market Universe

TradeOps supports multiple US equity symbols in a single processing run.

The current test universe includes:

- AAPL
- AMZN
- GOOGL
- META
- MSFT
- NVDA
- TSLA

The universe is configurable in `src/ingestion.py`.

Example:

```python
SYMBOLS = [
    "MSFT",
    "AAPL",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "TSLA",
]
```

---

# End-to-End Processing Flow

```text
Alpaca Market Data
        ↓
Raw Trades
        ↓
Cleaned Trades
        ↓
Execution Enrichment
        ↓
Synthetic Clearing Records
        ↓
Reconciliation
        ↓
Trade-Break Detection
        ↓
Severity Scoring
        ↓
SLA Processing
        ↓
Lifecycle Management
        ↓
DuckDB
        ↓
Streamlit Dashboard
        ↓
HIGH / CRITICAL Dispatch
        ↓
n8n
        ↓
AI Root-Cause Triage
        ↓
Deduplication
        ↓
Jira
```

The entire Python pipeline can be executed with:

```bash
python run_pipeline.py
```

---

# Core Components

## 1. Market Data Ingestion

File:

```text
src/ingestion.py
```

Historical trades are retrieved from the Alpaca Market Data API using the IEX feed.

The ingestion layer supports:

- multiple symbols
- configurable start time
- configurable end time
- configurable record limits
- per-symbol reporting
- API timeout handling
- combined multi-symbol output

Raw output:

```text
data/raw/market_trades_raw.csv
```

---

## 2. Data Cleaning

File:

```text
src/cleaning.py
```

The cleaning stage converts Alpaca's raw trade schema into a standardized internal format.

Example mappings:

| Alpaca | TradeOps |
|---|---|
| `i` | `market_trade_id` |
| `p` | `price` |
| `s` | `quantity` |
| `t` | `execution_timestamp` |
| `x` | `venue` |
| `z` | `tape` |
| `c` | `trade_conditions` |

Cleaning includes:

- timestamp normalization
- numeric conversion
- symbol normalization
- venue normalization
- duplicate removal
- invalid-price filtering
- invalid-quantity filtering
- missing-field filtering
- deterministic sorting
- internal trade-ID creation

Example internal TradeOps identifier:

```text
TRD-000001
```

Clean output:

```text
data/cleaned/market_trades_cleaned.csv
```

---

## 3. Execution Enrichment

File:

```text
src/enrich_executions.py
```

Clean market trades are enriched into internal execution records.

Additional fields include:

- Trade ID
- Symbol
- Side
- Account
- Trader ID
- Order ID
- Record Source
- Currency
- Venue

Output:

```text
data/processed/executions.csv
```

---

## 4. Synthetic Clearing Generation

File:

```text
src/generate_clearing.py
```

Synthetic clearing records are created from execution records.

Controlled errors are deliberately introduced so the reconciliation engine can be tested.

Injected scenarios include:

- quantity mismatch
- price mismatch
- side mismatch
- account mismatch
- currency mismatch
- failed settlement
- late clearing
- missing clearing record
- missing execution record
- duplicate clearing record

Output:

```text
data/processed/clearing.csv
```

---

# Reconciliation Engine

File:

```text
src/reconciliation.py
```

The reconciliation engine compares execution and clearing records and identifies operational exceptions.

Supported exception types:

```text
MISSING_CLEARING_RECORD
MISSING_EXECUTION_RECORD
DUPLICATE_CLEARING_RECORD
QUANTITY_MISMATCH
PRICE_MISMATCH
SIDE_MISMATCH
ACCOUNT_MISMATCH
CURRENCY_MISMATCH
SETTLEMENT_FAILED
LATE_CLEARING
```

Outputs:

```text
data/processed/reconciliation_results.csv
data/processed/trade_breaks.csv
```

---

## Break Identity

Each exception row receives a unique:

```text
break_id
```

TradeOps also defines a canonical logical incident identity:

```text
dedup_key = trade_id:exception_type
```

Example:

```text
TRD-000842:PRICE_MISMATCH
```

This `dedup_key` is used across TradeOps and n8n to identify the same operational incident across multiple workflow runs.

---

# Severity Scoring

File:

```text
src/severity.py
```

Each trade break receives a deterministic quantitative risk score between 0 and 100.

Current thresholds:

| Score | Severity |
|---:|---|
| 75–100 | CRITICAL |
| 50–74 | HIGH |
| 30–49 | MEDIUM |
| 0–29 | LOW |

Severity can consider factors such as:

- exception type
- affected notional
- settlement failure
- mismatch characteristics
- clearing latency
- operational impact

Output:

```text
data/processed/trade_breaks_scored.csv
```

---

## Deterministic Source of Truth

TradeOps remains authoritative for:

```text
exception_type
severity
severity_score
```

The downstream AI workflow is not allowed to override these values.

This design separates deterministic operational controls from probabilistic AI reasoning.

---

# SLA Monitoring

File:

```text
src/sla.py
```

Each severity class is assigned an operational SLA.

| Severity | SLA |
|---|---:|
| CRITICAL | 15 minutes |
| HIGH | 30 minutes |
| MEDIUM | 60 minutes |
| LOW | 240 minutes |

Possible SLA states:

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

The dashboard can optionally re-age open incidents using a live SLA clock.

---

# Break Lifecycle

TradeOps is designed to preserve incident lifecycle information across pipeline runs.

Lifecycle fields include:

```text
dedup_key
first_seen_at
last_seen_at
break_status
resolved_at
```

State is stored under:

```text
data/state/
```

Expected behavior:

```text
New break
→ first_seen_at = now
→ last_seen_at = now
→ status = OPEN

Same break appears again
→ preserve first_seen_at
→ update last_seen_at

Break disappears
→ status = RESOLVED
→ resolved_at = now
```

This prevents SLA age from resetting on each pipeline execution.

---

# Dispatch State

TradeOps also supports persistent dispatch state so unchanged incidents are not repeatedly POSTed to n8n.

Example fields:

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

A break is redispatched when:

- it is new
- severity changes
- SLA status changes
- break status changes
- a previous dispatch failed

Unchanged events are skipped.

---

# DuckDB Storage

File:

```text
src/load_database.py
```

Operational datasets are loaded into DuckDB.

Database:

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

DuckDB provides the analytical storage layer used by Streamlit.

---

# Streamlit Dashboard

Main entry point:

```text
dashboard/app.py
```

The application contains five core views:

```text
Overview
Exception Queue
SLA & Risk
Trade Investigation
Jira Incidents
```

---

## Overview

The Overview page provides high-level trading-health metrics.

Examples:

- Total Trades
- Matched Trades
- Broken Trades
- Break Rate
- Critical Breaks
- Affected Notional

---

## Global Market Scope

Users can select securities at the top level of the dashboard.

Example:

```text
AAPL
AMZN
GOOGL
META
MSFT
NVDA
TSLA
```

The selected scope can drive:

- KPI calculations
- reconciliation totals
- break counts
- risk views
- investigation results

---

## Trade Volume by Symbol

The Overview includes a stacked chart where:

```text
Total Trades = Matched Trades + Broken Trades
```

Visual convention:

```text
Black = Matched Trades
Pink  = Broken Trades
```

The chart can show:

- total trades per security
- unique broken trades
- matched-trade volume
- break rate
- total labels
- hover-level operational detail

A trade containing several exception rows is counted as one broken trade.

---

# Exception Queue

The Exception Queue provides a working view of active exceptions.

Typical fields include:

- Trade ID
- Symbol
- Exception Type
- Severity
- SLA Status
- Break Status
- Affected Notional
- Age

Available filters include:

- severity
- SLA status
- break status
- exception type
- symbol
- venue
- trade ID

The queue respects global market scope.

---

# SLA & Risk

The SLA & Risk page focuses on operational urgency.

Example metrics include:

- Open Breaks
- SLA Breached
- At Risk
- Critical Incidents

Symbol-level analysis can include:

| Metric | Meaning |
|---|---|
| Total Trades | Reconciled trade volume |
| Broken Trades | Unique broken trades |
| Break Rate | Broken / total |
| SLA Breached | Incidents beyond SLA |

This separates raw incident volume from true operational concentration.

---

# Trade Investigation

The Trade Investigation page supports detailed drill-down into an individual trade.

Example:

```text
Trade ID        Symbol       Break Type          Severity
TRD-001842      NVDA         PRICE_MISMATCH      HIGH
```

Execution details can include:

- account
- side
- quantity
- price
- currency
- venue
- execution timestamp

Clearing details can include:

- clearing quantity
- clearing price
- clearing account
- clearing side
- clearing currency
- clearing status
- clearing latency

Exception details can include:

- Break ID
- Dedup Key
- Exception Type
- Severity
- Severity Score
- SLA Status
- Affected Notional
- First Seen
- Last Seen

---

# Jira Incidents

The Jira Incidents page surfaces incidents escalated through n8n.

Fields can include:

- Jira Issue Key
- Trade ID
- Symbol
- Break Type
- Severity
- Jira Status
- Jira Priority
- Assignee
- Jira URL
- First Seen
- Last Seen
- Jira Updated At

Direct links allow users to move from TradeOps into Jira.

---

# n8n Automation

TradeOps uses n8n Cloud for incident orchestration.

Main workflow:

```text
Webhook
    ↓
Normalize TradeOps Event
    ↓
AI Root-Cause Triage
    ↓
Confidence Gate
    ↓
Load Incident Registry
    ↓
Find Open Jira Incidents
    ↓
Resolve Deduplication Decision
    ↓
Route Jira Action
    ├── CREATE
    │     ↓
    │  Create Jira Incident
    │     ↓
    │  Register Incident
    │
    ├── COMMENT
    │     ↓
    │  Comment on Existing Jira Incident
    │     ↓
    │  Update Last Seen
    │
    └── LOG ONLY
          ↓
        Audit
```

---

# AI-Assisted Root-Cause Triage

AI is used only for qualitative operational analysis.

Example output:

```text
likely_root_cause
confidence
recommended_action
evidence
```

Example root-cause categories:

```text
CLEARING_OR_SETTLEMENT_FAILURE
BOOKING_OR_ALLOCATION_MISMATCH
REFERENCE_DATA_MISMATCH
PRICE_CAPTURE_MISMATCH
DUPLICATE_PROCESSING
LATE_CLEARING
MISSING_DOWNSTREAM_RECORD
UNKNOWN_REQUIRES_REVIEW
```

---

## AI Guardrails

AI must not recalculate or modify:

```text
trade_id
exception_type
severity
severity_score
```

Evidence is separated into:

```text
OBSERVED:
HYPOTHESIS:
```

This helps distinguish source data from model inference.

---

# Confidence Gate

AI confidence is routed through a confidence gate.

Example thresholds:

```text
AUTO             confidence >= 0.80
REVIEW REQUIRED  confidence >= 0.60
MANUAL REVIEW    confidence < 0.60
```

The confidence result affects operational handling but never overrides deterministic TradeOps severity.

---

# Jira Integration

Current escalation policy:

```text
CRITICAL → Jira
HIGH     → Jira
MEDIUM   → Dashboard only
LOW      → Dashboard only
```

This reduces Jira noise while retaining all exceptions in TradeOps.

---

## Jira Deduplication

Before creating a Jira ticket, n8n checks the canonical incident key:

```text
dedup_key = trade_id:exception_type
```

Checks include:

- incident registry
- existing open Jira incidents
- duplicates within the workflow run

Possible outcomes:

```text
CREATE
COMMENT
LOG_ONLY
LOOKUP_FAILED
IN_RUN_DUPLICATE
```

Existing incidents can therefore be updated rather than duplicated.

---

# Jira Incident Content

A Jira incident can contain:

- Trade ID
- Symbol
- Break Type
- Severity
- Severity Score
- Execution Quantity
- Clearing Quantity
- Execution Price
- Clearing Price
- Clearing Status
- Clearing Latency
- Affected Notional
- SLA Status
- AI Root Cause
- AI Confidence
- Evidence
- Recommended Action

---

# Incident Registry

n8n maintains a persistent incident registry.

Typical fields:

```text
dedup_key
break_id
trade_id
symbol
break_type
jira_issue_key
status
severity
first_seen_at
last_seen_at
last_workflow_run_id
```

The registry supports:

- deduplication
- lifecycle tracking
- Jira linkage
- repeated-break handling
- dashboard incident retrieval

---

# TradeOps Incident API

A second n8n workflow exposes incident-registry data to Streamlit.

Flow:

```text
GET Webhook
    ↓
Load TradeOps Incidents
    ↓
Format Incident API Response
    ↓
Respond to Webhook
```

Example response:

```json
{
  "dedup_key": "TRD-001842:PRICE_MISMATCH",
  "break_id": "BRK-000123",
  "trade_id": "TRD-001842",
  "symbol": "NVDA",
  "break_type": "PRICE_MISMATCH",
  "severity": "HIGH",
  "jira_issue_key": "TROP-31",
  "jira_issue_url": "https://your-domain.atlassian.net/browse/TROP-31",
  "first_seen_at": "2026-10-21T00:00:00Z",
  "last_seen_at": "2026-10-21T00:15:00Z"
}
```

---

# Audit Logging

The automation architecture supports operational audit logging.

Example audit fields:

```text
workflow_run_id
processed_at
break_id
dedup_key
trade_id
break_type
severity
severity_score
sla_status
affected_notional
likely_root_cause
ai_confidence
automated_decision
jira_action
jira_issue_key
jira_ticket_created
duplicate_prevented
action_taken
processing_status
retry_required
retry_stage
workflow_error
error_detail
```

This enables later analysis of:

- workflow reliability
- AI confidence
- Jira creation rates
- duplicate prevention
- failed operations
- retries
- incident outcomes

---

# Pipeline Orchestration

File:

```text
run_pipeline.py
```

The orchestration script runs:

```text
Ingestion
→ Cleaning
→ Execution Enrichment
→ Clearing Generation
→ Reconciliation
→ Severity Scoring
→ SLA Processing
→ DuckDB Load
→ n8n Dispatch
```

Run:

```bash
python run_pipeline.py
```

The pipeline stops immediately if a stage fails.

---

# Pipeline Logging

Scheduled executions can write logs to:

```text
logs/pipeline.log
```

Example:

```text
2026-10-21 11:00:00 | TRADEOPS PIPELINE START
2026-10-21 11:00:01 | START | Ingestion
2026-10-21 11:00:04 | SUCCESS | Ingestion
2026-10-21 11:00:05 | START | Cleaning
2026-10-21 11:00:07 | SUCCESS | Cleaning
2026-10-21 11:00:18 | SUCCESS | n8n dispatch
2026-10-21 11:00:18 | TRADEOPS PIPELINE COMPLETE
```

Runtime logs should remain outside source control.

---

# Cloud Architecture

The project uses several cloud services:

| Layer | Service |
|---|---|
| Dashboard | Streamlit Community Cloud |
| Automation | n8n Cloud |
| Incident Management | Jira Cloud |
| Source Control | GitHub |
| Scheduled Pipeline | GitHub Actions |
| Market Data | Alpaca |

Target architecture:

```text
GitHub Actions
      ↓
run_pipeline.py
      ↓
Alpaca Market Data
      ↓
Reconciliation
      ↓
Severity / SLA
      ↓
Operational Data
      ↓
n8n Cloud
      ↓
Jira Cloud

Streamlit Community Cloud
      ↓
TradeOps Dashboard
```

---

# GitHub Actions

TradeOps can run automatically using GitHub Actions.

Example:

```yaml
name: TradeOps Pipeline

on:
  workflow_dispatch:

  schedule:
    - cron: "*/30 * * * *"

jobs:
  run-tradeops:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run TradeOps pipeline
        env:
          ALPACA_API_KEY: ${{ secrets.ALPACA_API_KEY }}
          ALPACA_SECRET_KEY: ${{ secrets.ALPACA_SECRET_KEY }}
          N8N_WEBHOOK_URL: ${{ secrets.N8N_WEBHOOK_URL }}
        run: |
          python run_pipeline.py
```

Credentials are stored using GitHub Actions Secrets.

---

# Technology Stack

## Backend

- Python
- Pandas
- DuckDB
- Requests
- python-dotenv

## Market Data

- Alpaca Market Data API
- IEX feed

## Dashboard

- Streamlit
- Plotly

## Automation

- n8n Cloud

## Incident Management

- Jira Cloud

## Deployment

- Streamlit Community Cloud
- GitHub
- GitHub Actions

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
│   │
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
│       ├── sidebar.py
│       └── theme.py
│
├── data/
│   ├── raw/
│   │   └── market_trades_raw.csv
│   │
│   ├── cleaned/
│   │   └── market_trades_cleaned.csv
│   │
│   ├── processed/
│   │   ├── executions.csv
│   │   ├── clearing.csv
│   │   ├── reconciliation_results.csv
│   │   ├── trade_breaks.csv
│   │   ├── trade_breaks_scored.csv
│   │   └── trade_breaks_sla.csv
│   │
│   ├── state/
│   │   ├── break_lifecycle.csv
│   │   └── dispatch_state.csv
│   │
│   └── tradeops.duckdb
│
├── logs/
│   └── pipeline.log
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
├── .env
├── .gitignore
├── README.md
├── requirements.txt
└── run_pipeline.py
```

---

# Local Setup

## 1. Clone Repository

```bash
git clone https://github.com/vivianle-2209/tradeops-platform.git
cd tradeops-platform
```

---

## 2. Create Virtual Environment

### Windows

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
```

---

## 3. Install Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. Environment Variables

Create:

```text
.env
```

Example:

```env
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
N8N_WEBHOOK_URL=your_webhook
```

Never commit `.env`.

---

# Streamlit Secrets

Local Streamlit secrets:

```text
.streamlit/secrets.toml
```

Example:

```toml
N8N_INCIDENT_API_URL = "your_incident_api_url"
JIRA_BOARD_URL = "your_jira_board_url"
```

For Streamlit Community Cloud:

```text
Manage app
→ Settings
→ Secrets
```

Never commit:

```text
.streamlit/secrets.toml
```

---

# Run Full Pipeline

```bash
python run_pipeline.py
```

Or run stages manually:

```bash
python src/ingestion.py
python src/cleaning.py
python src/enrich_executions.py
python src/generate_clearing.py
python src/reconciliation.py
python src/severity.py
python src/sla.py
python src/load_database.py
python src/send_to_n8n.py
```

---

# Run Dashboard

```bash
python -m streamlit run dashboard/app.py
```

---

# Environment Configuration

| Variable | Purpose |
|---|---|
| `ALPACA_API_KEY` | Alpaca authentication |
| `ALPACA_SECRET_KEY` | Alpaca authentication |
| `N8N_WEBHOOK_URL` | Break-dispatch endpoint |

Streamlit secrets:

| Secret | Purpose |
|---|---|
| `N8N_INCIDENT_API_URL` | n8n Incident API |
| `JIRA_BOARD_URL` | Jira board link |

---

# Security

Recommended `.gitignore` entries:

```gitignore
.env
.venv/
__pycache__/
*.pyc

.streamlit/secrets.toml

logs/

*.duckdb.wal
```

Never commit:

- Alpaca credentials
- Jira credentials
- n8n credentials
- private API tokens
- Streamlit secrets
- local virtual environments

---

# Key Design Decisions

## Deterministic Reconciliation

Break detection is deterministic and reproducible.

AI is not involved in deciding whether an execution and clearing record match.

---

## AI Is a Triage Layer

AI answers questions such as:

```text
What is the likely root cause?
What should an analyst investigate?
How confident is the model?
```

It does not decide whether the trade is broken.

---

## `break_id` vs `dedup_key`

TradeOps deliberately separates:

```text
break_id
```

from:

```text
dedup_key
```

`break_id` identifies an individual exception row.

`dedup_key` identifies the persistent logical incident.

Example:

```text
dedup_key = trade_id:exception_type
```

This enables incident deduplication and lifecycle management.

---

## Unique Broken Trades vs Exception Rows

One trade can have multiple exceptions.

Example:

```text
TRD-001201
├── QUANTITY_MISMATCH
├── ACCOUNT_MISMATCH
└── LATE_CLEARING
```

This represents:

```text
1 broken trade
3 exception rows
```

Therefore dashboard break-volume metrics use unique trade counts where appropriate.

---

## Jira Escalation Threshold

Only:

```text
HIGH
CRITICAL
```

are automatically escalated into Jira.

MEDIUM and LOW incidents remain visible in the dashboard without creating unnecessary operational ticket volume.

---

# Example Incident Lifecycle

```text
1. NVDA execution is captured.

2. Synthetic clearing generates a quantity mismatch.

3. Reconciliation detects:
   QUANTITY_MISMATCH

4. TradeOps calculates:
   severity = HIGH
   severity_score = 62

5. SLA engine assigns:
   30-minute SLA

6. Break appears in Streamlit.

7. Dispatch layer determines it is Jira-eligible.

8. n8n receives the event.

9. AI triage suggests:
   BOOKING_OR_ALLOCATION_MISMATCH

10. n8n checks:
    TRD-001842:QUANTITY_MISMATCH

11. No existing incident is found.

12. Jira incident is created.

13. Incident registry stores:
    Jira key
    severity
    first_seen_at
    last_seen_at

14. TradeOps Jira Incidents page displays the ticket.
```

---

# Current Status

Implemented:

- multi-symbol market-data ingestion
- normalized trade data
- execution enrichment
- synthetic clearing generation
- controlled break injection
- post-trade reconciliation
- multiple exception types
- quantitative severity scoring
- SLA classification
- DuckDB storage
- Streamlit operational dashboard
- global symbol scope
- symbol-level analytics
- stacked matched-vs-broken volume visualization
- Exception Queue
- SLA & Risk view
- Trade Investigation
- n8n integration
- AI-assisted root-cause triage
- confidence gating
- Jira ticket creation
- Jira deduplication
- persistent n8n incident registry
- TradeOps Incident API
- audit workflow
- pipeline orchestration
- scheduled-cloud architecture

---

# Roadmap

Planned improvements:

- persistent cloud-hosted operational database
- cloud persistence of lifecycle state
- dispatch retry handling
- real Jira workflow-status synchronization
- Jira assignee synchronization
- Jira priority synchronization
- automatic incident resolution
- historical SLA trends
- historical break-rate trends
- pipeline-health dashboard
- pipeline-run observability
- configurable market universe
- configurable reconciliation tolerances
- richer clearing simulation
- automated tests
- CI validation
- Docker support
- structured application logging

---

# Portfolio Relevance

TradeOps demonstrates practical experience across:

- Python data engineering
- post-trade reconciliation
- trading operations
- operational exception management
- quantitative severity scoring
- SLA monitoring
- workflow automation
- AI-assisted operations
- API integration
- incident management
- deduplication
- analytical databases
- dashboard engineering
- cloud scheduling
- operational controls
- auditability

The project is particularly relevant to roles in:

- quantitative trading operations
- trading technology
- middle office
- financial data analytics
- operations engineering
- fintech
- workflow automation
- post-trade analytics

---

# Disclaimer

TradeOps is an educational and portfolio project.

The project combines historical market data with synthetic execution, clearing, reconciliation, exception, and incident records for demonstration purposes.

It is not:

- a brokerage system
- a live trading platform
- an order-management system
- a clearinghouse
- a settlement platform
- a trading strategy
- financial advice

Synthetic records should not be interpreted as real brokerage, exchange, clearing, or settlement events.

---

# Author

**Vivian Le**

GitHub:  
https://github.com/vivianle-2209

Repository:  
https://github.com/vivianle-2209/tradeops-platform

Live Dashboard:  
https://vivianle-2209-tradeops-platform-dashboardapp-qveqlz.streamlit.app/
