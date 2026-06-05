"""
Chapter 2 — Shareholder Value Road Map (DCF Engine)
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.calculations import DCFInputs, run_dcf

st.markdown('<span class="chapter-badge">CHAPTER 2</span>', unsafe_allow_html=True)
st.title("🏗️ DCF Engine — Shareholder Value Road Map")
st.caption("Build up free cash flows from value drivers and compute total shareholder value.")

# ── Sidebar inputs ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Value Drivers")
    st.subheader("Operating")
    base_sales  = st.number_input("Year 0 Sales ($M)", 1.0, 500_000.0, 100.0, step=10.0)
    sales_growth = st.slider("Sales Growth Rate (%)", 0.0, 40.0, 10.0, 0.5) / 100
    op_margin    = st.slider("Operating Profit Margin (%)", 1.0, 60.0, 15.0, 0.5) / 100
    cash_tax     = st.slider("Cash Tax Rate (%)", 5.0, 50.0, 25.0, 0.5) / 100

    st.subheader("Investment Rates")
    ifcr = st.slider("Incr. Fixed-Capital Rate (%)", 0.0, 100.0, 15.0, 1.0) / 100
    iwcr = st.slider("Incr. Working-Capital Rate (%)", 0.0, 60.0, 10.0, 1.0) / 100
    st.caption("IFCR = (CapEx – Dep) / ΔSales  |  IWCR = ΔOp. WC / ΔSales")

    st.subheader("Capital & Time")
    wacc         = st.slider("WACC (%)", 3.0, 25.0, 8.0, 0.25) / 100
    forecast_yrs = st.slider("Forecast Period (years)", 1, 20, 5, 1)

    st.subheader("Continuing Value")
    inflation    = st.slider("Long-run Inflation (g, %)", 0.0, 6.0, 2.0, 0.25) / 100
    pp           = st.slider("Pricing Power Factor (p)", 0.0, 1.0, 1.0, 0.05)
    st.caption("CV = NOPAT×(1+i·p) / (WACC–i·p)")

    st.subheader("Non-Operating Items")
    excess_cash = st.number_input("Excess Cash & Non-Op Assets ($M)", 0.0, 100_000.0, 0.0, 10.0)
    debt        = st.number_input("Market Value of Debt ($M)", 0.0, 100_000.0, 0.0, 10.0)

# ── Calculate ─────────────────────────────────────────────────────────────────
inp = DCFInputs(
    base_sales=base_sales, sales_growth=sales_growth, op_margin=op_margin,
    cash_tax_rate=cash_tax, ifcr=ifcr, iwcr=iwcr, wacc=wacc,
    forecast_years=forecast_yrs, inflation=inflation, pricing_power=pp,
    excess_cash=excess_cash, debt=debt,
)
res = run_dcf(inp)

# ── Formula strip ─────────────────────────────────────────────────────────────
y1 = res.rows[0]
fcols = st.columns(7)
items = [
    ("Sales Y1", f"${y1.sales:,.1f}M"),
    ("× OPM", f"{op_margin*100:.1f}%"),
    ("= Op. Profit", f"${y1.op_profit:,.1f}M"),
    ("− Cash Tax", f"${y1.op_profit*cash_tax:,.1f}M"),
    ("= NOPAT", f"${y1.nopat:,.1f}M"),
    ("− Investment", f"${y1.investment:,.1f}M"),
    ("= FCF", f"${y1.fcf:,.1f}M"),
]
for col, (lbl, val) in zip(fcols, items):
    col.metric(lbl, val)

st.divider()

# ── Hero metric ───────────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("📊 Shareholder Value", f"${res.shareholder_value:,.1f}M")
m2.metric("PV of FCFs", f"${res.pv_fcfs:,.1f}M",
          f"{res.pv_fcfs/res.shareholder_value*100:.0f}% of total" if res.shareholder_value else "")
m3.metric("PV of Cont. Value", f"${res.pv_continuing_value:,.1f}M",
          f"{res.pv_continuing_value/res.shareholder_value*100:.0f}% of total" if res.shareholder_value else "")
m4.metric("Operating Value", f"${res.operating_value:,.1f}M",
          f"+ ${excess_cash:.0f}M non-op − ${debt:.0f}M debt")

st.divider()

# ── Charts ────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📅 Year-by-Year", "📊 Value Composition", "📈 Sales Ramp", "📐 Formulas"])

with tab1:
    df = pd.DataFrame([{
        "Year": r.year,
        "Sales ($M)": round(r.sales, 2),
        "Op. Profit ($M)": round(r.op_profit, 2),
        "NOPAT ($M)": round(r.nopat, 2),
        "Investment ($M)": round(r.investment, 2),
        "FCF ($M)": round(r.fcf, 2),
        "PV of FCF ($M)": round(r.pv_fcf, 2),
    } for r in res.rows])
    st.dataframe(df, use_container_width=True, hide_index=True)

    fig = go.Figure()
    fig.add_bar(x=df["Year"], y=df["NOPAT ($M)"], name="NOPAT", marker_color="#2563eb")
    fig.add_bar(x=df["Year"], y=df["Investment ($M)"], name="Investment", marker_color="#f59e0b")
    fig.add_scatter(x=df["Year"], y=df["FCF ($M)"], name="FCF", mode="lines+markers",
                    line=dict(color="#16a34a", width=2))
    fig.update_layout(barmode="overlay", height=320, margin=dict(t=10, b=10),
                      legend=dict(orientation="h", y=-0.2),
                      xaxis_title="Year", yaxis_title="$M")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    labels = ["PV of FCFs", "PV of Cont. Value", "Excess Cash"]
    values = [max(0, res.pv_fcfs), max(0, res.pv_continuing_value), max(0, excess_cash)]
    colors = ["#2563eb", "#16a34a", "#f59e0b"]

    col_pie, col_waterfall = st.columns(2)
    with col_pie:
        fig2 = go.Figure(go.Pie(labels=labels, values=values, hole=0.45,
                                 marker_colors=colors, textinfo="label+percent"))
        fig2.update_layout(height=300, margin=dict(t=10, b=10), showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

    with col_waterfall:
        wf_x = ["PV FCFs", "+ PV CV", "+ Non-Op", "− Debt", "= Sh. Value"]
        wf_y = [res.pv_fcfs, res.pv_continuing_value, excess_cash, -debt, 0]
        wf_measure = ["relative", "relative", "relative", "relative", "total"]
        fig3 = go.Figure(go.Waterfall(
            x=wf_x, y=wf_y, measure=wf_measure,
            connector=dict(line=dict(color="#94a3b8")),
            increasing=dict(marker_color="#2563eb"),
            decreasing=dict(marker_color="#dc2626"),
            totals=dict(marker_color="#1e293b"),
        ))
        fig3.update_layout(height=300, margin=dict(t=10, b=10),
                           yaxis_title="$M", showlegend=False)
        st.plotly_chart(fig3, use_container_width=True)

with tab3:
    years = list(range(forecast_yrs + 1))
    sales_vals = [base_sales * (1 + sales_growth) ** y for y in years]
    fcf_vals = [0] + [r.fcf for r in res.rows]
    pv_fcf_vals = [0] + [r.pv_fcf for r in res.rows]
    fig4 = go.Figure()
    fig4.add_scatter(x=years, y=sales_vals, name="Sales", mode="lines+markers",
                     line=dict(color="#2563eb", width=2))
    fig4.add_bar(x=years[1:], y=fcf_vals[1:], name="FCF", marker_color="#16a34a", opacity=0.7)
    fig4.add_scatter(x=years[1:], y=pv_fcf_vals[1:], name="PV of FCF", mode="lines+markers",
                     line=dict(color="#f59e0b", dash="dash", width=1.5))
    fig4.update_layout(height=320, margin=dict(t=10, b=10),
                       xaxis_title="Year", yaxis_title="$M",
                       legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig4, use_container_width=True)

with tab4:
    st.markdown("""
    #### Free Cash Flow
    """)
    for f in [
        "Sales × Operating Profit Margin = Operating Profit",
        "Operating Profit × (1 – Cash Tax Rate) = NOPAT",
        "Investment = (IFCR + IWCR) × ΔSales",
        "FCF = NOPAT – Investment",
    ]:
        st.markdown(f'<div class="formula-box">{f}</div>', unsafe_allow_html=True)

    st.markdown("#### Continuing Value (Partial-Inflation Perpetuity)")
    g_eff = inflation * pp
    st.markdown(f'<div class="formula-box">CV = NOPAT_N × (1 + i×p) / (WACC – i×p) &nbsp;&nbsp;→ effective g = {g_eff*100:.2f}%</div>', unsafe_allow_html=True)

    st.markdown("#### Shareholder Value")
    for f in [
        "Operating Value = PV(FCFs) + PV(Continuing Value)",
        "Shareholder Value = Operating Value + Non-Op Assets – Debt",
    ]:
        st.markdown(f'<div class="formula-box">{f}</div>', unsafe_allow_html=True)

    with st.expander("Computed values"):
        st.write({
            "Effective CV growth (i×p)": f"{g_eff*100:.2f}%",
            "Continuing Value at horizon ($M)": f"{res.continuing_value:,.1f}",
            "PV of Continuing Value ($M)": f"{res.pv_continuing_value:,.1f}",
            "PV of FCFs ($M)": f"{res.pv_fcfs:,.1f}",
            "Operating Value ($M)": f"{res.operating_value:,.1f}",
            "Shareholder Value ($M)": f"{res.shareholder_value:,.1f}",
        })
