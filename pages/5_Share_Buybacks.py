"""Chapter 11 — Share Buybacks, pre-filled from session state."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.calculations import buyback_rate_of_return, eps_accretion_test, wealth_transfer, capm

st.markdown('<span class="chapter-badge">CHAPTER 11</span>', unsafe_allow_html=True)
st.title("🔁 Share Buybacks — Golden Rule Analyser")
st.caption("**Golden Rule:** Repurchase only when price < Expected Value and no better internal investments exist.")

data = st.session_state.get("company_data")

if data:
    st.caption(f"Data loaded for **{data.name} ({data.ticker})**.")
    d = dict(price=data.current_price, shares=data.shares_outstanding_m,
             pe=data.pe_ratio, tax=data.cash_tax_rate_3yr,
             rf=data.rf_rate, beta=data.beta,
             kd=data.pretax_cost_of_debt)
else:
    st.info("No ticker loaded — using Microsoft 2006 defaults. Go to **Ticker Lookup** to load a company.")
    d = dict(price=22.85, shares=10000.0, pe=25.0, tax=0.165, rf=0.045, beta=1.0, kd=0.046)

with st.sidebar:
    st.header("Inputs")
    current_price  = st.number_input("Current Price ($)", 0.01, 100_000.0, round(d["price"],2), step=1.0)
    expected_val   = st.number_input("Expected / Fair Value ($)", 0.01, 100_000.0, round(d["price"]*1.1,2), step=1.0)
    shares_out     = st.number_input("Shares Outstanding (M)", 0.1, 100_000.0, round(d["shares"],1), step=100.0)
    buyback_amount = st.number_input("Buyback Program ($M)", 1.0, 1_000_000.0, round(d["shares"]*d["price"]*0.05,0), step=100.0)
    pe_ratio       = st.number_input("P/E Ratio", 1.0, 200.0, round(d["pe"],1), step=0.5)
    rf             = st.number_input("Risk-free Rate (%)", 0.0, 10.0, round(d["rf"]*100,2), step=0.05) / 100
    beta           = st.number_input("Beta", 0.1, 3.0, round(d["beta"],2), step=0.05)
    emp            = st.number_input("Equity Market Premium (%)", 2.0, 10.0, 5.5, step=0.1) / 100
    pretax_kd      = st.number_input("Pre-tax Cost of Debt (%)", 0.5, 15.0, round(d["kd"]*100,2), step=0.05) / 100
    tax_rate       = st.number_input("Tax Rate (%)", 5.0, 50.0, round(d["tax"]*100,1), step=0.5) / 100

ke           = capm(rf, beta, emp)
after_tax_kd = pretax_kd * (1 - tax_rate)
bb_ror       = buyback_rate_of_return(ke, current_price, expected_val)
accretion    = eps_accretion_test(pe_ratio, after_tax_kd)
ratio        = current_price / expected_val if expected_val else 1

r1, r2, r3 = st.columns(3)
r1.metric("Price / Fair Value", f"{ratio:.2f}x", "Undervalued ✅" if ratio < 1 else "Overvalued ⚠️")
r2.metric("Buyback Rate of Return", f"{bb_ror*100:.2f}%", f"vs cost of equity {ke*100:.2f}%")
r3.metric("Excess Return", f"{(bb_ror-ke)*100:.2f}%")

if ratio < 1.0:
    st.success(f"✅ **Golden Rule: FAVOURABLE** — buyback ROR {bb_ror*100:.2f}% > cost of equity {ke*100:.2f}%")
else:
    st.error(f"⚠️ **Golden Rule: UNFAVOURABLE** — stock is overvalued ({ratio:.2f}x fair value)")

st.divider()
st.subheader("EPS Accretion Test")
a1, a2, a3, a4 = st.columns(4)
a1.metric("P/E", f"{pe_ratio:.1f}x")
a2.metric("Earnings Yield (1/PE)", f"{accretion['earnings_yield']*100:.2f}%")
a3.metric("After-tax Interest Rate", f"{after_tax_kd*100:.2f}%")
a4.metric("Spread", f"{accretion['spread']*100:.2f}%",
          "Accretive ✅" if accretion['accretive'] else "Dilutive ⚠️",
          delta_color="normal" if accretion['accretive'] else "inverse")
st.caption("⚠️ EPS accretion ignores whether the price is above or below fair value — it is a misleading test on its own.")

st.divider()
st.subheader("Wealth Transfer Analysis")

wt_rows = []
for label, price_mult in [("Overvalued (2× FV)", 2.0), ("Undervalued (0.5× FV)", 0.5),
                            ("At Fair Value", 1.0), ("At Current Price", current_price / expected_val)]:
    bp = expected_val * price_mult
    wt = wealth_transfer(expected_val, shares_out, buyback_amount, bp)
    wt_rows.append({
        "Scenario": label,
        "Buyback Price ($)": f"${bp:,.2f}",
        "New Value / Share ($)": f"${wt.get('new_value_per_share',0):,.2f}",
        "Δ Value / Share ($)": f"{wt.get('value_change_per_share',0):+.2f}",
        "Wealth Transfer": wt.get("wealth_transfer", "—"),
    })
    
df = pd.DataFrame(wt_rows)
st.dataframe(df, use_container_width=True, hide_index=True)

deltas = [float(r["Δ Value / Share ($)"].replace("+","")) for r in wt_rows]
fig = go.Figure(go.Bar(
    x=[r["Scenario"] for r in wt_rows], y=deltas,
    marker_color=["#dc2626" if d < 0 else "#16a34a" if d > 0 else "#94a3b8" for d in deltas],
    text=[f"${d:+.2f}" for d in deltas], textposition="outside",
))
fig.add_hline(y=0, line=dict(color="#1e293b", width=1))
fig.update_layout(height=260, margin=dict(t=20,b=10),
                  yaxis_title="Δ Value / Share ($)", showlegend=False)
st.plotly_chart(fig, use_container_width=True)
