"""
Building blocks for the Trade Investigation page.
"""

from __future__ import annotations

import math

import pandas as pd

from tradeops_ui.components import (
    badge,
)

from tradeops_ui.data import (
    load_trade_records,
)

from tradeops_ui.formatting import (
    esc,
    fmt_duration,
    fmt_int,
    fmt_minutes,
    fmt_money,
    fmt_ts,
    fmt_value,
    is_missing,
    to_utc,
    worst,
)

from tradeops_ui.theme import (
    BLACK,
    GREY_MID,
    PINK,
    SEVERITY_ORDER,
    SLA_ORDER,
)


# --------------------------------------------------
# Comparison fields
# --------------------------------------------------

COMPARISON_FIELDS = [
    (
        "Symbol",
        "symbol",
        "symbol",
        "text",
    ),
    (
        "Side",
        "side",
        "side",
        "text",
    ),
    (
        "Quantity",
        "quantity",
        "quantity",
        "qty",
    ),
    (
        "Price",
        "price",
        "price",
        "price",
    ),
    (
        "Notional",
        "notional",
        "notional",
        "money",
    ),
    (
        "Currency",
        "currency",
        "currency",
        "text",
    ),
    (
        "Account",
        "account",
        "account",
        "text",
    ),
]


# ==================================================
# Records
# ==================================================

def trade_options(
    filtered: pd.DataFrame,
) -> pd.DataFrame:
    """
    One row per trade in the current dashboard scope.

    Includes symbol so the selector can display:

    TRD-001234 · META · HIGH · PRICE MISMATCH
    """

    if filtered.empty:

        return pd.DataFrame(
            columns=[
                "rank",
                "symbol_exec",
                "severity",
                "types",
            ]
        )


    return (
        filtered
        .groupby(
            "trade_id"
        )
        .agg(
            rank=(
                "priority_rank",
                "min",
            ),

            symbol_exec=(
                "symbol_exec",
                "first",
            ),

            severity=(
                "severity",
                lambda s: (
                    worst(
                        s,
                        SEVERITY_ORDER,
                    )
                ),
            ),

            types=(
                "exception_type",
                lambda s: (
                    ", ".join(
                        sorted(
                            s
                            .dropna()
                            .astype(str)
                            .unique()
                        )
                    )
                ),
            ),
        )
        .sort_values(
            "rank"
        )
    )


def _record_from_breaks(
    trade_breaks: pd.DataFrame,
    suffix: str,
) -> dict:
    """
    Fallback execution / clearing record reconstructed
    from reconciliation break columns.
    """

    row = (
        trade_breaks
        .iloc[0]
    )


    record = {
        field: row.get(
            f"{field}_{suffix}"
        )
        for field
        in [
            "symbol",
            "side",
            "quantity",
            "price",
            "currency",
            "account",
        ]
    }


    record[
        "timestamp"
    ] = row.get(
        (
            "execution_timestamp"
            if suffix == "exec"
            else "clearing_timestamp"
        )
    )


    return record


def _with_notional(
    record: dict,
) -> dict:

    qty = (
        record.get(
            "quantity"
        )
    )

    price = (
        record.get(
            "price"
        )
    )


    record[
        "notional"
    ] = (
        None
        if (
            is_missing(qty)
            or is_missing(price)
        )
        else (
            float(qty)
            * float(price)
        )
    )


    return record


