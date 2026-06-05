"""Chapter 5 — PIE Estimator, pre-filled from Ticker Lookup session state."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.calculations import DCFInputs, run_dcf, solve_pie_growth, solve_pie_forecast_period, calc_wacc, capm

st.markdown('<span class="chapter-badge">CHAPTER 5</span>', unsafe_allow_html=True)
st.title("🔎 PIE Estimator — Price-Implied Expectations")

data = st.session_state.get("company_data")

if data:
    st.caption(f"Data loaded for **{data.name} ({data.ticker})**.")
    d = dict(
        market_cap=data.market_cap_m,
        base_sales=data.base_sales_m,
        op_margin=data.op_margin_3yr,
        cash_tax=data.cash_tax_rate_3yr,
        ifcr=data.ifcr_3yr,
        iwcr=data.iwcr_3yr,
        wacc=data.wacc,
        excess_cash=data.excess_cash_m,
        debt=data.total_debt_m,
    )
else:
    st.info("No ticker loaded — using Domino's defaults. Go to **Ticker Lookup** to load a company.")
    d = dict(market_cap=16362.0, base_sales=3972.0, op_margin=0.175,
             cash_tax=0.165, ifcr=0.10, iwcr=0.15, wacc=0.0535,
             excess_cash=390.0, debt=4100.0)

with st.sidebar:
    st.header("Inputs")
    market_cap   = st.number_input("Market Cap ($M)", 1.0, 10_000_000.0, round(d["market_cap"], 0), step=100.0)
    base_sales   = st.number_input("Year 0 Sales ($M)", 1.0, 500_000.0, round(d["base_sales"], 1), step=50.0)
    op_margin    = st.number_input("Op. Profit Margin (%)", 1.0, 60.0, round(d["op_margin"]*100, 1), step=0.5) / 100
    cash_tax     = st.number_input("Cash Tax Rate (%)", 5.0, 50.0, round(d["cash_tax"]*100, 1), step=0.5) / 100
    ifcr         = st.number_input("IFCR (%)", 0.0, 100.0, round(d["ifcr"]*100, 1), step=1.0) / 100
    iwcr         = st.number_input("IWCR (%)", 0.0, 60.0, round(d["iwcr"]*100, 1), step=1.0) / 100
    wacc         = st.number_input("WACC (%)", 1.0, 20.0, round(d["wacc"]*100, 2), step=0.05) / 100
    inflation    = st.number_input("Long-run Inflation (%)", 0.0, 6.0, 2.0, step=0.25) / 100
    pp           = st.number_input("Pricing Power (p)", 0.0, 1.0, 1.0, step=0.05)
    max_yrs      = st.number_input("Max Forecast Period", 5, 30, 15, step=1)
    excess_cash  = st.number_input("Excess Cash ($M)", 0.0, 1_000_000.0, round(d["excess_cash"], 1), step=10.0)
    debt         = st.number_input("Debt ($M)", 0.0, 1_000_000.0, round(d["debt"], 1), step=10.0)

base_inp = DCFInputs(
    base_sales=base_sales, sales_growth=0.07, op_margin=op_margin,
    cash_tax_rate=cash_tax, ifcr=ifcr, iwcr=iwcr, wacc=wacc,
    forecast_years=int(max_yrs), inflation=inflation, pricing_power=pp,
    excess_cash=excess_cash, debt=debt,
)

implied_growth = solve_pie_growth(market_cap, base_inp)
implied_period = solve_pie_forecast_period(market_cap, base_inp, int(max_yrs))

c1, c2, c3 = st.columns(3)
c1.metric("Market Cap (target)", f"${market_cap:,.0f}M")
c2.metric("PIE — Implied Sales Growth", f"{implied_growth*100:.2f}%")
c3.metric("Market-Implied Forecast Period", f"{implied_period} years")

st.divider()

# Verification
verify_inp = DCFInputs(**{**base_inp.__dict__, 'sales_growth': implied_growth, 'forecast_years': implied_period})
verify_res = run_dcf(verify_inp)
v1, v2, v3 = st.columns(3)
v1.metric("DCF at PIE assumptions", f"${verify_res.shareholder_value:,.1f}M")
v2.metric("Target", f"${market_cap:,.1f}M")
delta_pct = (verify_res.shareholder_value - market_cap) / market_cap * 100
v3.metric("Difference", f"{delta_pct:+.1f}%")

st.divider()
st.subheader("Shareholder Value vs. Sales Growth")

growth_range = [g / 100 for g in range(0, 41)]
sv_range = []
for g in growth_range:
    i2 = DCFInputs(**{**base_inp.__dict__, 'sales_growth': g, 'forecast_years': int(max_yrs)})
    sv_range.append(run_dcf(i2).shareholder_value)

fig = go.Figure()
fig.add_scatter(x=[g*100 for g in growth_range], y=sv_range,
                mode="lines", line=dict(color="#2563eb", width=2))
fig.add_hline(y=market_cap, line=dict(color="#dc2626", dash="dash"),
              annotation_text=f"Market cap ${market_cap:,.0f}M")
fig.add_vline(x=implied_growth*100, line=dict(color="#f59e0b", dash="dot"),
              annotation_text=f"PIE {implied_growth*100:.2f}%")
fig.update_layout(height=320, margin=dict(t=20,b=10),
                  xaxis_title="Sales Growth Rate (%)", yaxis_title="Shareholder Value ($M)")
st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("Year-by-Year Value Build")
yby_rows = []
for yrs in range(1, int(max_yrs) + 1):
    i2 = DCFInputs(**{**base_inp.__dict__, 'sales_growth': implied_growth, 'forecast_years': yrs})
    sv2 = run_dcf(i2).shareholder_value
    yby_rows.append({"Years": yrs, "Shareholder Value ($M)": round(sv2, 1),
                     "vs Target": f"{(sv2/market_cap-1)*100:+.1f}%"})
df = pd.DataFrame(yby_rows)
st.dataframe(df.style.apply(
    lambda x: ["background-color: #dbeafe" if i+1 == implied_period else "" for i in range(len(x))],
    axis=0), use_container_width=True, hide_index=True)
