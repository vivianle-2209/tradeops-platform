"""
SLA & Risk

Dashboard view for:
- SLA status
- affected notional
- severity/SLA relationship
- break ageing
- escalation queues
- exposure concentration

All data comes from the dashboard context created by dashboard/app.py.
"""

import pandas as pd
import streamlit as st

from tradeops_ui.charts import (
    PLOTLY_CONFIG,
    chart_card,
    fig_age_vs_severity,
    fig_exposure_by_group,
    fig_notional_by_sla,
    fig_severity_sla_matrix,
    fig_sla_distribution,
)

from tradeops_ui.components import (
    empty_state,
    page_title,
)

from tradeops_ui.data import (
    total_exposure, exposure_by_group,
    get_context,
)

from tradeops_ui.formatting import (
    fmt_money,
)

from tradeops_ui.tables import (
    breaks_table,
)

from tradeops_ui.theme import (
    BLACK,
    PINK,
)


# ==================================================
# Configuration
# ==================================================

SLA_TABLE_COLUMNS = [
    "break_id",
    "trade_id",
    "symbol",
    "exception_type",
    "severity",
    "severity_score",
    "sla_status",
    "age_minutes",
    "sla_minutes",
    "sla_remaining_minutes",
    "affected_notional",
    "detected_at",
]


CONCENTRATION_DIMENSIONS = {
    "Exception type":
        "exception_type",

    "Symbol":
        "symbol",

    "Venue":
        "venue",

    "Account":
        "account_exec",
}


# ==================================================
# Context
# ==================================================

ctx = get_context()

filtered = (
    ctx.filtered.copy()
)


# ==================================================
# Header
# ==================================================

page_title(
    "SLA & Risk",
    (
        "SLA ageing, escalation queues and "
        "exposure concentration for the current "
        "market and operational filter scope."
    ),
)


# ==================================================
# Empty scope protection
# ==================================================

if filtered.empty:

    empty_state(
        (
            "No trade breaks match the current "
            "Market Scope and operational filters."
        )
    )

    st.stop()


# ==================================================
# SLA charts
# ==================================================

left, right = st.columns(
    2,
    vertical_alignment="top",
)


with left:

    chart_card(
        "SLA status distribution",
        fig_sla_distribution(
            filtered
        ),
        key="sla_dist",
    )


with right:

    chart_card(
        "Affected notional by SLA status",
        fig_notional_by_sla(
            filtered
        ),
        key="sla_notional",
    )


left, right = st.columns(
    2,
    vertical_alignment="top",
)


with left:

    chart_card(
        "Severity × SLA matrix",
        fig_severity_sla_matrix(
            filtered
        ),
        key="sla_matrix",
        caption=(
            "Break count per cell"
        ),
    )


with right:

    chart_card(
        "Break age vs severity",
        fig_age_vs_severity(
            filtered
        ),
        key="sla_scatter",
        caption=(
            "Bubble size = affected notional"
        ),
    )


# ==================================================
# Risk by symbol
# ==================================================