def resolve_records(
    trade_id: str,
    trade_breaks: pd.DataFrame,
    version: float,
):
    """
    Resolve execution and clearing source records.

    Prefer DuckDB source tables. Fall back to
    reconciled break values if necessary.
    """

    error = None


    try:

        exec_df, clear_df = (
            load_trade_records(
                trade_id,
                version,
            )
        )


    except Exception as exc:

        exec_df = (
            pd.DataFrame()
        )

        clear_df = (
            pd.DataFrame()
        )

        error = (
            str(exc)
        )


    # --------------------------------------------------
    # Execution
    # --------------------------------------------------

    if not exec_df.empty:

        execution = (
            exec_df
            .iloc[0]
            .to_dict()
        )


        execution[
            "timestamp"
        ] = execution.get(
            "execution_timestamp"
        )


    else:

        execution = (
            _record_from_breaks(
                trade_breaks,
                "exec",
            )
        )


        execution[
            "venue"
        ] = (
            trade_breaks[
                "venue"
            ]
            .iloc[0]
        )


    execution = (
        _with_notional(
            execution
        )
    )


    # --------------------------------------------------
    # Clearing
    # --------------------------------------------------

    clearing_records = []


    for _, row in (
        clear_df.iterrows()
    ):

        record = (
            row.to_dict()
        )


        record[
            "timestamp"
        ] = (
            record.get(
                "clearing_timestamp"
            )
        )


        clearing_records.append(
            _with_notional(
                record
            )
        )


    reconciled_count = (
        pd.to_numeric(
            trade_breaks.get(
                "clearing_record_count",
                pd.Series(
                    dtype=float
                ),
            ),
            errors="coerce",
        )
    )


    # If source lookup failed but reconciliation says
    # a clearing record existed, construct fallback.
    if (
        clear_df.empty
        and
        not reconciled_count.empty
        and
        reconciled_count.max()
        > 0
    ):

        clearing_records.append(
            _with_notional(
                _record_from_breaks(
                    trade_breaks,
                    "clear",
                )
            )
        )


    return (
        execution,
        clearing_records,
        exec_df,
        clear_df,
        error,
    )


# ==================================================
# Comparison
# ==================================================

def _compare(
    exec_value,
    clear_value,
    kind: str,
) -> tuple[str, str]:

    if (
        is_missing(
            clear_value
        )
        and
        not is_missing(
            exec_value
        )
    ):

        return (
            "MISSING",
            "—",
        )


    if (
        is_missing(
            exec_value
        )
        or
        is_missing(
            clear_value
        )
    ):

        return (
            "MATCH",
            "—",
        )


    if kind == "text":

        same = (
            str(
                exec_value
            )
            .strip()
            .upper()
            ==
            str(
                clear_value
            )
            .strip()
            .upper()
        )


        return (
            (
                "MATCH",
                "—",
            )
            if same
            else (
                "MISMATCH",
                "differs",
            )
        )


    diff = (
        float(
            clear_value
        )
        -
        float(
            exec_value
        )
    )


    if math.isclose(
        diff,
        0.0,
        abs_tol=1e-9,
    ):

        return (
            "MATCH",
            "—",
        )


    if kind == "qty":

        text = (
            f"{diff:+,.0f}"
        )


    elif kind == "money":

        text = (
            (
                "+"
                if diff > 0
                else "-"
            )
            +
            fmt_money(
                abs(diff)
            )
        )


    else:

        text = (
            f"{diff:+,.4f}"
            .rstrip("0")
            .rstrip(".")
        )


    return (
        "MISMATCH",
        text,
    )


def _fmt_field(
    value,
    kind: str,
) -> str:

    if is_missing(
        value
    ):

        return "—"


    if kind == "qty":

        return (
            f"{float(value):,.0f}"
        )


    if kind == "money":

        return (
            fmt_money(
                value
            )
        )


    if kind == "price":

        return (
            f"{float(value):,.4f}"
            .rstrip("0")
            .rstrip(".")
        )


    return (
        str(value)
    )


def comparison_table(
    execution: dict,
    clearing: dict | None,
) -> tuple[str, int]:

    rows = []
    mismatches = 0


    for (
        label,
        exec_field,
        clear_field,
        kind,
    ) in COMPARISON_FIELDS:

        exec_value = (
            execution.get(
                exec_field
            )
        )


        clear_value = (
            clearing.get(
                clear_field
            )
            if clearing
            else None
        )


        status, diff = (
            _compare(
                exec_value,
                clear_value,
                kind,
            )
        )


        mismatches += (
            status
            == "MISMATCH"
        )


        rows.append(
            (
                f'<tr class="'
                f'{"diff" if status != "MATCH" else ""}'
                f'">'

                f'<td class="f">'
                f'{esc(label)}'
                f'</td>'

                f'<td>'
                f'{esc(_fmt_field(exec_value, kind))}'
                f'</td>'

                f'<td>'
                f'{esc(_fmt_field(clear_value, kind))}'
                f'</td>'

                f'<td class="d">'
                f'{esc(diff)}'
                f'</td>'

                f'<td>'
                f'{badge(status)}'
                f'</td>'

                f'</tr>'
            )
        )


    table = (
        '<table class="cmp">'

        '<thead>'
        '<tr>'
        '<th>Field</th>'
        '<th>Execution</th>'
        '<th>Clearing</th>'
        '<th>Difference</th>'
        '<th></th>'
        '</tr>'
        '</thead>'

        '<tbody>'

        f'{"".join(rows)}'

        '</tbody>'
        '</table>'
    )


    return (
        table,
        mismatches,
    )


