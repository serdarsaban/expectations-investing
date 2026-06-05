"""
Chapter 11 — Share Buybacks
Golden Rule analyser, EPS accretion test, wealth transfer scenarios.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.calculations import buyback_rate_of_return, eps_accretion_test, wealth_transfer, capm

st.markdown('<span class="chapter-badge">CHAPTER 11</span>', unsafe_allow_html=True)
st.title("🔁 Share Buybacks — Golden Rule Analyser")
st.caption(
    "**Golden Rule:** Repurchase shares only when the stock trades below Expected Value "
    "and no better internal investments exist."
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Company & Market Data")
    current_price    = st.number_input("Current Stock Price ($)", 0.01, 100_000.0, 22.85, 0.01)
    expected_val     = st.number_input("Expected Value / Fair Value ($)", 0.01, 100_000.0, 24.75, 0.01)
    shares_out       = st.number_input("Shares Outstanding (M)", 0.1, 100_000.0, 10_000.0, 100.0)
    pe_ratio         = st.slider("P/E Ratio", 1.0, 100.0, 25.0, 0.5)
    buyback_amount   = st.number_input("Total Buyback Program ($M)", 1.0, 1_000_000.0, 20_000.0, 100.0)

    st.header("Cost of Capital")
    rf    = st.slider("Risk-free Rate (%)", 0.0, 10.0, 0.65, 0.05, key="bb_rf") / 100
    beta  = st.slider("Beta", 0.1, 3.0, 1.0, 0.05, key="bb_beta")
    emp   = st.slider("Equity Market Premium (%)", 2.0, 10.0, 5.1, 0.1, key="bb_emp") / 100
    ke    = capm(rf, beta, emp)
    st.caption(f"Cost of equity (CAPM) = {ke*100:.2f}%")

    st.header("EPS Accretion Test")
    pretax_kd  = st.slider("Pre-tax Cost of Debt (%)", 0.5, 15.0, 4.55, 0.05) / 100
    tax_rate   = st.slider("Tax Rate (%)", 5.0, 50.0, 16.5, 0.5) / 100
    after_tax_kd = pretax_kd * (1 - tax_rate)

# ── Calculations ──────────────────────────────────────────────────────────────
bb_ror = buyback_rate_of_return(ke, current_price, expected_val)
accretion = eps_accretion_test(pe_ratio, after_tax_kd)
wt_over   = wealth_transfer(expected_val, shares_out, buyback_amount, current_price * 2)   # overvalued
wt_under  = wealth_transfer(expected_val, shares_out, buyback_amount, current_price * 0.5) # undervalued
wt_fair   = wealth_transfer(expected_val, shares_out, buyback_amount, expected_val)         # fair value
wt_actual = wealth_transfer(expected_val, shares_out, buyback_amount, current_price)        # current

ratio = current_price / expected_val

# ── Golden Rule ───────────────────────────────────────────────────────────────
st.subheader("Golden Rule Assessment")

r1, r2, r3 = st.columns(3)
r1.metric("Current Price / Fair Value", f"{ratio:.2f}x",
          "Undervalued ✅" if ratio < 1.0 else "Overvalued ⚠️")
r2.metric("Buyback Rate of Return", f"{bb_ror*100:.2f}%",
          f"vs. Cost of Equity {ke*100:.2f}%")
r3.metric("Excess return from buyback", f"{(bb_ror - ke)*100:.2f}%",
          delta_color="normal")

if ratio < 1.0:
    st.success(
        f"✅ **Golden Rule: FAVOURABLE.** At ${current_price:.2f} vs. fair value ${expected_val:.2f}, "
        f"buybacks generate a {bb_ror*100:.2f}% return — above the {ke*100:.2f}% cost of equity."
    )
else:
    st.error(
        f"⚠️ **Golden Rule: UNFAVOURABLE.** Stock is overvalued ({ratio:.2f}x fair value). "
        f"Buybacks at this price destroy value for ongoing shareholders."
    )

st.divider()

# ── Buyback rate of return breakdown ─────────────────────────────────────────
st.subheader("Buyback Rate of Return")
st.markdown("""
<div class="formula-box">Buyback ROR = Cost of Equity / (Price / Expected Value)</div>
""", unsafe_allow_html=True)
st.markdown(f"""
| Component | Value |
|---|---|
| Cost of Equity (CAPM) | {ke*100:.2f}% |
| Current Price | ${current_price:.2f} |
| Expected Value | ${expected_val:.2f} |
| Price / EV ratio | {ratio:.3f} |
| **Buyback ROR** | **{bb_ror*100:.2f}%** |
""")

st.divider()

# ── EPS accretion test ────────────────────────────────────────────────────────
st.subheader("EPS Accretion Test")
st.markdown("""
<div class="formula-box">Accretive when: Earnings Yield (1/P·E) > After-tax Interest Rate</div>
""", unsafe_allow_html=True)

a1, a2, a3, a4 = st.columns(4)
a1.metric("P/E Ratio", f"{pe_ratio:.1f}x")
a2.metric("Earnings Yield (1/P·E)", f"{accretion['earnings_yield']*100:.2f}%")
a3.metric("After-tax Interest Rate", f"{after_tax_kd*100:.2f}%")
a4.metric("Spread", f"{accretion['spread']*100:.2f}%",
          "EPS Accretive ✅" if accretion['accretive'] else "EPS Dilutive ⚠️",
          delta_color="normal" if accretion['accretive'] else "inverse")

st.caption(
    "⚠️ EPS accretion is a misleading test — it ignores whether the price is above or below "
    "fair value. A buyback can be EPS-accretive while destroying shareholder value."
)

st.divider()

# ── Wealth transfer table ─────────────────────────────────────────────────────
st.subheader("Wealth Transfer Scenarios (Table 11.2)")
st.caption(f"Company fair value = ${expected_val:.2f} | Buyback program = ${buyback_amount:,.0f}M")

wt_rows = []
for label, price, result in [
    ("A — Overvalued", current_price * 2, wt_over),
    ("B — Undervalued", current_price * 0.5, wt_under),
    ("C — At Fair Value (= Dividend)", expected_val, wt_fair),
    ("D — Current Price", current_price, wt_actual),
]:
    wt_rows.append({
        "Scenario": label,
        "Buyback Price ($)": f"${price:.2f}",
        "Shares Bought (M)": f"{result.get('shares_bought', 0):,.1f}",
        "New Value / Share ($)": f"${result.get('new_value_per_share', 0):,.2f}",
        "Δ Value / Share ($)": f"{result.get('value_change_per_share', 0):+.2f}",
        "Wealth Transfer": result.get('wealth_transfer', '—'),
    })

df = pd.DataFrame(wt_rows)
st.dataframe(df, use_container_width=True, hide_index=True)

# Chart
labels = [r["Scenario"] for r in wt_rows]
deltas = [float(r["Δ Value / Share ($)"].replace("+", "")) for r in wt_rows]
colors = ["#dc2626" if d < 0 else "#16a34a" if d > 0 else "#94a3b8" for d in deltas]

fig = go.Figure(go.Bar(
    x=labels, y=deltas, marker_color=colors,
    text=[f"${d:+.2f}" for d in deltas], textposition="outside"
))
fig.add_hline(y=0, line=dict(color="#1e293b", width=1))
fig.update_layout(height=280, margin=dict(t=20, b=10),
                  yaxis_title="Change in Value / Share ($)", showlegend=False)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Case study ────────────────────────────────────────────────────────────────
with st.expander("📚 Case Study: Microsoft Dutch Auction 2006"):
    st.markdown("""
    - **Signal:** $20 billion Dutch Auction buyback announced.  
    - **Stock price:** $22.85  
    - **Auction range:** $22.50–$24.75  
    - **Forensic insight:** The premium range (up to $24.75) signalled management's conviction that the stock was undervalued — they would not pay up to $24.75 unless they believed intrinsic value was higher.  
    - **Lesson:** When management runs a Dutch Auction at a premium to market, it is a credible signal of undervaluation.  
    - **Application:** Run the Buyback ROR and compare to cost of equity. If ROR > Ke, the buyback is value-enhancing for ongoing shareholders.
    """)

st.divider()
st.subheader("📐 Key Principles (Ch 11)")
st.markdown("""
1. **Golden Rule** — Repurchase only when: (a) price < expected value, and (b) no internal investments offer better risk-adjusted returns.
2. **Wealth Transfer** — Buybacks above fair value transfer wealth from ongoing shareholders to sellers. Buybacks below fair value do the reverse.
3. **EPS Accretion is misleading** — A buyback can boost EPS and still destroy value if done above fair value.
4. **Credible signals** — Dutch Auction premiums, accelerated buybacks, and CEO insider purchases alongside buyback announcements increase signal quality.
5. **Asset growth warning** — High asset growth (balance sheet expansion) often predicts low future abnormal returns.
""")
