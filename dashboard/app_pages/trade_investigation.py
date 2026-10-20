"""Trade investigation: execution vs clearing comparison for one trade."""

import streamlit as st

from tradeops_ui.components import empty_state, page_title, section_label
from tradeops_ui.data import get_context
from tradeops_ui.formatting import fmt_duration
from tradeops_ui.investigation import (
    break_cards, comparison_table, kv_panel, resolve_records, timeline, trade_options, trade_summary_card,
)

ctx = get_context()

page_title("Trade investigation", "Execution vs clearing comparison, detected breaks and operational timeline.")

options = trade_options(ctx.filtered)
if options.empty:
    empty_state("No trades match the current filters.")
    st.stop()

# ---- Trade selection ---------------------------------------------------------
# `focus_trade` survives page switches (e.g. "Investigate" from the queue);
# the selectbox's own state is dropped whenever this page isn't shown.

trade_ids = options.index.astype(str).tolist()
focus = st.session_state.get("focus_trade")
if focus in trade_ids:
    st.session_state["trade_select"] = focus
elif st.session_state.get("trade_select") not in trade_ids:
    st.session_state.pop("trade_select", None)

trade_id = st.selectbox(
    "Trade", trade_ids, key="trade_select",
    format_func=lambda t: f"{t}  ·  {options.at[t, 'severity']}  ·  {options.at[t, 'types'].replace('_', ' ')}",
    help=f"{len(trade_ids):,} broken trades in the current filter scope, most urgent first",
)
st.session_state["focus_trade"] = trade_id

trade_breaks = ctx.breaks[ctx.breaks["trade_id"].astype(str) == trade_id]
execution, clearing_records, exec_df, clear_df, error = resolve_records(trade_id, trade_breaks, ctx.version)
if error:
    st.warning(f"Source records unavailable, showing reconciled values instead. ({error})",
               icon=":material/warning:")

st.html(trade_summary_card(trade_id, execution, trade_breaks))

# ---- Execution vs clearing + timeline ----------------------------------------

left, right = st.columns([3, 2])
with left:
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown("**Execution vs clearing**")
            st.space("stretch")
            clearing = None
            if len(clearing_records) > 1:
                st.badge(f"{len(clearing_records)} clearing records", color="primary",
                         icon=":material/content_copy:")
                ids = [str(r.get("clearing_id", i)) for i, r in enumerate(clearing_records)]
                chosen = st.segmented_control("Clearing record", ids, default=ids[0], required=True,
                                              key=f"clr_pick_{trade_id}", label_visibility="collapsed")
                clearing = clearing_records[ids.index(chosen or ids[0])]
            elif clearing_records:
                clearing = clearing_records[0]
            else:
                st.badge("No clearing record", color="primary", icon=":material/link_off:")

        table, mismatches = comparison_table(execution, clearing)
        st.html(table)
        if clearing is None:
            st.caption("Clearing record missing — every field is unmatched.")
        elif mismatches:
            st.caption(f"{mismatches} field{'s' if mismatches != 1 else ''} differ between execution and clearing.")
        else:
            st.caption("Economic fields agree; see detected breaks for status or timing exceptions.")

    with st.container(border=True):
        exec_col, clear_col = st.columns(2)
        with exec_col:
            st.markdown("**Execution record**")
            st.html(kv_panel([
                ("Order ID", execution.get("order_id")),
                ("Trader", execution.get("trader_id")),
                ("Venue", execution.get("venue")),
                ("Market trade ID", execution.get("market_trade_id")),
                ("Executed (UTC)", execution.get("timestamp")),
            ]))
        with clear_col:
            st.markdown("**Clearing record**")
            if clearing:
                st.html(kv_panel([
                    ("Clearing ID", clearing.get("clearing_id")),
                    ("Clearing status", clearing.get("clearing_status")),
                    ("Cleared (UTC)", clearing.get("timestamp")),
                    ("Clearing latency", fmt_duration(trade_breaks["clearing_latency_seconds"].max())),
                ]))
            else:
                empty_state("No clearing record received.")

with right:
    with st.container(border=True):
        st.markdown("**Operational timeline**")
        st.caption("UTC · T+ relative to execution")
        st.html(timeline(execution, clearing, trade_breaks))

# ---- Breaks on this trade ------------------------------------------------------

section_label("Detected breaks", f"{len(trade_breaks)} on this trade")
st.html(break_cards(trade_breaks))

with st.expander("Raw source records", icon=":material/table_view:"):
    st.caption("Execution")
    st.dataframe(exec_df, hide_index=True, width="stretch", alt="Raw execution record")
    st.caption("Clearing")
    st.dataframe(clear_df, hide_index=True, width="stretch", alt="Raw clearing records")
