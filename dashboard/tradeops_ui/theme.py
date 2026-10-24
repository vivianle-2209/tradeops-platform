"""Palette, canonical orderings and the CSS for custom HTML components.

Base colours and fonts live in .streamlit/config.toml; APP_CSS only styles
the custom HTML (header, KPI cards, badges, investigation panels).
"""

BLACK = "#111111"
CARD = "#171717"
PINK = "#FF4FA3"
PINK_LIGHT = "#FFD6EA"
GREY_TEXT = "#666666"
GREY_MID = "#999999"
BORDER = "#E8E8E8"

SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
SLA_ORDER = ["BREACHED", "AT_RISK", "WITHIN_SLA", "UNKNOWN", "CLOSED"]

SEVERITY_COLORS = {
    "CRITICAL": BLACK,
    "HIGH": PINK,
    "MEDIUM": PINK_LIGHT,
    "LOW": "#D4D4D4",
}
SLA_COLORS = {
    "BREACHED": BLACK,
    "AT_RISK": PINK,
    "WITHIN_SLA": "#D4D4D4",
    "UNKNOWN": BORDER,
    "CLOSED": GREY_MID,
}


APP_CSS = f"""
<style>
.to-header {{
  display:flex; justify-content:space-between; align-items:center; gap:16px;
  flex-wrap:wrap; padding:2px 0 14px; border-bottom:1px solid {BORDER};
}}
.to-brand {{ display:flex; align-items:center; gap:12px; }}
.to-logo {{
  width:38px; height:38px; border-radius:10px; background:{BLACK}; color:{PINK};
  display:grid; place-items:center; font-weight:800; font-size:15px; letter-spacing:-.02em;
}}
.to-title {{ font-size:20px; font-weight:800; color:{BLACK}; line-height:1.1; letter-spacing:-.01em; }}
.to-sub {{ font-size:12.5px; color:{GREY_TEXT}; margin-top:2px; }}
.to-meta {{ display:flex; gap:8px; flex-wrap:wrap; align-items:center; }}

.chip {{
  display:inline-flex; align-items:center; gap:6px; padding:5px 11px; border-radius:999px;
  border:1px solid {BORDER}; background:#FFFFFF; color:#333333; font-size:12px;
  font-variant-numeric:tabular-nums; white-space:nowrap;
}}
.chip b {{ color:{BLACK}; font-weight:700; }}
.chip.live {{ border-color:#FFB3D6; background:#FFF2F8; color:#B5126A; font-weight:700; letter-spacing:.04em; }}
.chip.warn {{ border-color:{PINK}; color:#B5126A; }}
.dot {{ width:7px; height:7px; border-radius:50%; background:{PINK}; display:inline-block; }}
.dot.pulse {{ animation:to-pulse 1.6s ease-in-out infinite; }}
.dot.ok {{ background:{BLACK}; }}
.dot.idle {{ background:{GREY_MID}; }}
@keyframes to-pulse {{
  0% {{ box-shadow:0 0 0 0 rgba(255,79,163,.55); }}
  70% {{ box-shadow:0 0 0 7px rgba(255,79,163,0); }}
  100% {{ box-shadow:0 0 0 0 rgba(255,79,163,0); }}
}}

.section-label {{
  display:flex; align-items:baseline; gap:10px; margin:6px 0 -4px;
  font-size:11px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; color:{BLACK};
}}
.section-label span {{ font-weight:500; letter-spacing:0; text-transform:none; color:{GREY_MID}; font-size:12px; }}

.page-title {{ font-size:18px; font-weight:800; color:{BLACK}; letter-spacing:-.01em; margin-top:4px; }}
.page-title span {{ display:block; font-size:12.5px; font-weight:500; color:{GREY_TEXT}; margin-top:2px; }}

.kpi-grid {{ display:grid; grid-template-columns:repeat(var(--cols), minmax(0,1fr)); gap:12px; }}
@media (max-width:1200px) {{ .kpi-grid {{ grid-template-columns:repeat(3, minmax(0,1fr)); }} }}
@media (max-width:640px)  {{ .kpi-grid {{ grid-template-columns:repeat(2, minmax(0,1fr)); }} }}
.kpi {{
  position:relative; overflow:hidden; background:{CARD}; border:1px solid #232323; border-radius:12px;
  padding:14px 16px 13px; min-height:112px; display:flex; flex-direction:column; justify-content:space-between;
}}
.kpi.alert::before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:3px; background:{PINK}; }}
.kpi-label {{ color:#A3A3A3; font-size:11px; font-weight:600; letter-spacing:.08em; text-transform:uppercase; }}
.kpi-value {{
  color:#FFFFFF; font-size:26px; font-weight:700; letter-spacing:-.02em; line-height:1.15; margin-top:8px;
  font-variant-numeric:tabular-nums; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}}
.kpi.alert .kpi-value {{ color:{PINK}; }}
.kpi-foot {{ color:#8C8C8C; font-size:12px; margin-top:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.kpi-bar {{ height:3px; border-radius:2px; background:#2C2C2C; margin-top:9px; overflow:hidden; }}
.kpi-bar > span {{ display:block; height:100%; background:{PINK}; }}

.stat-strip {{
  display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); border:1px solid {BORDER};
  border-radius:12px; overflow:hidden; background:#FFFFFF;
}}
@media (max-width:900px) {{ .stat-strip {{ grid-template-columns:repeat(2, minmax(0,1fr)); }} }}
.stat {{ padding:12px 16px; border-right:1px solid {BORDER}; }}
.stat:last-child {{ border-right:none; }}
.stat-label {{ font-size:11px; color:{GREY_TEXT}; letter-spacing:.06em; text-transform:uppercase; font-weight:600; }}
.stat-value {{ font-size:20px; font-weight:700; color:{BLACK}; margin-top:4px; font-variant-numeric:tabular-nums; }}
.stat-value.hot {{ color:#D81B7A; }}

.bdg {{
  display:inline-block; padding:2px 8px; border-radius:6px; font-size:10.5px; font-weight:700;
  letter-spacing:.04em; line-height:1.6; white-space:nowrap; border:1px solid transparent;
}}
.bdg-critical {{ background:{BLACK}; color:#FFFFFF; }}
.bdg-high {{ background:{PINK}; color:#FFFFFF; }}
.bdg-medium {{ background:{PINK_LIGHT}; color:#7A1048; }}
.bdg-low, .bdg-within_sla, .bdg-match, .bdg-open {{ background:#F2F2F2; color:#555555; }}
.bdg-breached {{ background:{BLACK}; color:{PINK}; }}
.bdg-at_risk {{ background:{PINK_LIGHT}; color:#7A1048; }}
.bdg-closed, .bdg-unknown, .bdg-resolved {{ background:#FFFFFF; color:{GREY_TEXT}; border-color:{BORDER}; }}
.bdg-mismatch {{ background:{PINK}; color:#FFFFFF; }}
.bdg-missing {{ background:{BLACK}; color:#FFFFFF; }}

.risk-list {{ display:flex; flex-direction:column; }}
.risk-row {{
  display:grid; grid-template-columns:28px minmax(0,1fr) auto; gap:12px; align-items:center;
  padding:10px 2px; border-bottom:1px solid #F0F0F0;
}}
.risk-row:last-child {{ border-bottom:none; }}
.risk-rank {{
  width:26px; height:26px; border-radius:7px; background:{BLACK}; color:#FFFFFF; display:grid;
  place-items:center; font-size:12px; font-weight:700;
}}
.risk-main {{ min-width:0; overflow:hidden; }}
.risk-main b {{ display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; color:{BLACK}; }}
.risk-main div {{ font-size:12px; color:{GREY_TEXT}; margin-top:2px; }}
.risk-side {{ text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; font-size:13px; font-weight:700; color:{BLACK}; }}
.risk-side div {{ margin-top:4px; display:flex; gap:4px; justify-content:flex-end; }}

.trade-card {{ background:{CARD}; border-radius:14px; padding:18px 20px; color:#FFFFFF; }}
.trade-top {{ display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; }}
.trade-id {{ font-size:22px; font-weight:800; letter-spacing:-.01em; }}
.trade-id span {{ color:#8C8C8C; font-size:12px; font-weight:600; letter-spacing:.1em; margin-right:8px; }}
.trade-badges {{ display:flex; gap:6px; flex-wrap:wrap; }}
.trade-grid {{
  display:grid; grid-template-columns:repeat(auto-fit, minmax(120px, 1fr)); gap:14px 18px;
  margin-top:16px; padding-top:14px; border-top:1px solid #2A2A2A;
}}
.trade-grid .k {{ font-size:10.5px; color:#8C8C8C; letter-spacing:.08em; text-transform:uppercase; font-weight:600; }}
.trade-grid .v {{ font-size:15px; font-weight:600; margin-top:3px; font-variant-numeric:tabular-nums; }}
.trade-grid .v.hot {{ color:{PINK}; }}

.cmp {{ width:100%; border-collapse:collapse; font-size:13px; }}
.cmp th {{
  text-align:left; font-size:10.5px; letter-spacing:.08em; text-transform:uppercase; color:{GREY_TEXT};
  font-weight:700; padding:8px 12px; border-bottom:1px solid {BORDER};
}}
.cmp td {{ padding:10px 12px; border-bottom:1px solid #F2F2F2; font-variant-numeric:tabular-nums; color:{BLACK}; }}
.cmp td.f {{ font-weight:600; }}
.cmp td.d {{ color:{GREY_TEXT}; }}
.cmp tr.diff td {{ background:#FFF3F9; }}
.cmp tr.diff td.f {{ box-shadow:inset 3px 0 0 {PINK}; }}
.cmp tr.diff td.d {{ color:#B5126A; font-weight:700; }}

.kv {{ display:grid; grid-template-columns:auto 1fr; gap:6px 16px; font-size:13px; }}
.kv .k {{ color:{GREY_TEXT}; }}
.kv .v {{ color:{BLACK}; font-weight:600; text-align:right; font-variant-numeric:tabular-nums; word-break:break-all; }}

.brk-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(270px, 1fr)); gap:12px; }}
.brk {{ border:1px solid {BORDER}; border-radius:12px; padding:14px 16px; background:#FFFFFF; }}
.brk.sev-critical {{ border-top:3px solid {BLACK}; }}
.brk.sev-high {{ border-top:3px solid {PINK}; }}
.brk-head {{ display:flex; justify-content:space-between; align-items:center; gap:8px; }}
.brk-id {{ font-size:12px; color:{GREY_TEXT}; font-weight:600; font-variant-numeric:tabular-nums; }}
.brk-type {{ font-size:14px; font-weight:700; color:{BLACK}; margin:8px 0 10px; }}
.brk .kv {{ font-size:12.5px; }}
.sla-bar {{ height:4px; border-radius:2px; background:#F0F0F0; margin-top:12px; overflow:hidden; }}
.sla-bar > span {{ display:block; height:100%; }}

.tl {{ position:relative; padding-left:22px; }}
.tl::before {{ content:""; position:absolute; left:6px; top:6px; bottom:6px; width:2px; background:{BORDER}; }}
.tl-item {{ position:relative; padding:0 0 16px; }}
.tl-item:last-child {{ padding-bottom:0; }}
.tl-dot {{
  position:absolute; left:-21px; top:3px; width:12px; height:12px; border-radius:50%;
  background:{BLACK}; border:2px solid #FFFFFF; box-shadow:0 0 0 1px {BLACK};
}}
.tl-item.accent .tl-dot {{ background:{PINK}; box-shadow:0 0 0 1px {PINK}; }}
.tl-item.pending .tl-dot {{ background:#FFFFFF; box-shadow:0 0 0 1px #BBBBBB; }}
.tl-label {{ font-size:12.5px; font-weight:700; color:{BLACK}; }}
.tl-time {{ font-size:12.5px; color:#333333; font-variant-numeric:tabular-nums; margin-top:1px; }}
.tl-time span {{ color:{GREY_MID}; margin-left:6px; }}
.tl-item.pending .tl-label, .tl-item.pending .tl-time {{ color:{GREY_MID}; }}

.empty {{
  border:1px dashed #D9D9D9; border-radius:12px; padding:22px; text-align:center;
  color:{GREY_TEXT}; font-size:13px; background:#FCFCFC;
}}

.sb-brand {{ display:flex; align-items:center; gap:10px; margin-bottom:14px; }}
.sb-brand .to-logo {{ background:{PINK}; color:{BLACK}; width:34px; height:34px; font-size:14px; }}
.sb-name {{ color:#FFFFFF; font-size:17px; font-weight:800; line-height:1.1; }}
.sb-tag {{ color:#8C8C8C; font-size:11px; letter-spacing:.08em; text-transform:uppercase; margin-top:2px; }}
.sb-status {{ border:1px solid #2A2A2A; border-radius:10px; padding:10px 12px; background:#171717; }}
.sb-row {{ display:flex; justify-content:space-between; align-items:center; font-size:12px; padding:3px 0; }}
.sb-row .k {{ color:#8C8C8C; }}
.sb-row .v {{ color:#F2F2F2; font-weight:600; display:inline-flex; align-items:center; gap:6px; font-variant-numeric:tabular-nums; }}
.sb-row .v.hot {{ color:{PINK}; }}

/* ---- Sidebar filter widgets ------------------------------------------- */

/* Pills: pink outline, solid pink when selected. */
.st-key-f_severity button, .st-key-f_sla button, .st-key-f_status button {{
  background:transparent; border:1px solid rgba(255,79,163,.55); color:#FF8CC4; font-weight:600;
}}
.st-key-f_severity button:hover, .st-key-f_sla button:hover, .st-key-f_status button:hover {{
  border-color:{PINK}; color:{PINK}; background:rgba(255,79,163,.10);
}}
.st-key-f_severity button[data-testid$="Active"], .st-key-f_sla button[data-testid$="Active"],
.st-key-f_status button[data-testid$="Active"] {{
  background:{PINK}; border-color:{PINK}; color:{BLACK};
}}
.st-key-f_severity button *, .st-key-f_sla button *, .st-key-f_status button * {{ color:inherit; }}

/* Select boxes in the sidebar: white control, dark text. */
section[data-testid="stSidebar"] [data-baseweb="select"] > div {{
  background:#FFFFFF; border-color:#FFFFFF; color:{BLACK};
}}
section[data-testid="stSidebar"] [data-baseweb="select"] input {{ color:{BLACK}; caret-color:{PINK}; }}
section[data-testid="stSidebar"] [data-baseweb="select"] input::placeholder {{ color:#777777; }}
section[data-testid="stSidebar"] [data-baseweb="select"] [aria-hidden="true"],
section[data-testid="stSidebar"] [data-baseweb="select"] div {{ color:{BLACK}; }}
section[data-testid="stSidebar"] [data-baseweb="select"] svg {{ fill:#555555; color:#555555; }}
section[data-testid="stSidebar"] [data-baseweb="tag"] {{ background:{PINK}; }}
section[data-testid="stSidebar"] [data-baseweb="tag"] span,
section[data-testid="stSidebar"] [data-baseweb="tag"] svg {{ color:{BLACK}; fill:{BLACK}; }}

/* Dropdown menus (rendered outside the sidebar): white with dark text. */
[data-testid="stMultiSelectDropdown"], [data-testid="stSelectboxVirtualDropdown"] {{
  background:#FFFFFF; border:1px solid {BORDER}; box-shadow:0 8px 24px rgba(0,0,0,.12);
}}
[data-testid="stMultiSelectDropdown"] *, [data-testid="stSelectboxVirtualDropdown"] * {{ color:{BLACK}; }}
[data-testid="stMultiSelectDropdown"] [role="option"]:hover,
[data-testid="stMultiSelectDropdown"] [role="option"][data-focused],
[data-testid="stMultiSelectDropdown"] [role="option"][data-hovered],
[data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover,
[data-testid="stSelectboxVirtualDropdown"] [role="option"][data-focused],
[data-testid="stSelectboxVirtualDropdown"] [role="option"][data-hovered] {{ background:#FFF0F7; }}
[data-testid="stMultiSelectDropdown"] [role="option"][aria-selected="true"],
[data-testid="stSelectboxVirtualDropdown"] [role="option"][aria-selected="true"] {{
  background:{PINK_LIGHT}; font-weight:600;
}}
[data-testid="stMultiSelectDropdown"] [role="separator"],
[data-testid="stMultiSelectDropdown"] hr {{ border-color:{BORDER}; background:{BORDER}; }}
</style>
"""
