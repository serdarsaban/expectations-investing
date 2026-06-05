"""Chapter 7 — Buy / Sell / Hold, pre-filled from session state."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.calculations import DCFInputs, run_dcf, Scenario, expected_value, annual_excess_return, tax_hurdle

st.markdown('<span class="chapter-badge">CHAPTER 7</span>', unsafe_allow_html=True)
st.title("🎯 Buy / Sell / Hold — Expected Value Analysis")

data = st.session_state.get("company_data")

if data:
    st.caption(f"Data loaded for **{data.name} ({data.ticker})**.")
    d = dict(price=data.current_price, shares=data.shares_outstanding_m,
             base_sales=data.base_sales_m, sg=data.sales_growth_3yr,
             opm=data.op_margin_3yr, tax=data.cash_tax_rate_3yr,
             ifcr=data.ifcr_3yr, iwcr=data.iwcr_3yr, wacc=data.wacc,
             excess_cash=data.excess_cash_m, debt=data.total_debt_m)
else:
    st.info("No ticker loaded — using Domino's defaults. Go to **Ticker Lookup** to load a company.")
    d = dict(price=418.0, shares=39.0, base_sales=3972.0, sg=0.07,
             opm=0.175, tax=0.165, ifcr=0.10, iwcr=0.15, wacc=0.0535,
             excess_cash=390.0, debt=4100.0)

with st.sidebar:
    st.header("Market")
    current_price = st.number_input("Current Price ($)", 0.01, 100_000.0, round(d["price"],2), step=1.0)
    shares        = st.number_input("Shares Outstanding (M)", 0.1, 100_000.0, round(d["shares"],1), step=0.5)

    st.header("Scenario Inputs")
    sg_lo  = st.number_input("Sales Growth — Bear (%)",  -10.0, 40.0, round(max(-10.0, d["sg"]*100-4),1), step=0.5) / 100
    sg_mid = st.number_input("Sales Growth — Base (%)",   0.0,  50.0, round(d["sg"]*100,1), step=0.5) / 100
    sg_hi  = st.number_input("Sales Growth — Bull (%)",   0.0,  60.0, round(d["sg"]*100+4,1), step=0.5) / 100
    p_lo   = st.number_input("Probability — Bear (%)",    0, 100, 25, step=5) / 100
    p_mid  = st.number_input("Probability — Base (%)",    0, 100, 50, step=5) / 100
    p_hi   = st.number_input("Probability — Bull (%)",    0, 100, 25, step=5) / 100

    total_p = p_lo + p_mid + p_hi
    if abs(total_p - 1.0) > 0.01:
        st.warning(f"Probabilities sum to {total_p*100:.0f}% — adjust to 100%.")

    st.header("Common Inputs")
    base_sales   = st.number_input("Year 0 Sales ($M)", 1.0, 500_000.0, round(d["base_sales"],1), step=50.0)
    opm          = st.number_input("Op. Margin (%)", 1.0, 60.0, round(d["opm"]*100,1), step=0.5) / 100
    cash_tax     = st.number_input("Cash Tax Rate (%)", 5.0, 50.0, round(d["tax"]*100,1), step=0.5) / 100
    ifcr         = st.number_input("IFCR (%)", 0.0, 100.0, round(d["ifcr"]*100,1), step=1.0) / 100
    iwcr         = st.number_input("IWCR (%)", 0.0, 60.0, round(d["iwcr"]*100,1), step=1.0) / 100
    wacc         = st.number_input("WACC (%)", 1.0, 20.0, round(d["wacc"]*100,2), step=0.05) / 100
    forecast_yrs = st.number_input("Forecast Period (years)", 1, 20, 8, step=1)
    inflation    = st.number_input("Inflation (%)", 0.0, 6.0, 2.0, step=0.25) / 100
    pp           = st.number_input("Pricing Power (p)", 0.0, 1.0, 1.0, step=0.05)
    excess_cash  = st.number_input("Excess Cash ($M)", 0.0, 1_000_000.0, round(d["excess_cash"],1), step=10.0)
    debt         = st.number_input("Debt ($M)", 0.0, 1_000_000.0, round(d["debt"],1), step=10.0)
    yrs_conv     = st.number_input("Years to Convergence", 1, 10, 2, step=1)
    purchase_price = st.number_input("Original Purchase Price ($)", 0.01, 100_000.0, round(d["price"],2), step=1.0)
    cg_tax       = st.number_input("Capital Gains Tax Rate (%)", 0.0, 40.0, 20.0, step=1.0) / 100

def make_inp(sg):
    return DCFInputs(
        base_sales=base_sales, sales_growth=sg, op_margin=opm,
        cash_tax_rate=cash_tax, ifcr=ifcr, iwcr=iwcr, wacc=wacc,
        forecast_years=int(forecast_yrs), inflation=inflation, pricing_power=pp,
        excess_cash=excess_cash, debt=debt,
    )

sv_lo  = run_dcf(make_inp(sg_lo)).shareholder_value  / shares if shares else 0
sv_mid = run_dcf(make_inp(sg_mid)).shareholder_value / shares if shares else 0
sv_hi  = run_dcf(make_inp(sg_hi)).shareholder_value  / shares if shares else 0

scenarios = [
    Scenario("Bear", sv_lo,  p_lo),
    Scenario("Base", sv_mid, p_mid),
    Scenario("Bull", sv_hi,  p_hi),
]
ev      = expected_value(scenarios)
upside  = (ev - current_price) / current_price * 100 if current_price else 0
ann_exc = annual_excess_return(current_price, ev, yrs_conv)

# Decision
if upside > 10:
    dec, col = "🟢 BUY", "success"
elif upside < -10:
    dec, col = "🔴 SELL", "error"
else:
    dec, col = "🟡 HOLD", "warning"

m1, m2, m3, m4 = st.columns(4)
m1.metric("Expected Value", f"${ev:,.2f}")
m2.metric("Current Price", f"${current_price:,.2f}")
m3.metric("EV vs Price", f"{upside:+.1f}%")
m4.metric("Annual Excess Return", f"{ann_exc*100:.1f}%", f"over {yrs_conv} years")

if col == "success":   st.success(f"**{dec}** — EV exceeds price by >10%")
elif col == "error":   st.error(f"**{dec}** — Price exceeds EV by >10%")
else:                  st.warning(f"**{dec}** — within ±10% of EV")

st.divider()

sc_df = pd.DataFrame([{
    "Scenario": s.label,
    "Sales Growth": f"{[sg_lo,sg_mid,sg_hi][i]*100:.1f}%",
    "Value / Share ($)": f"${s.stock_value:,.2f}",
    "Probability": f"{s.probability*100:.0f}%",
    "Weighted Value ($)": f"${s.weighted:,.2f}",
} for i, s in enumerate(scenarios)] + [{
    "Scenario": "Expected Value",
    "Sales Growth": "", "Value / Share ($)": "",
    "Probability": "100%", "Weighted Value ($)": f"${ev:,.2f}",
}])
st.dataframe(sc_df, use_container_width=True, hide_index=True)

fig = go.Figure(go.Bar(
    x=["Bear", "Base", "Bull", "EV", "Price"],
    y=[sv_lo, sv_mid, sv_hi, ev, current_price],
    marker_color=["#dc2626","#2563eb","#16a34a","#7c3aed","#94a3b8"],
    text=[f"${v:,.1f}" for v in [sv_lo,sv_mid,sv_hi,ev,current_price]],
    textposition="outside",
))
fig.add_hline(y=current_price, line=dict(color="#94a3b8", dash="dot"))
fig.update_layout(height=300, margin=dict(t=30,b=10), yaxis_title="$ / Share", showlegend=False)
st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("Tax & Time Hurdle")
th = tax_hurdle(purchase_price, current_price, cg_tax, wacc)
t1, t2, t3, t4 = st.columns(4)
t1.metric("Capital Gain", f"${th['gain']:,.2f}")
t2.metric("Tax Paid", f"${th['tax_paid']:,.2f}")
t3.metric("Available to Reinvest", f"${th['reinvest_amount']:,.2f}")
t4.metric("Excess Return Needed", f"{th['excess_return_needed']*100:.2f}%")
