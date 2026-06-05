"""
Chapter 7 — Buy, Sell, or Hold?
Expected Value calculator with scenario probabilities and tax hurdle.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.calculations import (
    DCFInputs, run_dcf, Scenario, expected_value, annual_excess_return, tax_hurdle
)

st.markdown('<span class="chapter-badge">CHAPTER 7</span>', unsafe_allow_html=True)
st.title("🎯 Buy / Sell / Hold — Expected Value Analysis")
st.caption("Convert anticipated revisions in expectations into an expected value, then compare to the current price.")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Current Stock Price")
    current_price = st.number_input("Current Stock Price ($)", 0.01, 100_000.0, 418.0, 1.0)
    shares = st.number_input("Shares Outstanding (M)", 0.1, 100_000.0, 39.0, 0.5)
    current_mktcap = current_price * shares
    st.caption(f"Market Cap: ${current_mktcap:,.0f}M")

    st.header("Scenario: Low")
    sg_lo   = st.slider("Sales Growth — Low (%)", 0.0, 30.0, 3.0, 0.5, key="lo_sg") / 100
    opm_lo  = st.slider("OPM — Low (%)", 1.0, 50.0, 17.5, 0.5, key="lo_opm") / 100
    p_lo    = st.slider("Probability — Low (%)", 0, 100, 25, 1, key="lo_p") / 100

    st.header("Scenario: Consensus")
    sg_mid  = st.slider("Sales Growth — Consensus (%)", 0.0, 40.0, 7.0, 0.5, key="mid_sg") / 100
    opm_mid = st.slider("OPM — Consensus (%)", 1.0, 60.0, 17.5, 0.5, key="mid_opm") / 100
    p_mid   = st.slider("Probability — Consensus (%)", 0, 100, 55, 1, key="mid_p") / 100

    st.header("Scenario: High")
    sg_hi   = st.slider("Sales Growth — High (%)", 0.0, 50.0, 11.0, 0.5, key="hi_sg") / 100
    opm_hi  = st.slider("OPM — High (%)", 1.0, 60.0, 17.5, 0.5, key="hi_opm") / 100
    p_hi    = st.slider("Probability — High (%)", 0, 100, 20, 1, key="hi_p") / 100

    total_p = p_lo + p_mid + p_hi
    if abs(total_p - 1.0) > 0.01:
        st.warning(f"Probabilities sum to {total_p*100:.0f}%. Adjust to sum to 100%.")

    st.header("Common Inputs")
    base_sales   = st.number_input("Year 0 Sales ($M)", 1.0, 500_000.0, 3972.0, 50.0)
    cash_tax     = st.slider("Cash Tax Rate (%)", 5.0, 50.0, 16.5, 0.5) / 100
    ifcr         = st.slider("IFCR (%)", 0.0, 100.0, 10.0, 1.0) / 100
    iwcr         = st.slider("IWCR (%)", 0.0, 60.0, 15.0, 1.0) / 100
    wacc         = st.slider("WACC (%)", 1.0, 20.0, 5.35, 0.05) / 100
    forecast_yrs = st.slider("Forecast Period (years)", 1, 20, 8, 1)
    inflation    = st.slider("Inflation (%)", 0.0, 6.0, 2.0, 0.25) / 100
    pp           = st.slider("Pricing Power (p)", 0.0, 1.0, 1.0, 0.05)
    excess_cash  = st.number_input("Excess Cash ($M)", 0.0, 1_000_000.0, 390.0, 10.0)
    debt         = st.number_input("Debt ($M)", 0.0, 1_000_000.0, 4100.0, 10.0)

    st.header("Tax Hurdle")
    purchase_price = st.number_input("Original Purchase Price ($)", 0.01, 100_000.0, 100.0, 1.0)
    cg_tax         = st.slider("Capital Gains Tax Rate (%)", 0.0, 40.0, 20.0, 1.0) / 100
    yrs_converge   = st.slider("Years to Convergence", 1, 10, 2, 1)

# ── Run DCF for each scenario ─────────────────────────────────────────────────
def make_inp(sg, opm):
    return DCFInputs(
        base_sales=base_sales, sales_growth=sg, op_margin=opm,
        cash_tax_rate=cash_tax, ifcr=ifcr, iwcr=iwcr, wacc=wacc,
        forecast_years=forecast_yrs, inflation=inflation, pricing_power=pp,
        excess_cash=excess_cash, debt=debt,
    )

sv_lo  = run_dcf(make_inp(sg_lo,  opm_lo)).shareholder_value
sv_mid = run_dcf(make_inp(sg_mid, opm_mid)).shareholder_value
sv_hi  = run_dcf(make_inp(sg_hi,  opm_hi)).shareholder_value

# Convert total SV to per-share
sp_lo  = sv_lo  / shares if shares else 0
sp_mid = sv_mid / shares if shares else 0
sp_hi  = sv_hi  / shares if shares else 0

scenarios = [
    Scenario("Low",       sp_lo,  p_lo),
    Scenario("Consensus", sp_mid, p_mid),
    Scenario("High",      sp_hi,  p_hi),
]

ev = expected_value(scenarios)
discount_to_ev = (ev - current_price) / current_price * 100
ann_excess = annual_excess_return(current_price, ev, yrs_converge)

# ── Decision logic ────────────────────────────────────────────────────────────
MARGIN = 0.10   # 10% minimum margin of safety
if ev > current_price * (1 + MARGIN):
    decision = "🟢 BUY"
    decision_color = "success"
elif ev < current_price * (1 - MARGIN):
    decision = "🔴 SELL"
    decision_color = "error"
else:
    decision = "🟡 HOLD"
    decision_color = "warning"

# ── Layout ────────────────────────────────────────────────────────────────────
st.subheader("Expected Value Calculation")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Expected Value (EV)", f"${ev:,.2f}")
col2.metric("Current Price", f"${current_price:,.2f}")
col3.metric("EV vs. Price", f"{discount_to_ev:+.1f}%",
            delta_color="normal" if discount_to_ev >= 0 else "inverse")
col4.metric("Annual Excess Return", f"{ann_excess*100:.1f}%",
            f"over {yrs_converge} years to convergence")

if decision_color == "success":
    st.success(f"**Decision: {decision}** — EV exceeds current price by >{MARGIN*100:.0f}% margin of safety")
elif decision_color == "error":
    st.error(f"**Decision: {decision}** — Current price exceeds EV by >{MARGIN*100:.0f}%")
else:
    st.warning(f"**Decision: {decision}** — EV and price are within ±{MARGIN*100:.0f}%")

st.divider()

# ── Scenario table ────────────────────────────────────────────────────────────
st.subheader("Scenario Detail")

df = pd.DataFrame([{
    "Scenario": s.label,
    "Sales Growth (%)": f"{[sg_lo, sg_mid, sg_hi][i]*100:.1f}%",
    "OPM (%)": f"{[opm_lo, opm_mid, opm_hi][i]*100:.1f}%",
    "Sh. Value ($M)": f"${[sv_lo, sv_mid, sv_hi][i]:,.1f}M",
    "Price / Share ($)": f"${s.stock_value:,.2f}",
    "Probability": f"{s.probability*100:.0f}%",
    "Weighted Value ($)": f"${s.weighted:,.2f}",
} for i, s in enumerate(scenarios)])

st.dataframe(df, use_container_width=True, hide_index=True)

# EV row
st.metric("Expected Value (EV)", f"${ev:,.2f}", f"= Σ(price × probability)")

st.divider()

# ── Waterfall / scenario bar chart ───────────────────────────────────────────
col_chart, col_gauge = st.columns([2, 1])

with col_chart:
    st.subheader("Scenario Values vs. Current Price")
    labels = ["Low", "Consensus", "High", "Expected Value", "Current Price"]
    values = [sp_lo, sp_mid, sp_hi, ev, current_price]
    colors = ["#dc2626", "#2563eb", "#16a34a", "#7c3aed", "#94a3b8"]
    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=colors,
        text=[f"${v:,.1f}" for v in values],
        textposition="outside",
    ))
    fig.add_hline(y=current_price, line=dict(color="#94a3b8", dash="dot"),
                  annotation_text="Current Price")
    fig.update_layout(height=320, margin=dict(t=30, b=10),
                      yaxis_title="Price / Share ($)", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with col_gauge:
    st.subheader("EV vs. Price")
    fig2 = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=ev,
        delta={"reference": current_price, "valueformat": ".2f"},
        gauge={
            "axis": {"range": [min(sp_lo * 0.8, current_price * 0.8),
                                max(sp_hi * 1.1, current_price * 1.1)]},
            "bar": {"color": "#2563eb"},
            "steps": [
                {"range": [sp_lo * 0.8, current_price], "color": "#fee2e2"},
                {"range": [current_price, sp_hi * 1.1], "color": "#dcfce7"},
            ],
            "threshold": {"line": {"color": "#dc2626", "width": 2},
                          "thickness": 0.75, "value": current_price},
        },
        number={"prefix": "$", "valueformat": ".2f"},
        title={"text": "Expected Value"},
    ))
    fig2.update_layout(height=300, margin=dict(t=30, b=0))
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ── Tax hurdle ────────────────────────────────────────────────────────────────
st.subheader("Tax & Time Hurdle (Ch 7)")
th = tax_hurdle(purchase_price, current_price, cg_tax, wacc)

t1, t2, t3, t4 = st.columns(4)
t1.metric("Capital Gain", f"${th['gain']:,.2f}")
t2.metric("Tax Paid", f"${th['tax_paid']:,.2f}")
t3.metric("Available to Reinvest", f"${th['reinvest_amount']:,.2f}")
t4.metric("Excess Return Needed to Break Even", f"{th['excess_return_needed']*100:.2f}%")

st.caption(
    "Selling triggers a tax event. The new investment must earn this excess return above WACC "
    "just to match the return from holding the original (fairly valued) stock."
)

st.divider()

# ── Sell triggers (Ch 7) ──────────────────────────────────────────────────────
st.subheader("📐 The Three Sell Triggers (Ch 7)")
col_a, col_b, col_c = st.columns(3)
with col_a:
    st.info("**1. EV Reached**\nYour analysis no longer shows upside relative to the updated estimate. Re-run PIE; if the stock has converged to EV, it is time to consider selling.")
with col_b:
    st.info("**2. Better Opportunities**\nReallocation to a higher risk-adjusted return. Factor in the tax hurdle before switching.")
with col_c:
    st.info("**3. Downward Revision**\nThesis failure, material error, or management signal that undermines the original expectations revision.")
