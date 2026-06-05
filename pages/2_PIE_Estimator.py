"""
Chapter 5 — Price-Implied Expectations (PIE) Estimator
Reverse-engineer the stock price to reveal what the market is pricing in.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.calculations import (
    DCFInputs, run_dcf, solve_pie_growth, solve_pie_forecast_period, calc_wacc, capm
)

st.markdown('<span class="chapter-badge">CHAPTER 5</span>', unsafe_allow_html=True)
st.title("🔎 PIE Estimator — Price-Implied Expectations")
st.caption("Reverse-engineer the current stock price to read what the market expects.")

st.info(
    "**How to use:** Enter the current market data and consensus operating assumptions. "
    "The tool solves for either the **implied sales growth rate** or the **market-implied "
    "forecast period** that justifies today's stock price."
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Market Data")
    market_cap  = st.number_input("Market Cap ($M)", 1.0, 10_000_000.0, 418.0 * 39.0, 100.0,
                                   help="Shares × stock price")
    excess_cash = st.number_input("Excess Cash & Non-Op Assets ($M)", 0.0, 1_000_000.0, 390.0, 10.0)
    debt        = st.number_input("Market Value of Debt ($M)", 0.0, 1_000_000.0, 4100.0, 10.0)

    st.header("Consensus Operating Assumptions")
    base_sales  = st.number_input("Year 0 Sales ($M)", 1.0, 500_000.0, 3972.0, 50.0)
    op_margin   = st.slider("Operating Profit Margin (%)", 1.0, 60.0, 17.5, 0.5) / 100
    cash_tax    = st.slider("Cash Tax Rate (%)", 5.0, 50.0, 16.5, 0.5) / 100
    ifcr        = st.slider("Incr. Fixed-Capital Rate (%)", 0.0, 100.0, 10.0, 1.0) / 100
    iwcr        = st.slider("Incr. Working-Capital Rate (%)", 0.0, 60.0, 15.0, 1.0) / 100

    st.header("WACC Builder")
    use_wacc_builder = st.toggle("Use WACC builder", False)
    if use_wacc_builder:
        rf   = st.slider("Risk-free Rate (%)", 0.0, 10.0, 0.65, 0.05) / 100
        beta = st.slider("Beta (equity)", 0.1, 3.0, 1.0, 0.05)
        emp  = st.slider("Equity Market Premium (%)", 2.0, 10.0, 5.1, 0.1) / 100
        ke   = capm(rf, beta, emp)
        st.caption(f"Cost of equity = {ke*100:.2f}%")
        eq_wt = st.slider("Equity Weight (%)", 10.0, 100.0, 80.0, 1.0) / 100
        kd_pretax = st.slider("Pre-tax Cost of Debt (%)", 0.5, 15.0, 4.55, 0.05) / 100
        wacc = calc_wacc(eq_wt, 1 - eq_wt, ke, kd_pretax, cash_tax)
        st.success(f"WACC = {wacc*100:.2f}%")
    else:
        wacc = st.slider("WACC (%)", 1.0, 20.0, 5.35, 0.05) / 100

    st.header("Continuing Value")
    inflation = st.slider("Long-run Inflation (%)", 0.0, 6.0, 2.0, 0.25) / 100
    pp        = st.slider("Pricing Power (p)", 0.0, 1.0, 1.0, 0.05)
    max_yrs   = st.slider("Max Forecast Period (years)", 5, 30, 15, 1)

# ── Implied target equity value ───────────────────────────────────────────────
# Equity value = Market cap, but DCF returns total shareholder value.
# Shareholder Value = PV FCFs + PV CV + excess_cash – debt = market_cap
# So DCF target = market_cap
target_sv = market_cap

# ── Solve PIE ────────────────────────────────────────────────────────────────
base_inp = DCFInputs(
    base_sales=base_sales, sales_growth=0.07, op_margin=op_margin,
    cash_tax_rate=cash_tax, ifcr=ifcr, iwcr=iwcr, wacc=wacc,
    forecast_years=max_yrs, inflation=inflation, pricing_power=pp,
    excess_cash=excess_cash, debt=debt,
)

implied_growth = solve_pie_growth(target_sv, base_inp)
implied_period = solve_pie_forecast_period(target_sv, base_inp, max_yrs)

# ── Hero display ──────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
c1.metric("📌 Target Shareholder Value", f"${target_sv:,.0f}M")
c2.metric("⚡ Implied Sales Growth (PIE)", f"{implied_growth*100:.2f}%",
          "Rate the market is pricing in")
c3.metric("📅 Market-Implied Forecast Period", f"{implied_period} years",
          "Years of value-creating growth")

st.divider()

# ── Verification ──────────────────────────────────────────────────────────────
verify_inp = DCFInputs(**{**base_inp.__dict__, 'sales_growth': implied_growth,
                          'forecast_years': implied_period})
verify_res = run_dcf(verify_inp)

st.subheader("Verification — DCF at implied assumptions")
v1, v2, v3, v4 = st.columns(4)
v1.metric("DCF Shareholder Value", f"${verify_res.shareholder_value:,.1f}M")
v2.metric("Target", f"${target_sv:,.1f}M")
delta_pct = (verify_res.shareholder_value - target_sv) / target_sv * 100
v3.metric("Difference", f"{delta_pct:+.1f}%", delta_color="inverse")
v4.metric("PV Cont. Value / Total", f"{verify_res.pv_continuing_value/verify_res.shareholder_value*100:.0f}%"
          if verify_res.shareholder_value else "—")

st.divider()

# ── Sweep: shareholder value vs. sales growth ─────────────────────────────────
st.subheader("Sensitivity — Shareholder Value vs. Sales Growth")
growth_range = [g / 100 for g in range(0, 41)]
sv_range = []
for g in growth_range:
    i2 = DCFInputs(**{**base_inp.__dict__, 'sales_growth': g, 'forecast_years': max_yrs})
    sv_range.append(run_dcf(i2).shareholder_value)

fig = go.Figure()
fig.add_scatter(x=[g * 100 for g in growth_range], y=sv_range,
                mode="lines", line=dict(color="#2563eb", width=2), name="Shareholder Value")
fig.add_hline(y=target_sv, line=dict(color="#dc2626", dash="dash", width=1.5),
              annotation_text=f"Market price target ${target_sv:,.0f}M", annotation_position="top left")
fig.add_vline(x=implied_growth * 100, line=dict(color="#f59e0b", dash="dot", width=1.5),
              annotation_text=f"PIE growth: {implied_growth*100:.2f}%", annotation_position="top right")
fig.update_layout(height=340, margin=dict(t=20, b=20),
                  xaxis_title="Sales Growth Rate (%)", yaxis_title="Shareholder Value ($M)",
                  legend=dict(orientation="h", y=-0.2))
st.plotly_chart(fig, use_container_width=True)

# ── Year-by-year PIE path ─────────────────────────────────────────────────────
st.subheader("Market-Implied Forecast Period — Year-by-Year Value Build")
st.caption("Value grows each year until it reaches the stock price — that year is the implied forecast period.")

yby_rows = []
for yrs in range(1, max_yrs + 1):
    i2 = DCFInputs(**{**base_inp.__dict__, 'sales_growth': implied_growth, 'forecast_years': yrs})
    sv2 = run_dcf(i2).shareholder_value
    yby_rows.append({"Years": yrs, "Shareholder Value ($M)": round(sv2, 1),
                     "vs Target": f"{(sv2/target_sv - 1)*100:+.1f}%"})
df = pd.DataFrame(yby_rows)
st.dataframe(df.style.apply(
    lambda x: ["background-color: #dbeafe" if i + 1 == implied_period else "" for i in range(len(x))],
    axis=0), use_container_width=True, hide_index=True)

st.divider()
st.subheader("📐 Operational Guidelines (Ch 5)")
st.markdown("""
1. **Cash Flows** — Use consensus forecasts (Value Line, Bloomberg, FactSet) for OPM, tax, IFCR, IWCR. Keep them fixed; solve only for growth or forecast period.
2. **WACC** — Use market weights (not book). CAPM for cost of equity: `R_f + β × (E_m − R_f)`.
3. **Non-Operating Assets** — Add excess cash (>1% of sales). Subtract debt, preferred stock, underfunded pension (PBO > plan assets).
4. **Market-Implied Forecast Period** — Extend the DCF horizon until it hits the stock price. For US stocks: typically 5–15 years. Outliers deserve scrutiny.
5. **Revisit PIE** when: stock price moves >10%, earnings surprise, M&A announced, large buyback disclosed.
""")
