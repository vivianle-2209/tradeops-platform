import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tradeops_ui.charts import (
    fig_age_histogram,
    fig_breaks_by_type,
    fig_breaks_by_venue,
    fig_exposure_by_group,
    fig_severity_donut,
)

from tradeops_ui.components import (
    badge,
    empty_state,
    kpi_card,
    kpi_row,
    section_label,
    stat_strip,
)

from tradeops_ui.data import (
    total_exposure, exposure_by_group,
    get_context,
)

from tradeops_ui.formatting import (
    esc,
    fmt_duration,
    fmt_int,
    fmt_money,
    fmt_money_compact,
    fmt_trade_id,
)


# --------------------------------------------------
# Context
# --------------------------------------------------

ctx = get_context()

kpis = ctx.kpis
filtered = ctx.filtered

reconciliation = (
    ctx.reconciliation.copy()
)

scoped_breaks = (
    ctx.breaks.copy()
)


# --------------------------------------------------
# Scope label
# --------------------------------------------------

selected_symbols = (
    st.session_state.get(
        "f_symbol",
        [],
    )
    or []
)


if selected_symbols:

    scope_label = (
        ", ".join(
            selected_symbols
        )
    )

else:

    scope_label = (
        "all symbols"
    )


# --------------------------------------------------
# Trading Health
# --------------------------------------------------

section_label(
    "Trading health",
    scope_label,
)


kpi_row(
    [
        kpi_card(
            "Total trades",
            f"{kpis['total']:,}",
            "Ingested executions",
        ),

        kpi_card(
            "Matched trades",
            f"{kpis['matched']:,}",
            (
                f"{kpis['match_rate']:.1f}% "
                "match rate"
            ),
            progress=(
                kpis[
                    "match_rate"
                ]
                / 100
            ),
        ),

        kpi_card(
            "Broken trades",
            f"{kpis['broken']:,}",
            (
                f"{kpis['break_count']:,} "
                "exceptions raised"
            ),
        ),

        kpi_card(
            "Break rate",
            f"{kpis['break_rate']:.2f}%",
            "Broken / total",
            progress=(
                kpis[
                    "break_rate"
                ]
                / 100
            ),
        ),

        kpi_card(
            "Critical breaks",
            f"{kpis['critical']:,}",
            "Severity critical",
            alert=(
                kpis[
                    "critical"
                ]
                > 0
            ),
        ),

        kpi_card(
            "Affected notional",
            fmt_money_compact(
                kpis[
                    "affected"
                ]
            ),
            fmt_money(
                kpis[
                    "affected"
                ]
            ),
        ),
    ]
)


# --------------------------------------------------
# SLA & Operations KPIs
# --------------------------------------------------

section_label(
    "SLA & operations",
    "current scope",
)


kpi_row(
    [
        kpi_card(
            "SLA breached",
            f"{kpis['breached']:,}",
            (
                "Escalate now"
                if kpis[
                    "breached"
                ]
                else "None breached"
            ),
            alert=(
                kpis[
                    "breached"
                ]
                > 0
            ),
        ),

        kpi_card(
            "At risk",
            f"{kpis['at_risk']:,}",
            "≥75% of SLA consumed",
            alert=(
                kpis[
                    "at_risk"
                ]
                > 0
            ),
        ),

        kpi_card(
            "Avg break age",
            (
                f"{kpis['avg_age']:,.1f} "
                "min"
            ),
            "Open breaks",
        ),

        kpi_card(
            "Avg clearing latency",
            fmt_duration(
                kpis[
                    "avg_latency"
                ]
            ),
            "Execution → clearing",
        ),

        kpi_card(
            "Open breaks",
            f"{kpis['open']:,}",
            (
                f"of "
                f"{kpis['break_count']:,} "
                "exceptions"
            ),
            progress=(
                (
                    kpis[
                        "open"
                    ]
                    /
                    kpis[
                        "break_count"
                    ]
                )
                if kpis[
                    "break_count"
                ]
                else 0
            ),
        ),
    ]
)


# ==================================================
# Trading Activity by Symbol
# ==================================================

section_label(
    "Trading activity by symbol",
    "market scope",
)