with st.container(
    border=True
):

    st.markdown(
        "**Risk by symbol**"
    )

    st.caption(
        (
            "Operational risk concentration "
            "within the current scope"
        )
    )


    if (
        "symbol"
        not in filtered.columns
    ):

        empty_state(
            "Symbol data is unavailable."
        )

    else:

        working = (
            filtered.copy()
        )


        working[
            "affected_notional"
        ] = pd.to_numeric(
            working[
                "affected_notional"
            ],
            errors="coerce",
        ).fillna(0)


        working[
            "age_minutes"
        ] = pd.to_numeric(
            working[
                "age_minutes"
            ],
            errors="coerce",
        )


        symbol_summary = (
            working
            .groupby(
                "symbol",
                dropna=False,
            )
            .agg(
                breaks=(
                    "break_id",
                    "count",
                ),

                critical=(
                    "severity",
                    lambda values: (
                        values
                        .astype(str)
                        .eq(
                            "CRITICAL"
                        )
                        .sum()
                    ),
                ),

                high=(
                    "severity",
                    lambda values: (
                        values
                        .astype(str)
                        .eq(
                            "HIGH"
                        )
                        .sum()
                    ),
                ),

                breached=(
                    "sla_status",
                    lambda values: (
                        values
                        .astype(str)
                        .eq(
                            "BREACHED"
                        )
                        .sum()
                    ),
                ),

                at_risk=(
                    "sla_status",
                    lambda values: (
                        values
                        .astype(str)
                        .eq(
                            "AT_RISK"
                        )
                        .sum()
                    ),
                ),

                avg_age=(
                    "age_minutes",
                    "mean",
                ),

                affected_notional=(
                    "affected_notional",
                    "sum",
                ),
            )
            .reset_index()
        )


        symbol_summary[
            "symbol"
        ] = (
            symbol_summary[
                "symbol"
            ]
            .fillna(
                "UNKNOWN"
            )
            .astype(str)
        )


        symbol_summary = (
            symbol_summary
            .sort_values(
                [
                    "breached",
                    "critical",
                    "affected_notional",
                ],
                ascending=[
                    False,
                    False,
                    False,
                ],
            )
        )


        symbol_summary['affected_notional'] = symbol_summary['symbol'].map(exposure_by_group(working, 'symbol')).fillna(0)

        display_summary = (
            symbol_summary.rename(
                columns={
                    "symbol":
                        "Symbol",

                    "breaks":
                        "Breaks",

                    "critical":
                        "Critical",

                    "high":
                        "High",

                    "breached":
                        "Breached",

                    "at_risk":
                        "At Risk",

                    "avg_age":
                        "Avg Age (min)",

                    "affected_notional":
                        "Affected Notional",
                }
            )
        )


        st.dataframe(
            display_summary,
            hide_index=True,
            width="stretch",
            column_config={

                "Symbol":
                    st.column_config.TextColumn(
                        "Symbol",
                        width="small",
                    ),

                "Breaks":
                    st.column_config.NumberColumn(
                        "Breaks",
                        format="%d",
                    ),

                "Critical":
                    st.column_config.NumberColumn(
                        "Critical",
                        format="%d",
                    ),

                "High":
                    st.column_config.NumberColumn(
                        "High",
                        format="%d",
                    ),

                "Breached":
                    st.column_config.NumberColumn(
                        "Breached",
                        format="%d",
                    ),

                "At Risk":
                    st.column_config.NumberColumn(
                        "At Risk",
                        format="%d",
                    ),

                "Avg Age (min)":
                    st.column_config.NumberColumn(
                        "Avg Age (min)",
                        format="%.1f",
                    ),

                "Affected Notional":
                    st.column_config.NumberColumn(
                        "Affected Notional",
                        format="$%,.2f",
                    ),
            },
        )


# ==================================================
# SLA breach queue
# ==================================================

with st.container(
    border=True
):

    breached = (
        filtered[
            filtered[
                "sla_status"
            ]
            .astype(str)
            .eq(
                "BREACHED"
            )
        ]
        .copy()
    )


    if not breached.empty:

        breached = (
            breached
            .sort_values(
                [
                    "severity_score",
                    "age_minutes",
                ],
                ascending=[
                    False,
                    False,
                ],
                na_position="last",
            )
        )


    st.markdown(
        (
            f"**SLA breach queue** "
            f"· {len(breached):,}"
        )
    )

    st.caption(
        (
            "Escalation candidates, highest "
            "severity and oldest first"
        )
    )


    if breached.empty:

        empty_state(
            (
                "No SLA breaches in "
                "the current scope."
            )
        )

    else:

        breaks_table(
            breached,
            SLA_TABLE_COLUMNS,
            alt=(
                "SLA breach queue"
            ),
            key=(
                "sla_breach_table"
            ),
        )


# ==================================================
# Critical / High queue
# ==================================================

