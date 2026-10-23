"""
Operations Performance

Historical TradeOps analytics built from persistent
pipeline snapshots stored in DuckDB.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys


# ==================================================
# Import path
# ==================================================

DASHBOARD_DIR = (
    Path(__file__)
    .resolve()
    .parents[1]
)

if str(DASHBOARD_DIR) not in sys.path:

    sys.path.insert(
        0,
        str(DASHBOARD_DIR),
    )


# ==================================================
# Imports
# ==================================================

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tradeops_ui import data as db

from tradeops_ui.formatting import (
    fmt_money,
    fmt_money_compact,
)

from tradeops_ui.theme import (
    BLACK,
    BORDER,
    GREY_TEXT,
    PINK,
    PINK_LIGHT,
    SEVERITY_COLORS,
    SEVERITY_ORDER,
)


# ==================================================
# Configuration
# ==================================================

TIMEZONE_OPTIONS = {
    "New York": "America/New_York",
    "UTC": "UTC",
    "Sydney": "Australia/Sydney",
}


METRIC_COLUMNS = {
    "Trades": "total_trades",
    "Breaks": "broken_trades",
    "Break Rate": "break_rate",
    "Affected Notional": "affected_notional",
}


METRIC_LABELS = {
    "Trades": "Trades",
    "Breaks": "Breaks",
    "Break Rate": "Break Rate (%)",
    "Affected Notional": "Affected Notional",
}


# ==================================================
# Utility functions
# ==================================================

def load_history():
    try:
        return db.load_history_runs(db.db_version()), pd.DataFrame(), pd.DataFrame()
    except Exception as exc:
        st.error(f'Historical data is unavailable: {exc}')
        st.stop()



def prepare_timestamp(
    frame: pd.DataFrame,
    column: str = "snapshot_at",
) -> pd.DataFrame:
    """
    Parse snapshot timestamps as UTC.
    """

    frame = frame.copy()

    if (
        not frame.empty
        and column in frame.columns
    ):

        frame[column] = pd.to_datetime(
            frame[column],
            errors="coerce",
            utc=True,
        )

    return frame


def localise_snapshots(
    frame: pd.DataFrame,
    timezone_name: str,
) -> pd.DataFrame:
    """
    Add local snapshot timestamp used by the
    historical analytics page.
    """

    frame = frame.copy()

    if (
        frame.empty
        or "snapshot_at"
        not in frame.columns
    ):

        return frame

    frame[
        "snapshot_local"
    ] = (
        frame[
            "snapshot_at"
        ]
        .dt.tz_convert(
            timezone_name
        )
    )

    return frame


def filter_date_range(
    frame: pd.DataFrame,
    from_date: date,
    to_date: date,
) -> pd.DataFrame:
    """
    Filter using the user's selected local date.
    """

    if (
        frame.empty
        or "snapshot_local"
        not in frame.columns
    ):

        return frame.copy()

    local_dates = (
        frame[
            "snapshot_local"
        ]
        .dt.date
    )

    mask = (
        (local_dates >= from_date)
        &
        (local_dates <= to_date)
    )

    return (
        frame[
            mask
        ]
        .copy()
    )


def filter_symbols(
    frame: pd.DataFrame,
    selected_symbols: list[str],
) -> pd.DataFrame:
    """
    Restrict a historical dataset to selected
    symbols where symbol exists.
    """

    if (
        frame.empty
        or not selected_symbols
        or "symbol"
        not in frame.columns
    ):

        return frame.copy()

    return (
        frame[
            frame[
                "symbol"
            ]
            .astype(str)
            .isin(
                selected_symbols
            )
        ]
        .copy()
    )


def format_metric(
    value: float,
    metric: str,
) -> str:

    if pd.isna(value):

        return "—"

    if metric == "Affected Notional":

        return fmt_money_compact(
            float(value)
        )

    if metric == "Break Rate":

        return (
            f"{float(value):.2f}%"
        )

    return (
        f"{int(round(float(value))):,}"
    )


def calculate_change(
    current: float,
    previous: float,
) -> float | None:
    """
    Percentage change between current and
    previous comparable periods.
    """

    if (
        pd.isna(previous)
        or float(previous) == 0
    ):

        return None

    return (
        (
            float(current)
            - float(previous)
        )
        /
        abs(
            float(previous)
        )
        * 100
    )


def aggregate_break_rate(frame, bucket_column):
    return db.aggregate_break_rate(frame, bucket_column)



def aggregate_metric(frame, bucket_column, metric):
    return db.aggregate_metric(frame, bucket_column, metric)



def make_trend_chart(
    data: pd.DataFrame,
    x_column: str,
    metric: str,
    timezone_label: str,
) -> go.Figure:
    """
    Build the main historical activity trend.
    """

    metric_column = (
        METRIC_COLUMNS[
            metric
        ]
    )

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=(
                data[
                    x_column
                ]
            ),
            y=(
                data[
                    metric_column
                ]
            ),
            mode="lines+markers",
            line=dict(
                color=BLACK,
                width=2,
            ),
            marker=dict(
                size=7,
                color=PINK,
                line=dict(
                    color=BLACK,
                    width=0.7,
                ),
            ),
            fill="tozeroy",
            fillcolor=(
                "rgba(255,77,166,0.08)"
            ),
            hovertemplate=(
                "<b>%{x}</b><br>"
                +
                (
                    "Affected notional: "
                    "$%{y:,.2f}"
                    if metric
                    == "Affected Notional"
                    else
                    (
                        "Break rate: "
                        "%{y:.2f}%"
                        if metric
                        == "Break Rate"
                        else
                        f"{metric}: "
                        "%{y:,.0f}"
                    )
                )
                +
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        height=380,
        margin=dict(
            l=20,
            r=20,
            t=20,
            b=55,
        ),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        showlegend=False,
        hovermode="x unified",
        font=dict(
            family=(
                "Inter, -apple-system, "
                "Segoe UI, sans-serif"
            ),
            color=BLACK,
        ),
    )

    fig.update_xaxes(
        title_text=(
            f"Time ({timezone_label})"
        ),
        title_standoff=20,
        showgrid=False,
        automargin=True,
        linecolor=BORDER,
    )

    fig.update_yaxes(
        title_text=(
            METRIC_LABELS[
                metric
            ]
        ),
        gridcolor="#F1F1F1",
        zeroline=False,
        automargin=True,
    )

    if (
        metric
        == "Affected Notional"
    ):

        fig.update_yaxes(
            tickprefix="$",
            tickformat="~s",
        )

    return fig


def make_intraday_chart(
    data: pd.DataFrame,
    metric: str,
    timezone_label: str,
) -> go.Figure:
    """
    Show operational activity by time of day.
    """

    metric_column = (
        METRIC_COLUMNS[
            metric
        ]
    )

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=data[
                "time_of_day"
            ],
            y=data[
                metric_column
            ],
            marker_color=BLACK,
            marker_line_color=(
                "#FFFFFF"
            ),
            marker_line_width=1,
            hovertemplate=(
                "<b>%{x}</b><br>"
                +
                (
                    "Affected notional: "
                    "$%{y:,.2f}"
                    if metric
                    == "Affected Notional"
                    else
                    (
                        "Break rate: "
                        "%{y:.2f}%"
                        if metric
                        == "Break Rate"
                        else
                        f"{metric}: "
                        "%{y:,.0f}"
                    )
                )
                +
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        height=360,
        margin=dict(
            l=20,
            r=20,
            t=20,
            b=65,
        ),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        showlegend=False,
        bargap=0.25,
        font=dict(
            family=(
                "Inter, -apple-system, "
                "Segoe UI, sans-serif"
            ),
            color=BLACK,
        ),
    )

    fig.update_xaxes(
        title_text=(
            f"Time of day "
            f"({timezone_label})"
        ),
        title_standoff=22,
        showgrid=False,
        automargin=True,
        tickangle=-45,
    )

    fig.update_yaxes(
        title_text=(
            METRIC_LABELS[
                metric
            ]
        ),
        gridcolor="#F1F1F1",
        zeroline=False,
    )

    if (
        metric
        == "Affected Notional"
    ):

        fig.update_yaxes(
            tickprefix="$",
            tickformat="~s",
        )

    return fig


def build_activity_calendar(
    runs_frame: pd.DataFrame,
    metric: str,
) -> go.Figure | None:
    """
    GitHub-style daily operations activity
    heatmap.

    Columns = week
    Rows = weekday
    """

    if runs_frame.empty:

        return None

    frame = (
        runs_frame.copy()
    )

    frame[
        "calendar_date"
    ] = (
        frame[
            "snapshot_local"
        ]
        .dt.normalize()
    )

    if metric == "Break Rate":

        daily = (
            aggregate_break_rate(
                frame,
                "calendar_date",
            )
        )

    else:

        metric_column = (
            METRIC_COLUMNS[
                metric
            ]
        )

        daily = (
            frame
            .groupby(
                "calendar_date",
                as_index=False,
            )[
                metric_column
            ]
            .sum()
        )

    if daily.empty:

        return None

    metric_column = (
        METRIC_COLUMNS[
            metric
        ]
    )

    start_date = (
        daily[
            "calendar_date"
        ]
        .min()
    )

    end_date = (
        daily[
            "calendar_date"
        ]
        .max()
    )

    all_dates = pd.DataFrame(
        {
            "calendar_date":
                pd.date_range(
                    start=start_date,
                    end=end_date,
                    freq="D",
                    tz=(
                        start_date.tz
                        if hasattr(
                            start_date,
                            "tz"
                        )
                        else None
                    ),
                )
        }
    )

    daily = (
        all_dates.merge(
            daily,
            on="calendar_date",
            how="left",
        )
    )

    daily[
        metric_column
    ] = (
        daily[
            metric_column
        ]
        .fillna(0)
    )

    daily[
        "weekday"
    ] = (
        daily[
            "calendar_date"
        ]
        .dt.weekday
    )

    daily[
        "week_start"
    ] = (
        daily[
            "calendar_date"
        ]
        -
        pd.to_timedelta(
            daily[
                "weekday"
            ],
            unit="D",
        )
    )

    week_values = sorted(
        daily[
            "week_start"
        ]
        .drop_duplicates()
        .tolist()
    )

    week_lookup = {
        value: index
        for index, value
        in enumerate(
            week_values
        )
    }

    daily[
        "week_number"
    ] = (
        daily[
            "week_start"
        ]
        .map(
            week_lookup
        )
    )

    z = np.zeros(
        (
            7,
            max(
                len(
                    week_values
                ),
                1,
            ),
        )
    )

    customdata = np.empty(
        z.shape,
        dtype=object,
    )

    customdata[:] = ""

    for _, row in (
        daily.iterrows()
    ):

        weekday = int(
            row[
                "weekday"
            ]
        )

        week_number = int(
            row[
                "week_number"
            ]
        )

        z[
            weekday,
            week_number,
        ] = float(
            row[
                metric_column
            ]
        )

        date_text = (
            row[
                "calendar_date"
            ]
            .strftime(
                "%d/%m/%Y"
            )
        )

        if (
            metric
            == "Affected Notional"
        ):

            value_text = fmt_money(
                row[
                    metric_column
                ]
            )

        elif (
            metric
            == "Break Rate"
        ):

            value_text = (
                f"{row[metric_column]:.2f}%"
            )

        else:

            value_text = (
                f"{row[metric_column]:,.0f}"
            )

        customdata[
            weekday,
            week_number,
        ] = (
            f"{date_text}"
            f"<br>{metric}: "
            f"{value_text}"
        )

    weekday_names = [
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
        "Sun",
    ]

    x_labels = [
        value.strftime(
            "%d %b"
        )
        for value
        in week_values
    ]

    fig = go.Figure(
        go.Heatmap(
            z=z.tolist(),
            x=x_labels,
            y=weekday_names,
            customdata=(
                customdata.tolist()
            ),
            hovertemplate=(
                "%{customdata}"
                "<extra></extra>"
            ),
            colorscale=[
                [
                    0,
                    "#F5F5F5",
                ],
                [
                    0.25,
                    "#FCE2EF",
                ],
                [
                    0.55,
                    PINK_LIGHT,
                ],
                [
                    0.8,
                    PINK,
                ],
                [
                    1,
                    BLACK,
                ],
            ],
            xgap=4,
            ygap=4,
            showscale=True,
            colorbar=dict(
                title=(
                    "More"
                ),
                thickness=10,
                len=0.5,
            ),
        )
    )

    fig.update_layout(
        height=300,
        margin=dict(
            l=45,
            r=60,
            t=10,
            b=45,
        ),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(
            family=(
                "Inter, -apple-system, "
                "Segoe UI, sans-serif"
            ),
            color=BLACK,
        ),
    )

    fig.update_xaxes(
        title_text=None,
        showgrid=False,
        side="top",
    )

    fig.update_yaxes(
        title_text=None,
        showgrid=False,
        autorange="reversed",
    )

    return fig


def severity_history_chart(breaks_frame: pd.DataFrame) -> go.Figure | None:
    if breaks_frame.empty or 'severity' not in breaks_frame.columns:
        return None
    severity_data = breaks_frame.copy()
    fig = go.Figure()
    for severity in SEVERITY_ORDER:
        part = severity_data[severity_data['severity'].astype(str).eq(severity)]
        if part.empty:
            continue
        fig.add_trace(go.Scatter(x=part['date'], y=part['breaks'], mode='lines+markers', name=severity, line=dict(color=SEVERITY_COLORS.get(severity, '#999999'), width=2), marker=dict(size=6), hovertemplate=f'<b>{severity}</b><br>%{{x|%d/%m/%Y}}<br>%{{y:,}} breaks<extra></extra>'))
    fig.update_layout(height=360, margin=dict(l=20, r=20, t=15, b=55), paper_bgcolor='#FFFFFF', plot_bgcolor='#FFFFFF', legend=dict(orientation='h', y=1.08, x=0), hovermode='x unified')
    fig.update_xaxes(title_text='Date', title_standoff=20, showgrid=False)
    fig.update_yaxes(title_text='Breaks', gridcolor='#F1F1F1', zeroline=False)
    return fig


# ==================================================
# Load data
# ==================================================

runs, reconciliation, breaks = (
    load_history()
)


runs = prepare_timestamp(
    runs
)

reconciliation = prepare_timestamp(
    reconciliation
)

breaks = prepare_timestamp(
    breaks
)


# ==================================================
# Page header
# ==================================================

st.markdown(
    "# Operations Performance"
)

st.caption(
    (
        "Historical trading-operations performance, "
        "reconciliation trends, intraday activity "
        "and pipeline snapshot analysis."
    )
)


# ==================================================
# No history
# ==================================================

if runs.empty:

    st.info(
        (
            "Historical operational snapshots will "
            "appear after the next successful "
            "TradeOps pipeline run."
        ),
        icon=":material/history:",
    )

    st.caption(
        (
            "The platform previously stored only "
            "the latest operational snapshot. "
            "History starts accumulating after "
            "the historical tables are deployed."
        )
    )

    st.stop()


# ==================================================
# Time zone
# ==================================================

control_left, control_right = (
    st.columns(
        [
            3,
            2,
        ],
        vertical_alignment="bottom",
    )
)


with control_left:

    timezone_label = (
        st.segmented_control(
            "Time zone",
            list(
                TIMEZONE_OPTIONS
            ),
            default="New York",
            required=True,
            key=(
                "history_timezone"
            ),
        )
    )


with control_right:

    st.caption(
        (
            "New York is recommended for analysing "
            "US market-hours operational activity."
        )
    )


timezone_name = (
    TIMEZONE_OPTIONS[
        timezone_label
    ]
)


runs = localise_snapshots(
    runs,
    timezone_name,
)

reconciliation = (
    localise_snapshots(
        reconciliation,
        timezone_name,
    )
)

breaks = localise_snapshots(
    breaks,
    timezone_name,
)


# ==================================================
# Date range
# ==================================================

available_start = (
    runs[
        "snapshot_local"
    ]
    .min()
    .date()
)

available_end = (
    runs[
        "snapshot_local"
    ]
    .max()
    .date()
)


st.markdown(
    "### Date Range"
)


date_left, spacer, date_right = (
    st.columns(
        [
            1,
            0.08,
            1,
        ],
        vertical_alignment="bottom",
    )
)


with date_left:

    from_date = st.date_input(
        "From",
        value=available_start,
        min_value=available_start,
        max_value=available_end,
        format="DD/MM/YYYY",
        key=(
            "history_from_date"
        ),
    )


with spacer:

    st.markdown(
        """
        <div style="
            text-align:center;
            padding-bottom:0.7rem;
            font-size:1.25rem;
            opacity:0.45;
        ">
            —
        </div>
        """,
        unsafe_allow_html=True,
    )


with date_right:

    to_date = st.date_input(
        "To",
        value=available_end,
        min_value=available_start,
        max_value=available_end,
        format="DD/MM/YYYY",
        key=(
            "history_to_date"
        ),
    )


if from_date > to_date:

    st.error(
        (
            "The From date must be earlier than "
            "or equal to the To date."
        )
    )

    st.stop()


# ==================================================
# Apply date range
# ==================================================

runs_filtered = (
    filter_date_range(
        runs,
        from_date,
        to_date,
    )
)

reconciliation_filtered = pd.DataFrame()

breaks_filtered = (
    filter_date_range(
        breaks,
        from_date,
        to_date,
    )
)


if runs_filtered.empty:

    st.warning(
        (
            "No historical pipeline runs exist "
            "inside the selected date range."
        )
    )

    st.stop()


# ==================================================
# Historical symbol scope
# ==================================================

historical_symbols = db.load_history_symbols(db.db_version(), from_date, to_date, timezone_name)


selected_symbols = (
    st.multiselect(
        "Historical symbols",
        historical_symbols,
        placeholder=(
            "All symbols"
        ),
        key=(
            "history_symbols"
        ),
    )
)


runs = localise_snapshots(prepare_timestamp(db.load_history_runs(db.db_version(), symbols=tuple(selected_symbols), timezone_name=timezone_name)), timezone_name)
runs_filtered = localise_snapshots(prepare_timestamp(db.load_history_runs(db.db_version(), from_date, to_date, tuple(selected_symbols), timezone_name)), timezone_name)

breaks_filtered = db.load_history_severity(db.db_version(), from_date, to_date, tuple(selected_symbols), timezone_name)


# ==================================================
# Historical summary
# ==================================================

st.divider()

st.markdown(
    "### Historical Summary"
)


latest_run = (
    runs_filtered
    .sort_values(
        "snapshot_at"
    )
    .iloc[-1]
)


summary1, summary2, summary3, summary4, summary5 = (
    st.columns(5)
)


with summary1:

    st.metric(
        "Pipeline Runs",
        (
            f"{runs_filtered['snapshot_id'].nunique():,}"
        ),
    )


with summary2:

    st.metric(
        "Latest Trades",
        (
            f"{int(latest_run['total_trades']):,}"
        ),
    )


with summary3:

    st.metric(
        "Latest Breaks",
        (
            f"{int(latest_run['broken_trades']):,}"
        ),
    )


with summary4:

    st.metric(
        "Latest Break Rate",
        (
            f"{float(latest_run['break_rate']):.2f}%"
        ),
    )


with summary5:

    st.metric(
        "Latest Exposure",
        fmt_money_compact(
            latest_run[
                "affected_notional"
            ]
        ),
    )


# ==================================================
# Operational Activity Trend
# ==================================================

st.divider()

st.markdown(
    "### Operational Activity Trend"
)

st.caption(
    (
        "Analyse operational activity across "
        "the selected historical period."
    )
)


metric_col, granularity_col = (
    st.columns(2)
)


with metric_col:

    metric = (
        st.segmented_control(
            "Metric",
            [
                "Trades",
                "Breaks",
                "Break Rate",
                "Affected Notional",
            ],
            default="Trades",
            required=True,
            key="history_metric",
        )
    )


with granularity_col:

    time_granularity = (
        st.segmented_control(
            "Time analysis",
            [
                "Daily",
                "Hourly",
                "30-minute",
            ],
            default="Daily",
            required=True,
            key=(
                "history_granularity"
            ),
        )
    )


trend_data = db.load_history_trend(db.db_version(), from_date, to_date, tuple(selected_symbols), metric, time_granularity, timezone_name)

metric_column = (
    METRIC_COLUMNS[
        metric
    ]
)


# ==================================================
# Current vs previous period
# ==================================================

current_value = float(
    trend_data[
        metric_column
    ]
    .sum()
    if (
        metric
        != "Break Rate"
    )
    else (
        aggregate_break_rate(
            runs_filtered.assign(
                period="current"
            ),
            "period",
        )[
            "break_rate"
        ]
        .iloc[0]
    )
)


selected_days = (
    to_date
    - from_date
).days + 1


previous_end = (
    from_date
    - pd.Timedelta(
        days=1
    )
)


previous_start = (
    previous_end
    - pd.Timedelta(
        days=(
            selected_days
            - 1
        )
    )
)


previous_runs = (
    filter_date_range(
        runs,
        previous_start.date()
        if hasattr(
            previous_start,
            "date",
        )
        else previous_start,
        previous_end.date()
        if hasattr(
            previous_end,
            "date",
        )
        else previous_end,
    )
)


if previous_runs.empty:

    previous_value = np.nan

else:

    if metric == "Break Rate":

        previous_value = float(
            aggregate_break_rate(
                previous_runs.assign(
                    period="previous"
                ),
                "period",
            )[
                "break_rate"
            ]
            .iloc[0]
        )

    else:

        previous_value = float(
            previous_runs[
                metric_column
            ]
            .sum()
        )


change = calculate_change(
    current_value,
    previous_value,
)


trend_kpi_left, trend_kpi_right = (
    st.columns(
        [
            1,
            4,
        ]
    )
)


with trend_kpi_left:

    delta_text = (
        f"{change:+.1f}% vs prior period"
        if change is not None
        else None
    )

    st.metric(
        metric,
        format_metric(
            current_value,
            metric,
        ),
        delta=delta_text,
    )


with trend_kpi_right:

    st.plotly_chart(
        make_trend_chart(
            trend_data,
            "time_bucket",
            metric,
            timezone_label,
        ),
        width="stretch",
        config={
            "displayModeBar": False,
        },
        key=(
            "historical_trend"
        ),
    )


# ==================================================
# Intraday Operations
# ==================================================

st.divider()

st.markdown(
    "### Intraday Operations"
)

st.caption(
    (
        "Analyse when operational activity occurs "
        "within the trading day."
    )
)


intraday_data = db.load_history_trend(db.db_version(), from_date, to_date, tuple(selected_symbols), metric, 'Intraday', timezone_name)

st.plotly_chart(
    make_intraday_chart(
        intraday_data,
        metric,
        timezone_label,
    ),
    width="stretch",
    config={
        "displayModeBar": False,
    },
    key=(
        "historical_intraday"
    ),
)


# ==================================================
# Operations Activity Calendar
# ==================================================

st.divider()

calendar_header_left, calendar_header_right = (
    st.columns(
        [
            3,
            2,
        ],
        vertical_alignment="bottom",
    )
)


with calendar_header_left:

    st.markdown(
        "### Operations Activity Calendar"
    )

    st.caption(
        (
            "Daily operational activity intensity "
            "across the selected period."
        )
    )


with calendar_header_right:

    calendar_metric = (
        st.segmented_control(
            "Calendar metric",
            [
                "Trades",
                "Breaks",
                "Break Rate",
                "Affected Notional",
            ],
            default="Breaks",
            required=True,
            key=(
                "history_calendar_metric"
            ),
            label_visibility="collapsed",
        )
    )


calendar_fig = (
    build_activity_calendar(
        runs_filtered,
        calendar_metric,
    )
)


if calendar_fig is None:

    st.info(
        "No activity calendar data is available."
    )

else:

    st.plotly_chart(
        calendar_fig,
        width="stretch",
        config={
            "displayModeBar": False,
        },
        key=(
            "history_calendar"
        ),
    )


# ==================================================
# Historical Severity
# ==================================================

st.divider()

st.markdown(
    "### Break Severity History"
)

st.caption(
    (
        "Historical break observations by "
        "severity across pipeline snapshots."
    )
)


severity_fig = (
    severity_history_chart(
        breaks_filtered
    )
)


if severity_fig is None:

    st.info(
        (
            "No historical break severity "
            "data exists for this period."
        )
    )

else:

    st.plotly_chart(
        severity_fig,
        width="stretch",
        config={
            "displayModeBar": False,
        },
        key=(
            "history_severity"
        ),
    )


# ==================================================
# Snapshot Explorer
# ==================================================

st.divider()

st.markdown(
    "### Snapshot Explorer"
)

st.caption(
    (
        "Inspect the reconciliation and exception "
        "state captured by any historical "
        "pipeline run."
    )
)


snapshot_options = (
    runs_filtered[
        [
            "snapshot_id",
            "snapshot_local",
        ]
    ]
    .drop_duplicates()
    .sort_values(
        "snapshot_local",
        ascending=False,
    )
)


snapshot_labels = {
    (
        row[
            "snapshot_local"
        ]
        .strftime(
            "%d/%m/%Y %H:%M:%S"
        )
        +
        f" {timezone_label}"
    ):
        row[
            "snapshot_id"
        ]

    for _, row
    in snapshot_options.iterrows()
}


selected_label = (
    st.selectbox(
        "Pipeline snapshot",
        list(
            snapshot_labels
        ),
        key=(
            "history_snapshot"
        ),
    )
)


selected_snapshot = (
    snapshot_labels[
        selected_label
    ]
)


run_row = (
    runs[
        runs[
            "snapshot_id"
        ]
        .eq(
            selected_snapshot
        )
    ]
    .iloc[0]
)


snapshot_reconciliation, snapshot_breaks = db.load_history_observations(db.db_version(), selected_snapshot, tuple(selected_symbols))




snapshot_symbols = []


if (
    "symbol"
    in snapshot_reconciliation.columns
):

    snapshot_symbols = sorted(
        snapshot_reconciliation[
            "symbol"
        ]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )


st.caption(
    (
        "Symbols captured: "
        +
        (
            ", ".join(
                snapshot_symbols
            )
            if snapshot_symbols
            else "None"
        )
    )
)


snap1, snap2, snap3, snap4, snap5 = (
    st.columns(5)
)


with snap1:

    st.metric(
        "Trades",
        (
            f"{int(run_row['total_trades']):,}"
        ),
    )


with snap2:

    st.metric(
        "Matched",
        (
            f"{int(run_row['matched_trades']):,}"
        ),
    )


with snap3:

    st.metric(
        "Broken",
        (
            f"{int(run_row['broken_trades']):,}"
        ),
    )


with snap4:

    st.metric(
        "Break Rate",
        (
            f"{float(run_row['break_rate']):.2f}%"
        ),
    )


with snap5:

    st.metric(
        "Symbols",
        (
            f"{int(run_row['symbol_count']):,}"
        ),
    )


recon_tab, breaks_tab = (
    st.tabs(
        [
            "Reconciliation",
            "Breaks",
        ]
    )
)


# ==================================================
# Snapshot reconciliation
# ==================================================

with recon_tab:

    if snapshot_reconciliation.empty:

        st.info(
            (
                "No reconciliation records "
                "exist for this snapshot."
            )
        )

    else:

        reconciliation_columns = [
            column
            for column in [
                "trade_id",
                "symbol",
                "execution_timestamp",
                "quantity_exec",
                "price_exec",
                "side_exec",
                "account_exec",
                "venue",
                "clearing_status",
                "clearing_latency_seconds",
                "reconciliation_status",
            ]
            if column
            in snapshot_reconciliation.columns
        ]

        st.dataframe(
            (
                snapshot_reconciliation[
                    reconciliation_columns
                ]
                if reconciliation_columns
                else snapshot_reconciliation
            ),
            width="stretch",
            hide_index=True,
        )


# ==================================================
# Snapshot breaks
# ==================================================

with breaks_tab:

    if snapshot_breaks.empty:

        st.success(
            (
                "No breaks were observed in "
                "this pipeline snapshot."
            )
        )

    else:

        break_columns = [
            column
            for column in [
                "break_id",
                "trade_id",
                "symbol",
                "exception_type",
                "severity",
                "severity_score",
                "sla_status",
                "break_status",
                "age_minutes",
                "affected_notional",
                "first_seen_at",
                "last_seen_at",
            ]
            if column
            in snapshot_breaks.columns
        ]

        st.dataframe(
            (
                snapshot_breaks[
                    break_columns
                ]
                if break_columns
                else snapshot_breaks
            ),
            width="stretch",
            hide_index=True,
        )


# ==================================================
# Methodology
# ==================================================

st.divider()

with st.expander(
    "About historical operations data"
):

    st.markdown(
        """
Historical Operations is based on **pipeline snapshots**.

Each successful market-data pipeline run records:

- pipeline-level operating metrics
- reconciliation results
- trade-break observations
- timestamp of the snapshot

The current dashboard pages continue to represent the
**latest operational state**, while this page analyses
how that state has changed over time.

Because ingestion windows may overlap, historical
snapshot totals should be interpreted as **operational
observations by pipeline run**, rather than as one
deduplicated consolidated market tape.

No-data runs before the first trade do not create a snapshot. Afterward, snapshots
observe durable operational state; repeated open trades are observations, not new volume.
        """
    )