# --------------------------------------------------
# Chart selector
# --------------------------------------------------

header_left, header_right = (
    st.columns(
        [
            3,
            2,
        ],
        vertical_alignment="bottom",
    )
)


with header_left:

    st.caption(
        (
            "Compare reconciliation volume and "
            "financial exposure across symbols."
        )
    )


with header_right:

    activity_view = (
        st.segmented_control(
            "Metric",
            [
                "Volume",
                "Affected Notional",
            ],
            default="Volume",
            key="overview_activity_metric",
            label_visibility="collapsed",
        )
    )


# --------------------------------------------------
# Volume view
# --------------------------------------------------

if (
    activity_view
    == "Volume"
):

    if (
        reconciliation.empty
        or
        "symbol"
        not in reconciliation.columns
    ):

        empty_state(
            "No trading activity is available "
            "for the current market scope."
        )

    else:

        activity = (
            reconciliation[
                [
                    "symbol",
                    "reconciliation_status",
                ]
            ]
            .copy()
        )


        activity[
            "symbol"
        ] = (
            activity[
                "symbol"
            ]
            .fillna(
                "UNKNOWN"
            )
            .astype(str)
        )


        grouped = (
            activity
            .groupby(
                [
                    "symbol",
                    "reconciliation_status",
                ]
            )
            .size()
            .unstack(
                fill_value=0
            )
        )


        for status_column in [
            "MATCHED",
            "BREAK",
        ]:

            if (
                status_column
                not in grouped.columns
            ):

                grouped[
                    status_column
                ] = 0


        grouped[
            "TOTAL"
        ] = (
            grouped[
                "MATCHED"
            ]
            +
            grouped[
                "BREAK"
            ]
        )


        grouped[
            "BREAK_RATE"
        ] = (
            grouped[
                "BREAK"
            ]
            /
            grouped[
                "TOTAL"
            ]
            .replace(
                0,
                pd.NA,
            )
            * 100
        ).fillna(0)


        grouped[
            "MATCH_RATE"
        ] = (
            grouped[
                "MATCHED"
            ]
            /
            grouped[
                "TOTAL"
            ]
            .replace(
                0,
                pd.NA,
            )
            * 100
        ).fillna(0)
        grouped = (
            grouped
            .sort_values(
                "TOTAL",
                ascending=False,
            )
        )


        fig_activity = (
            go.Figure()
        )


        fig_activity.add_trace(
            go.Bar(
                x=grouped.index,
                y=grouped[
                    "MATCHED"
                ],
                name="Matched",
                marker_color=(
                    "#171717"
                ),
                customdata=[
                    [
                        int(
                            grouped.loc[
                                symbol,
                                "TOTAL",
                            ]
                        ),
                        int(
                            grouped.loc[
                                symbol,
                                "BREAK",
                            ]
                        ),
                        float(
                            grouped.loc[
                                symbol,
                                "MATCH_RATE",
                            ]
                        ),
                        float(
                            grouped.loc[
                                symbol,
                                "BREAK_RATE",
                            ]
                        ),
                    ]
                    for symbol
                    in grouped.index
                ],
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Matched trades: %{y:,}<br>"
                    "Broken trades: %{customdata[1]:,}<br>"
                    "Total trades: %{customdata[0]:,}<br>"
                    "Match rate: %{customdata[2]:.2f}%<br>"
                    "Break rate: %{customdata[3]:.2f}%"
                    "<extra></extra>"
                ),
            )
        )


        fig_activity.add_trace(
            go.Bar(
                x=grouped.index,
                y=grouped[
                    "BREAK"
                ],
                name="Broken",
                marker_color=(
                    "#ff4da6"
                ),
                customdata=[
                    [
                        int(
                            grouped.loc[
                                symbol,
                                "TOTAL",
                            ]
                        ),
                        int(
                            grouped.loc[
                                symbol,
                                "MATCHED",
                            ]
                        ),
                        float(
                            grouped.loc[
                                symbol,
                                "MATCH_RATE",
                            ]
                        ),
                        float(
                            grouped.loc[
                                symbol,
                                "BREAK_RATE",
                            ]
                        ),
                    ]
                    for symbol
                    in grouped.index
                ],
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Broken trades: %{y:,}<br>"
                    "Matched trades: %{customdata[1]:,}<br>"
                    "Total trades: %{customdata[0]:,}<br>"
                    "Match rate: %{customdata[2]:.2f}%<br>"
                    "Break rate: %{customdata[3]:.2f}%"
                    "<extra></extra>"
                ),
            )
        )


        # Total trade count above each stack
        fig_activity.add_trace(
            go.Scatter(
                x=grouped.index,
                y=grouped[
                    "TOTAL"
                ],
                mode="text",
                text=[
                    f"{int(value):,}"
                    for value
                    in grouped[
                        "TOTAL"
                    ]
                ],
                textposition=(
                    "top center"
                ),
                showlegend=False,
                hoverinfo="skip",
            )
        )


        fig_activity.update_layout(
            barmode="stack",
            height=430,
            margin=dict(
                l=20,
                r=20,
                t=30,
                b=45,
            ),
            paper_bgcolor=(
                "rgba(0,0,0,0)"
            ),
            plot_bgcolor=(
                "rgba(0,0,0,0)"
            ),
            legend=dict(
                orientation="h",
                x=0,
                xanchor="left",
                y=1.08,
                yanchor="bottom",
            ),
            xaxis_title=None,
            yaxis_title="Trades",
            bargap=0.28,
        )


        fig_activity.update_xaxes(
            showgrid=False,
        )


        fig_activity.update_yaxes(
            gridcolor=(
                "rgba(0,0,0,0.08)"
            ),
            zeroline=False,
        )


        with st.container(
            border=True
        ):

            st.plotly_chart(
                fig_activity,
                width="stretch",
                config={
                    "displayModeBar": False,
                },
                key=(
                    "overview_symbol_volume"
                ),
            )