# ==================================================
# Panels
# ==================================================

def kv_panel(
    items: list[
        tuple[
            str,
            object,
        ]
    ],
) -> str:

    return (
        '<div class="kv">'
        +
        "".join(
            (
                f'<span class="k">'
                f'{esc(key)}'
                f'</span>'

                f'<span class="v">'
                f'{esc(fmt_value(value))}'
                f'</span>'
            )

            for key, value
            in items
        )
        +
        '</div>'
    )


def trade_summary_card(
    trade_id: str,
    execution: dict,
    trade_breaks: pd.DataFrame,
) -> str:

    severity = (
        worst(
            trade_breaks[
                "severity"
            ],
            SEVERITY_ORDER,
        )
    )


    sla = (
        worst(
            trade_breaks[
                "sla_status"
            ],
            SLA_ORDER,
        )
    )


    affected = (
        trade_breaks[
            "affected_notional"
        ]
        .max()
    )


    fields = [
        (
            "Symbol",
            execution.get(
                "symbol"
            ),
            False,
        ),

        (
            "Side",
            execution.get(
                "side"
            ),
            False,
        ),

        (
            "Venue",
            (
                execution.get(
                    "venue"
                )
                or
                trade_breaks[
                    "venue"
                ]
                .iloc[0]
            ),
            False,
        ),

        (
            "Account",
            execution.get(
                "account"
            ),
            False,
        ),

        (
            "Execution notional",
            fmt_money(
                trade_breaks[
                    "execution_notional"
                ]
                .max()
            ),
            False,
        ),

        (
            "Affected notional",
            fmt_money(
                affected
            ),
            bool(
                not is_missing(
                    affected
                )
                and
                affected > 0
            ),
        ),

        (
            "Open breaks",
            (
                f'{int(trade_breaks["break_status"].eq("OPEN").sum())}'
                f' / '
                f'{len(trade_breaks)}'
            ),
            False,
        ),
    ]


    grid = (
        "".join(
            (
                '<div>'

                f'<div class="k">'
                f'{esc(key)}'
                f'</div>'

                f'<div class="v{" hot" if hot else ""}">'
                f'{esc(fmt_value(value))}'
                f'</div>'

                '</div>'
            )

            for (
                key,
                value,
                hot,
            )
            in fields
        )
    )


    return (
        '<div class="trade-card">'

        '<div class="trade-top">'

        '<div class="trade-id">'
        '<span>TRADE</span>'
        f'{esc(trade_id)}'
        '</div>'

        '<div class="trade-badges">'
        f'{badge(severity)}'
        f'{badge(sla)}'
        '</div>'

        '</div>'

        f'<div class="trade-grid">'
        f'{grid}'
        f'</div>'

        '</div>'
    )


def break_cards(
    trade_breaks: pd.DataFrame,
) -> str:
    """
    Render one operational card for each detected
    break on the selected trade.
    """

    cards = []

    sorted_breaks = (
        trade_breaks
        .sort_values(
            "priority_rank"
        )
    )

    for _, row in (
        sorted_breaks.iterrows()
    ):

        consumed = row.get(
            "sla_consumed_pct"
        )

        if is_missing(
            consumed
        ):

            width = 0.0

        else:

            width = max(
                0.0,
                min(
                    float(
                        consumed
                    ),
                    100.0,
                ),
            )


        sla_status = str(
            row.get(
                "sla_status",
                "",
            )
        )


        bar_color = {
            "BREACHED": BLACK,
            "AT_RISK": PINK,
        }.get(
            sla_status,
            GREY_MID,
        )


        severity = str(
            row.get(
                "severity",
                "",
            )
        )


        sev_class = (
            f"sev-{severity.lower()}"
        )


        # ------------------------------------------
        # Detail panel
        # ------------------------------------------

        details_html = kv_panel(
            [
                (
                    "Severity score",
                    fmt_int(
                        row.get(
                            "severity_score"
                        )
                    ),
                ),

                (
                    "Status",
                    row.get(
                        "break_status"
                    ),
                ),

                (
                    "Age",
                    fmt_minutes(
                        row.get(
                            "age_minutes"
                        )
                    ),
                ),

                (
                    "SLA remaining",
                    fmt_minutes(
                        row.get(
                            "sla_remaining_minutes"
                        )
                    ),
                ),

                (
                    "Affected notional",
                    fmt_money(
                        row.get(
                            "affected_notional"
                        )
                    ),
                ),

                (
                    "Dedup key",
                    row.get(
                        "dedup_key"
                    ),
                ),
            ]
        )


        # ------------------------------------------
        # SLA progress bar
        # ------------------------------------------

        sla_bar_html = (
            f'<div class="sla-bar" '
            f'title="SLA consumed {width:.0f}%">'
            f'<span style="'
            f'width:{width:.1f}%;'
            f'background:{bar_color};'
            f'"></span>'
            f'</div>'
        )


        # ------------------------------------------
        # Complete break card
        # ------------------------------------------

        card_html = (
            f'<div class="brk {esc(sev_class)}">'

            f'<div class="brk-head">'

            f'<span class="brk-id">'
            f'{esc(row.get("break_id"))}'
            f'</span>'

            f'<span>'
            f'{badge(severity)} '
            f'{badge(sla_status)}'
            f'</span>'

            f'</div>'

            f'<div class="brk-type">'
            f'{esc(str(row.get("exception_type", "")).replace("_", " "))}'
            f'</div>'

            f'{details_html}'

            f'{sla_bar_html}'

            f'</div>'
        )


        cards.append(
            card_html
        )


    return (
        '<div class="brk-grid">'
        + "".join(
            cards
        )
        + '</div>'
    )


def timeline(
    execution: dict,
    clearing: dict | None,
    trade_breaks: pd.DataFrame,
) -> str:

    exec_ts = (
        to_utc(
            execution.get(
                "timestamp"
            )
        )
    )


    resolved = (
        trade_breaks[
            "resolved_at"
        ]
    )


    events = [
        (
            "Executed",
            exec_ts,
            "",
        ),

        (
            "Cleared",
            (
                to_utc(
                    clearing.get(
                        "timestamp"
                    )
                )
                if clearing
                else None
            ),
            "",
        ),

        (
            "Break detected",
            to_utc(
                trade_breaks[
                    "detected_at"
                ]
                .min()
            ),
            "accent",
        ),

        (
            "First seen",
            to_utc(
                trade_breaks[
                    "first_seen_at"
                ]
                .min()
            ),
            "",
        ),

        (
            "Last seen",
            to_utc(
                trade_breaks[
                    "last_seen_at"
                ]
                .max()
            ),
            "",
        ),

        (
            "Resolved",
            (
                to_utc(
                    resolved.max()
                )
                if (
                    not resolved.empty
                    and
                    resolved.notna().all()
                )
                else None
            ),
            "",
        ),
    ]


    items = []


    for (
        label,
        ts,
        css,
    ) in sorted(
        (
            event
            for event
            in events
            if event[1]
            is not None
        ),
        key=lambda event: (
            event[1]
        ),
    ):

        delta = ""


        if (
            exec_ts
            is not None
            and
            ts
            != exec_ts
        ):

            delta = (
                '<span>'
                f'T+'
                f'{esc(fmt_duration((ts - exec_ts).total_seconds()))}'
                '</span>'
            )


        items.append(
            (
                f'<div class="tl-item {css}">'

                '<div class="tl-dot"></div>'

                f'<div class="tl-label">'
                f'{esc(label)}'
                f'</div>'

                f'<div class="tl-time">'
                f'{esc(fmt_ts(ts))}'
                f'{delta}'
                f'</div>'

                '</div>'
            )
        )


    for (
        label,
        ts,
        _,
    ) in events:

        if ts is None:

            note = (
                "No clearing record"
                if label == "Cleared"
                else "Pending"
            )


            items.append(
                (
                    '<div class="tl-item pending">'

                    '<div class="tl-dot"></div>'

                    f'<div class="tl-label">'
                    f'{esc(label)}'
                    f'</div>'

                    f'<div class="tl-time">'
                    f'{esc(note)}'
                    f'</div>'

                    '</div>'
                )
            )


    return (
        '<div class="tl">'
        f'{"".join(items)}'
        '</div>'
    )