with st.container(
    border=True
):

    severe = (
        filtered[
            filtered[
                "severity"
            ]
            .astype(str)
            .isin(
                [
                    "CRITICAL",
                    "HIGH",
                ]
            )
        ]
        .copy()
    )


    if not severe.empty:

        if (
            "priority_rank"
            in severe.columns
        ):

            severe = (
                severe
                .sort_values(
                    "priority_rank",
                    na_position="last",
                )
            )


    st.markdown(
        (
            "**Critical and high severity incidents** "
            f"· {len(severe):,}"
        )
    )


    st.caption(
        (
            "Priority incidents requiring "
            "operational attention"
        )
    )


    if severe.empty:

        empty_state(
            (
                "No critical or high severity "
                "breaks in the current scope."
            )
        )

    else:

        breaks_table(
            severe,
            SLA_TABLE_COLUMNS,
            alt=(
                "Critical and high severity incidents"
            ),
            key=(
                "severe_table"
            ),
        )


# ==================================================
# Exposure concentration
# ==================================================

with st.container(
    border=True
):

    dims = {
        label: column
        for label, column
        in CONCENTRATION_DIMENSIONS.items()
        if column
        in filtered.columns
    }


    with st.container(
        horizontal=True,
        vertical_alignment="center",
    ):

        st.markdown(
            "**Exposure concentration**"
        )

        st.space(
            "stretch"
        )


        if not dims:

            dim_label = None

        else:

            default_dimension = (
                "Exception type"
                if "Exception type"
                in dims
                else next(
                    iter(
                        dims
                    )
                )
            )


            dim_label = (
                st.segmented_control(
                    "Group by",
                    list(
                        dims
                    ),
                    default=(
                        default_dimension
                    ),
                    required=True,
                    key="conc_dim",
                    label_visibility=(
                        "collapsed"
                    ),
                )
            )


        measure_label = (
            st.segmented_control(
                "Measure",
                [
                    "Affected",
                    "Gross",
                ],
                default="Affected",
                required=True,
                key="conc_measure",
                label_visibility=(
                    "collapsed"
                ),
                help=(
                    "Affected = mismatched notional; "
                    "Gross = full known trade notional"
                ),
            )
        )


    if not dims:

        empty_state(
            (
                "No concentration dimensions "
                "are available."
            )
        )

    else:

        gross = (
            measure_label
            == "Gross"
        )


        column = dims[
            dim_label
        ]


        measure = (
            "trade_exposure"
            if gross
            else "affected_notional"
        )


        if measure not in filtered.columns:

            empty_state(
                (
                    f"{measure} is unavailable "
                    "for the current dataset."
                )
            )

        else:

            exposure_values = (
                pd.to_numeric(
                    filtered[
                        measure
                    ],
                    errors="coerce",
                )
                .fillna(0)
            )


            total = total_exposure(filtered, measure)


            if total <= 0:

                empty_state(
                    (
                        "No exposure for this measure "
                        "in the current scope."
                    )
                )

            else:

                concentration_frame = (
                    filtered.copy()
                )


                concentration_frame[
                    measure
                ] = exposure_values


                grouped = exposure_by_group(concentration_frame, column, measure).sort_values(ascending=False)


                top3_share = (
                    grouped
                    .head(3)
                    .sum()
                    / total
                )


                st.caption(
                    (
                        f"Top 3 of {len(grouped):,} "
                        f"{dim_label.lower()} groups "
                        f"hold {top3_share:.0%} of "
                        f"{fmt_money(total)}"
                    )
                )


                st.plotly_chart(
                    fig_exposure_by_group(
                        concentration_frame,
                        column,
                        measure,
                        color=(
                            BLACK
                            if gross
                            else PINK
                        ),
                        top=12,
                    ),
                    theme=None,
                    config=PLOTLY_CONFIG,
                    width="stretch",
                    key=(
                        "sla_concentration"
                    ),
                )
