"""
TradeOps pipeline orchestrator.

Runs each pipeline stage sequentially and writes a structured
operational log to logs/pipeline.log.

Logging strategy:
- INFO: stage start, success, row counts, durations, summaries
- WARNING: non-fatal anomalies
- ERROR: failed stages and tracebacks
- Rotating log file to prevent unbounded growth
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path


# ==================================================
# Paths
# ==================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
)

LOG_DIR = (
    PROJECT_ROOT
    / "logs"
)

LOG_FILE = (
    LOG_DIR
    / "pipeline.log"
)


# ==================================================
# Pipeline stages
# ==================================================

PIPELINE_STAGES = [
    (
        "Ingestion",
        "src/ingestion.py",
    ),
    (
        "Cleaning",
        "src/cleaning.py",
    ),
    (
        "Execution enrichment",
        "src/enrich_executions.py",
    ),
    (
        "Clearing generation",
        "src/generate_clearing.py",
    ),
    (
        "Reconciliation",
        "src/reconciliation.py",
    ),
    (
        "Severity scoring",
        "src/severity.py",
    ),
    (
        "SLA processing",
        "src/sla.py",
    ),
    (
        "DuckDB load",
        "src/load_database.py",
    ),
    (
        "n8n dispatch",
        "src/send_to_n8n.py",
    ),
]


# ==================================================
# Logging
# ==================================================

def build_logger() -> logging.Logger:
    """
    Configure console + rotating file logging.
    """

    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    logger = logging.getLogger(
        "tradeops_pipeline"
    )


    logger.setLevel(
        logging.INFO
    )


    # Prevent duplicated handlers if imported/rerun.
    logger.handlers.clear()


    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


    # --------------------------------------------------
    # Rotating file handler
    # --------------------------------------------------

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )

    file_handler.setLevel(
        logging.INFO
    )

    file_handler.setFormatter(
        formatter
    )


    # --------------------------------------------------
    # Console handler
    # --------------------------------------------------

    console_handler = logging.StreamHandler(
        sys.stdout
    )

    console_handler.setLevel(
        logging.INFO
    )

    console_handler.setFormatter(
        formatter
    )


    logger.addHandler(
        file_handler
    )

    logger.addHandler(
        console_handler
    )


    return logger


LOGGER = build_logger()


# ==================================================
# Helpers
# ==================================================

def extract_summary_lines(
    output: str,
) -> list[str]:
    """
    Keep only operationally useful summary lines.

    This avoids dumping entire dataframes or verbose debug output
    into the production pipeline log.
    """

    if not output:
        return []


    useful_keywords = [
        "Rows retrieved:",
        "Raw rows:",
        "Clean rows:",
        "Execution rows:",
        "Clearing rows:",
        "Matched trades:",
        "Broken trades:",
        "Total trades:",
        "Total breaks:",
        "Breaks scored:",
        "Current breaks:",
        "Lifecycle records:",
        "Lifecycle OPEN:",
        "Lifecycle RESOLVED:",
        "Eligible:",
        "Sent:",
        "Skipped:",
        "Failed:",
        "Database saved to:",
        "Breaks tracked:",
    ]


    summaries = []


    for raw_line in output.splitlines():

        line = raw_line.strip()


        if not line:
            continue


        if any(
            keyword in line
            for keyword in useful_keywords
        ):

            summaries.append(
                line
            )


    return summaries


def run_stage(
    stage_name: str,
    script_path: str,
) -> tuple[bool, float]:
    """
    Run one pipeline stage.

    Returns:
        success
        duration_seconds
    """

    started = time.perf_counter()


    LOGGER.info(
        "START | %s",
        stage_name,
    )


    script = (
        PROJECT_ROOT
        / script_path
    )


    if not script.exists():

        duration = (
            time.perf_counter()
            - started
        )


        LOGGER.error(
            (
                "FAILED | %s | "
                "script_not_found=%s | "
                "duration=%.2fs"
            ),
            stage_name,
            script,
            duration,
        )


        return (
            False,
            duration,
        )


    try:

        result = subprocess.run(
            [
                sys.executable,
                str(script),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=os.environ.copy(),
        )


    except Exception:

        duration = (
            time.perf_counter()
            - started
        )


        LOGGER.exception(
            (
                "FAILED | %s | "
                "subprocess_exception | "
                "duration=%.2fs"
            ),
            stage_name,
            duration,
        )


        return (
            False,
            duration,
        )


    duration = (
        time.perf_counter()
        - started
    )


    # --------------------------------------------------
    # Successful stage
    # --------------------------------------------------

    if result.returncode == 0:

        summaries = (
            extract_summary_lines(
                result.stdout
            )
        )


        for summary in summaries:

            LOGGER.info(
                "%s | %s",
                stage_name,
                summary,
            )


        LOGGER.info(
            (
                "SUCCESS | %s | "
                "duration=%.2fs"
            ),
            stage_name,
            duration,
        )


        return (
            True,
            duration,
        )


    # --------------------------------------------------
    # Failed stage
    # --------------------------------------------------

    LOGGER.error(
        (
            "FAILED | %s | "
            "exit_code=%s | "
            "duration=%.2fs"
        ),
        stage_name,
        result.returncode,
        duration,
    )


    if result.stdout.strip():

        LOGGER.error(
            "%s | STDOUT\n%s",
            stage_name,
            result.stdout.strip(),
        )


    if result.stderr.strip():

        LOGGER.error(
            "%s | STDERR\n%s",
            stage_name,
            result.stderr.strip(),
        )


    return (
        False,
        duration,
    )


# ==================================================
# Pipeline
# ==================================================

def main() -> int:
    """
    Run the complete TradeOps pipeline.
    """

    pipeline_started = (
        time.perf_counter()
    )


    LOGGER.info(
        "=" * 72
    )


    LOGGER.info(
        "TRADEOPS PIPELINE START"
    )


    LOGGER.info(
        "python=%s",
        sys.executable,
    )


    completed = 0


    for (
        stage_name,
        script_path,
    ) in PIPELINE_STAGES:

        success, _ = run_stage(
            stage_name,
            script_path,
        )


        if not success:

            total_duration = (
                time.perf_counter()
                - pipeline_started
            )


            LOGGER.error(
                "TRADEOPS PIPELINE FAILED"
            )


            LOGGER.error(
                (
                    "COMPLETED | %s/%s | "
                    "duration=%.2fs"
                ),
                completed,
                len(
                    PIPELINE_STAGES
                ),
                total_duration,
            )


            LOGGER.info(
                "=" * 72
            )


            return 1


        completed += 1


    total_duration = (
        time.perf_counter()
        - pipeline_started
    )


    LOGGER.info(
        "TRADEOPS PIPELINE COMPLETE"
    )


    LOGGER.info(
        (
            "COMPLETED | %s/%s | "
            "duration=%.2fs"
        ),
        completed,
        len(
            PIPELINE_STAGES
        ),
        total_duration,
    )


    LOGGER.info(
        "=" * 72
    )


    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )