"""Plotly chart builders sharing one house style (white, black, pink, grey)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from tradeops_ui.components import empty_state
from tradeops_ui.formatting import fmt_money, fmt_money_compact, ordered
from tradeops_ui.theme import (
    BLACK, BORDER, GREY_MID, GREY_TEXT, PINK, PINK_LIGHT,
    SEVERITY_COLORS, SEVERITY_ORDER, SLA_COLORS, SLA_ORDER,
)

PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}


# --------------------------------------------------
# Styling
# --------------------------------------------------

def _plain_arrays(fig: go.Figure) -> None:
    """
    Plotly >= 6 serialises numpy arrays as base64 typed arrays, which some
    front-end builds mis-read (e.g. every bar rendering at full length).
    Plain lists are unambiguous.
    """
    for trace in fig.data:
        for attr in ("x", "y", "z", "values", "customdata", "text"):
            if attr in trace and isinstance(trace[attr], np.ndarray):
                trace[attr] = trace[attr].tolist()
        marker = getattr(trace, "marker", None)
        if marker is not None and "size" in marker and isinstance(marker.size, np.ndarray):
            marker.size = marker.size.tolist()


def style_fig(fig: go.Figure, height: int = 300, legend: bool = False) -> go.Figure:
    """House style: white canvas, black text, minimal grid, compact margins."""
    _plain_arrays(fig)
    fig.update_layout(
        height=height,
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Inter, -apple-system, Segoe UI, sans-serif", size=12, color=BLACK),
        margin=dict(l=8, r=16, t=8, b=8),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(size=11, color="#333333"), bgcolor="rgba(0,0,0,0)", title_text=""),
        hoverlabel=dict(bgcolor=BLACK, font_color="#FFFFFF", font_size=12, bordercolor=BLACK),
        bargap=0.35,
    )
    axis_style = dict(zeroline=False, linecolor=BORDER, ticks="", automargin=True,
                      tickfont=dict(color="#333333", size=11), title_font=dict(size=11, color=GREY_TEXT))
    fig.update_xaxes(showgrid=False, **axis_style)
    fig.update_yaxes(showgrid=True, gridcolor="#F2F2F2", **axis_style)
    return fig


def chart_card(title: str, fig: go.Figure | None, key: str, caption: str | None = None,
               empty_message: str = "No breaks match the current filters.") -> None:
    """
    Bordered card with a title, optional caption and a Plotly chart.
    The stable `key` keeps the chart mounted across reruns, so filters and
    auto-refresh update it in place instead of re-creating it (which made
    the page jump to the top).
    """
    with st.container(border=True):
        st.markdown(f"**{title}**")
        if caption:
            st.caption(caption)
        if fig is None:
            empty_state(empty_message)
        else:
            st.plotly_chart(fig, theme=None, config=PLOTLY_CONFIG, width="stretch", key=key, alt=title)


# --------------------------------------------------
# Builders
# --------------------------------------------------

def counts_by(df: pd.DataFrame, column: str) -> pd.DataFrame:
    counts = df[column].fillna("UNKNOWN").astype(str).value_counts().reset_index()
    counts.columns = [column, "count"]
    return counts


def hbar(data: pd.DataFrame, category: str, value: str, color: str, label: str,
         hover_value: str) -> go.Figure:
    """Sorted horizontal bar chart; `label` is the column printed beside each bar."""
    data = data.sort_values(value, ascending=True)
    peak = float(data[value].max()) if len(data) else 0.0
    fig = go.Figure(go.Bar(
        x=data[value].astype(float).tolist(),
        y=data[category].astype(str).str.replace("_", " ").tolist(),
        orientation="h",
        marker=dict(color=color),
        text=data[label].tolist(),
        textposition="outside",
        cliponaxis=False,
        textfont=dict(size=11, color="#333333"),
        hovertemplate=f"%{{y}}<br>{hover_value}<extra></extra>",
    ))
    fig = style_fig(fig, height=max(240, 34 * len(data) + 40))
    # Headroom on the right so the outside labels are never clipped.
    fig.update_xaxes(showticklabels=False, range=[0, peak * 1.22 if peak > 0 else 1])
    fig.update_yaxes(showgrid=False, ticksuffix="  ", tickfont=dict(size=11.5, color=BLACK))
    return fig


def fig_breaks_by_type(df: pd.DataFrame) -> go.Figure | None:
    if df.empty:
        return None
    data = counts_by(df, "exception_type")
    data["label"] = data["count"].map(lambda v: f"{v:,}")
    return hbar(data, "exception_type", "count", BLACK, "label", "%{x:,.0f} breaks")


def fig_severity_donut(df: pd.DataFrame) -> go.Figure | None:
    if df.empty:
        return None
    data = counts_by(df, "severity").set_index("severity").reindex(
        ordered(df["severity"], SEVERITY_ORDER)).reset_index()
    fig = go.Figure(go.Pie(
        labels=data["severity"].tolist(), values=data["count"].astype(int).tolist(),
        hole=0.64, sort=False, direction="clockwise",
        marker=dict(colors=[SEVERITY_COLORS.get(s, GREY_MID) for s in data["severity"]],
                    line=dict(color="#FFFFFF", width=2)),
        textinfo="none", hovertemplate="%{label}<br>%{value:,} breaks · %{percent}<extra></extra>",
    ))
    fig.add_annotation(
        text=f"<b>{int(data['count'].sum()):,}</b><br><span style='font-size:11px;color:{GREY_TEXT}'>breaks</span>",
        showarrow=False, font=dict(size=22, color=BLACK),
    )
    fig = style_fig(fig, height=280, legend=True)
    fig.update_layout(legend=dict(orientation="v", y=0.5, yanchor="middle", x=1.0, xanchor="left"))
    return fig


def fig_breaks_by_venue(df: pd.DataFrame) -> go.Figure | None:
    if df.empty:
        return None
    data = (df.assign(venue=df["venue"].astype(str))
              .groupby(["venue", "severity"], dropna=False).size().reset_index(name="count"))
    venue_order = data.groupby("venue")["count"].sum().sort_values(ascending=False).index.tolist()
    fig = px.bar(data, x="venue", y="count", color="severity",
                 category_orders={"venue": venue_order, "severity": SEVERITY_ORDER},
                 color_discrete_map=SEVERITY_COLORS)
    fig.update_traces(marker_line_color="#FFFFFF", marker_line_width=1,
                      hovertemplate="Venue %{x}<br>%{y:,} breaks<extra></extra>")
    fig = style_fig(fig, height=280, legend=True)
    fig.update_layout(barmode="stack")
    fig.update_xaxes(title_text="Venue", type="category")
    fig.update_yaxes(title_text="Breaks")
    return fig


def fig_age_histogram(df: pd.DataFrame) -> go.Figure | None:
    ages = df["age_minutes"].dropna()
    if ages.empty:
        return None
    fig = go.Figure(go.Histogram(
        x=ages.astype(float).tolist(), nbinsx=20,
        marker=dict(color=BLACK, line=dict(color="#FFFFFF", width=1)),
        hovertemplate="%{x} min<br>%{y:,} breaks<extra></extra>",
    ))
    fig = style_fig(fig, height=280)
    fig.update_xaxes(title_text="Age (minutes)")
    fig.update_yaxes(title_text="Breaks")
    return fig


def fig_exposure_by_group(df: pd.DataFrame, column: str, measure: str = "affected_notional",
                          color: str = PINK, top: int | None = None) -> go.Figure | None:
    """Exposure per group with share of total; zero-exposure groups are omitted."""
    total = df[measure].fillna(0).sum() if not df.empty else 0
    if total <= 0:
        return None
    data = (df.assign(**{column: df[column].fillna("UNKNOWN").astype(str)})
              .groupby(column)[measure].sum().reset_index())
    data = data[data[measure] > 0].sort_values(measure, ascending=False)
    if top:
        data = data.head(top)
    data["label"] = data[measure].map(lambda v: f"{fmt_money_compact(v)} · {v / total:.0%}")
    return hbar(data, column, measure, color, "label", "$%{x:,.2f}")


def _by_sla_status(df: pd.DataFrame, value: str | None) -> pd.DataFrame:
    """Count (value=None) or sum `value` per SLA status, in canonical order."""
    status = df["sla_status"].fillna("UNKNOWN").astype(str)
    data = (status.value_counts() if value is None else df[value].fillna(0).groupby(status).sum())
    data = data.rename("v").reset_index()
    data.columns = ["sla_status", "v"]
    data["order"] = data["sla_status"].map({s: i for i, s in enumerate(SLA_ORDER)}).fillna(99)
    return data.sort_values("order")


def _sla_bar(data: pd.DataFrame, labels: list[str], hover: str) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=data["sla_status"].str.replace("_", " ").tolist(),
        y=data["v"].astype(float).tolist(),
        marker=dict(color=[SLA_COLORS.get(s, GREY_MID) for s in data["sla_status"]],
                    line=dict(color=BLACK, width=0.5)),
        text=labels, textposition="outside", cliponaxis=False,
        hovertemplate=f"%{{x}}<br>{hover}<extra></extra>",
    ))
    fig = style_fig(fig, height=280)
    peak = float(data["v"].max()) if len(data) else 0.0
    fig.update_yaxes(range=[0, peak * 1.2 if peak > 0 else 1])
    return fig


def fig_sla_distribution(df: pd.DataFrame) -> go.Figure | None:
    if df.empty:
        return None
    data = _by_sla_status(df, None)
    fig = _sla_bar(data, [f"{int(v):,}" for v in data["v"]], "%{y:,.0f} breaks")
    fig.update_yaxes(title_text="Breaks")
    return fig


def fig_notional_by_sla(df: pd.DataFrame) -> go.Figure | None:
    if df.empty:
        return None
    data = _by_sla_status(df, "affected_notional")
    fig = _sla_bar(data, [fmt_money_compact(v) for v in data["v"]], "$%{y:,.2f}")
    fig.update_yaxes(title_text="Affected notional", tickprefix="$", tickformat="~s")
    return fig


def fig_severity_sla_matrix(df: pd.DataFrame) -> go.Figure | None:
    if df.empty:
        return None
    rows = ordered(df["severity"], SEVERITY_ORDER)
    present = set(df["sla_status"].dropna())
    cols = [s for s in SLA_ORDER if s in {"BREACHED", "AT_RISK", "WITHIN_SLA"} or s in present]
    matrix = pd.crosstab(df["severity"], df["sla_status"]).reindex(index=rows, columns=cols, fill_value=0)
    z = matrix.to_numpy()
    zmax = max(int(z.max()), 1)
    x_labels = [c.replace("_", " ") for c in cols]
    fig = go.Figure(go.Heatmap(
        z=z.tolist(), x=x_labels, y=rows, zmin=0, zmax=zmax, xgap=3, ygap=3, showscale=False,
        colorscale=[[0, "#FAFAFA"], [0.35, PINK_LIGHT], [0.7, PINK], [1, BLACK]],
        hovertemplate="%{y} · %{x}<br>%{z:,} breaks<extra></extra>",
    ))
    for i, row in enumerate(rows):
        for j, label in enumerate(x_labels):
            value = int(z[i, j])
            fig.add_annotation(x=label, y=row, text=f"{value:,}", showarrow=False,
                               font=dict(size=13, color="#FFFFFF" if value / zmax > 0.6 else BLACK))
    fig = style_fig(fig, height=280)
    fig.update_yaxes(autorange="reversed", showgrid=False, ticksuffix="  ")
    fig.update_xaxes(side="top")
    return fig


def fig_age_vs_severity(df: pd.DataFrame) -> go.Figure | None:
    data = df.dropna(subset=["age_minutes", "severity_score"])
    if data.empty:
        return None
    notional = data["affected_notional"].fillna(0).clip(lower=0)
    peak = notional.max()
    data = data.assign(
        bubble=8 + (np.sqrt(notional / peak) * 22 if peak > 0 else 0),
        notional_fmt=notional.map(fmt_money),
    )
    fig = px.scatter(
        data, x="age_minutes", y="severity_score", color="severity", size="bubble", size_max=30,
        category_orders={"severity": SEVERITY_ORDER}, color_discrete_map=SEVERITY_COLORS,
        custom_data=["trade_id", "exception_type", "notional_fmt", "sla_status"],
    )
    fig.update_traces(
        marker=dict(line=dict(color=BLACK, width=0.6), opacity=0.9),
        hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>Age %{x:.1f} min · Score %{y}"
                      "<br>%{customdata[2]} · %{customdata[3]}<extra></extra>",
    )
    fig = style_fig(fig, height=300, legend=True)
    fig.update_xaxes(title_text="Break age (minutes)", showgrid=True, gridcolor="#F2F2F2")
    fig.update_yaxes(title_text="Severity score")
    return fig