# --------------------------------------------------
# Affected Notional view
# --------------------------------------------------

else:

    if scoped_breaks.empty:

        empty_state(
            "No affected notional is available "
            "for the current market scope."
        )

    else:

        exposure = (
            scoped_breaks
            .copy()
        )


        exposure[
            "affected_notional"
        ] = (
            pd.to_numeric(
                exposure[
                    "affected_notional"
                ],
                errors="coerce",
            )
            .fillna(0)
        )


        exposure_by_symbol = exposure_by_group(exposure, 'symbol').sort_values(ascending=False)


        exposure_by_symbol.index = (
            exposure_by_symbol
            .index
            .fillna(
                "UNKNOWN"
            )
            .astype(str)
        )


        fig_exposure_symbol = (
            go.Figure()
        )


        fig_exposure_symbol.add_trace(
            go.Bar(
                x=(
                    exposure_by_symbol
                    .index
                ),
                y=(
                    exposure_by_symbol
                    .values
                ),
                marker_color=(
                    "#ff4da6"
                ),
                text=[
                    fmt_money_compact(
                        value
                    )
                    for value
                    in exposure_by_symbol
                    .values
                ],
                textposition=(
                    "outside"
                ),
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Affected notional: "
                    "$%{y:,.2f}"
                    "<extra></extra>"
                ),
            )
        )


        fig_exposure_symbol.update_layout(
            height=430,
            margin=dict(
                l=20,
                r=20,
                t=35,
                b=45,
            ),
            paper_bgcolor=(
                "rgba(0,0,0,0)"
            ),
            plot_bgcolor=(
                "rgba(0,0,0,0)"
            ),
            showlegend=False,
            xaxis_title=None,
            yaxis_title=(
                "Affected notional"
            ),
            bargap=0.32,
        )


        fig_exposure_symbol.update_xaxes(
            showgrid=False,
        )


        fig_exposure_symbol.update_yaxes(
            gridcolor=(
                "rgba(0,0,0,0.08)"
            ),
            tickprefix="$",
            zeroline=False,
        )


        with st.container(
            border=True
        ):

            st.plotly_chart(
                fig_exposure_symbol,
                width="stretch",
                config={
                    "displayModeBar": False,
                },
                key=(
                    "overview_symbol_exposure"
                ),
            )


# ==================================================
# Operational Summary
# ==================================================

section_label(
    "Operational summary",
    "current filter scope",
)


filtered_trade_count = (
    filtered[
        "trade_id"
    ]
    .nunique()
    if (
        not filtered.empty
        and
        "trade_id"
        in filtered.columns
    )
    else 0
)


scope_rate = (
    (
        filtered_trade_count
        / kpis[
            "total"
        ]
        * 100
    )
    if kpis[
        "total"
    ]
    else 0.0
)


scope_critical = (
    int(
        filtered[
            "severity"
        ]
        .eq(
            "CRITICAL"
        )
        .sum()
    )
    if not filtered.empty
    else 0
)


if (
    "clearing_latency_seconds"
    in filtered.columns
):

    scope_latency = (
        pd.to_numeric(
            filtered[
                "clearing_latency_seconds"
            ],
            errors="coerce",
        )
        .mean()
    )

else:

    scope_latency = float(
        "nan"
    )


scope_affected = total_exposure(filtered)


stat_strip(
    [
        (
            "Break coverage",
            f"{scope_rate:.2f}%",
            False,
        ),

        (
            "Critical incidents",
            f"{scope_critical:,}",
            (
                scope_critical
                > 0
            ),
        ),

        (
            "Avg clearing latency",
            fmt_duration(
                scope_latency
            ),
            False,
        ),

        (
            "Affected notional",
            fmt_money(
                scope_affected
            ),
            False,
        ),
    ]
)


# ==================================================
# Analytics cards
# ==================================================

section_label(
    "Exception analytics",
    "current filter scope",
)


CARD_HEIGHT = 530
FIG_HEIGHT = 390


# --------------------------------------------------
# Row 1
# --------------------------------------------------

left, right = st.columns(
    [
        3,
        2,
    ],
    vertical_alignment="top",
)


# Break type
with left:

    with st.container(
        border=True,
        height=CARD_HEIGHT,
    ):

        st.markdown(
            "**Breaks by exception type**"
        )

        st.caption(
            "Exception mix in the current scope"
        )


        fig_break_type = (
            fig_breaks_by_type(
                filtered
            )
        )


        if fig_break_type is not None:
            fig_break_type.update_layout(
                height=FIG_HEIGHT,
                margin=dict(
                    l=20,
                    r=20,
                    t=25,
                    b=45,
                ),
            )


        if fig_break_type is None:
            empty_state("No breaks match the current filters.")
        else:
            st.plotly_chart(
                fig_break_type,
                width="stretch",
                config={
                    "displayModeBar": False,
                },
                key="ov_by_type",
            )


# Severity donut
with right:

    with st.container(
        border=True,
        height=CARD_HEIGHT,
    ):

        st.markdown(
            "**Severity distribution**"
        )

        st.caption(
            "Current exception severity mix"
        )


        fig_severity = (
            fig_severity_donut(
                filtered
            )
        )


        if fig_severity is not None:
            fig_severity.update_traces(
                domain=dict(
                    x=[
                        0.18,
                        0.82,
                    ],
                    y=[
                        0.18,
                        0.95,
                    ],
                )
            )


        if fig_severity is not None:
            fig_severity.update_layout(
                height=FIG_HEIGHT,
                margin=dict(
                    l=15,
                    r=15,
                    t=15,
                    b=70,
                ),
                legend=dict(
                    orientation="h",
                    x=0.5,
                    xanchor="center",
                    y=-0.08,
                    yanchor="top",
                ),
            )


        if fig_severity is None:
            empty_state("No breaks match the current filters.")
        else:
            st.plotly_chart(
                fig_severity,
                width="stretch",
                config={
                    "displayModeBar": False,
                },
                key="ov_severity",
            )


# --------------------------------------------------
# Row 2
# --------------------------------------------------

left, right = st.columns(
    2,
    vertical_alignment="top",
)


# Venue
with left:

    with st.container(
        border=True,
        height=CARD_HEIGHT,
    ):

        st.markdown(
            "**Breaks by venue**"
        )

        st.caption(
            "Stacked by severity"
        )


        fig_venue = (
            fig_breaks_by_venue(
                filtered
            )
        )


        if fig_venue is not None:
            fig_venue.update_layout(
                height=(
                    FIG_HEIGHT
                    - 30
                ),
                margin=dict(
                    l=20,
                    r=20,
                    t=20,
                    b=80,
                ),
                paper_bgcolor=(
                    "rgba(0,0,0,0)"
                ),
                plot_bgcolor=(
                    "rgba(0,0,0,0)"
                ),
                legend=dict(
                    orientation="h",
                    x=0.5,
                    xanchor="center",
                    y=-0.12,
                    yanchor="top",
                ),
            )


        if fig_venue is None:
            empty_state("No breaks match the current filters.")
        else:
            st.plotly_chart(
                fig_venue,
                width="stretch",
                config={
                    "displayModeBar": False,
                },
                key="ov_venue",
            )


# Age distribution
with right:

    with st.container(
        border=True,
        height=CARD_HEIGHT,
    ):

        st.markdown(
            "**Break age distribution**"
        )

        st.caption(
            "Open-break age profile"
        )


        fig_age = (
            fig_age_histogram(
                filtered
            )
        )


        if fig_age is not None:
            fig_age.update_layout(
                height=(
                    FIG_HEIGHT
                    - 30
                ),
                margin=dict(
                    l=20,
                    r=20,
                    t=20,
                    b=80,
                ),
                paper_bgcolor=(
                    "rgba(0,0,0,0)"
                ),
                plot_bgcolor=(
                    "rgba(0,0,0,0)"
                ),
            )


        if fig_age is None:
            empty_state("No breaks match the current filters.")
        else:
            st.plotly_chart(
                fig_age,
                width="stretch",
                config={
                    "displayModeBar": False,
                },
                key="ov_age",
            )


# ==================================================
# Exposure + Top Risks
# ==================================================

left, right = st.columns(
    [
        3,
        2,
    ],
    vertical_alignment="top",
)


with left:

    with st.container(
        border=True
    ):

        st.markdown(
            "**Financial exposure by exception type**"
        )

        st.caption(
            (
                "Affected notional and share "
                "of total"
            )
        )


        if (
            filtered.empty
            or
            filtered[
                "affected_notional"
            ]
            .fillna(0)
            .sum()
            <= 0
        ):

            empty_state(
                "No affected notional in "
                "the current scope."
            )

        else:

            fig_exposure = (
                fig_exposure_by_group(
                    filtered,
                    "exception_type",
                )
            )


            st.plotly_chart(
                fig_exposure,
                width="stretch",
                config={
                    "displayModeBar": False,
                },
                key="ov_exposure",
            )


with right:

    with st.container(
        border=True
    ):

        st.markdown(
            "**Top 5 highest-risk breaks**"
        )

        st.caption(
            "By priority rank"
        )


        if filtered.empty:

            empty_state(
                "No breaks match the current filters."
            )

        else:

            top = (
                filtered
                .sort_values(
                    [
                        "priority_rank",
                        "severity_score",
                    ],
                    ascending=[
                        True,
                        False,
                    ],
                    na_position="last",
                )
                .head(5)
            )


            rows = "".join(
                (
                    '<div class="risk-row">'

                    f'<div class="risk-rank">'
                    f'{esc(fmt_int(row["priority_rank"]))}'
                    f'</div>'

                    '<div class="risk-main">'

                    f'<b title="{esc(row["trade_id"])}">'
                    f'{esc(fmt_trade_id(row["trade_id"]))}</b>'

                    '<div>'

                    f'{esc(str(row.get("symbol", "")))}'
                    ' · '

                    f'{esc(str(row["exception_type"]).replace("_", " "))}'

                    '</div>'

                    '</div>'

                    '<div class="risk-side">'

                    f'{esc(fmt_money(row["affected_notional"]))}'

                    '<div>'

                    f'{badge(row["severity"])}'
                    f'{badge(row["sla_status"])}'

                    '</div>'

                    '</div>'

                    '</div>'
                )

                for _, row
                in top.iterrows()
            )


            st.html(
                f'<div class="risk-list">'
                f'{rows}'
                f'</div>'
            )
