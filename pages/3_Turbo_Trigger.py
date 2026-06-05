"""
Chapters 3 & 6 — Expectations Infrastructure & Turbo Trigger
Sensitivity analysis to identify the high-leverage value driver.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.calculations import DCFInputs, run_dcf, sensitivity_table

st.markdown('<span class="chapter-badge">CHAPTERS 3 & 6</span>', unsafe_allow_html=True)
st.title("⚡ Turbo Trigger — Expectations Infrastructure")
st.caption(
    "Identify which value driver — Sales, Costs, or Investment — has the greatest leverage "
    "on shareholder value. The 'turbo trigger' is the one where realistic revisions produce "
    "the biggest price impact."
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Consensus PIE Baseline")
    base_sales   = st.number_input("Year 0 Sales ($M)", 1.0, 500_000.0, 3972.0, 50.0)
    pie_growth   = st.slider("PIE Sales Growth (%)", 0.0, 40.0, 7.0, 0.5) / 100
    pie_opm      = st.slider("PIE Op. Profit Margin (%)", 1.0, 60.0, 17.5, 0.5) / 100
    cash_tax     = st.slider("Cash Tax Rate (%)", 5.0, 50.0, 16.5, 0.5) / 100
    pie_ifcr     = st.slider("PIE Incr. Fixed-Cap Rate (%)", 0.0, 100.0, 10.0, 1.0) / 100
    pie_iwcr     = st.slider("PIE Incr. Working-Cap Rate (%)", 0.0, 60.0, 15.0, 1.0) / 100
    wacc         = st.slider("WACC (%)", 1.0, 20.0, 5.35, 0.05) / 100
    forecast_yrs = st.slider("Forecast Period (years)", 1, 20, 8, 1)
    inflation    = st.slider("Long-run Inflation (%)", 0.0, 6.0, 2.0, 0.25) / 100
    pp           = st.slider("Pricing Power (p)", 0.0, 1.0, 1.0, 0.05)
    excess_cash  = st.number_input("Excess Cash ($M)", 0.0, 100_000.0, 390.0, 10.0)
    debt         = st.number_input("Debt ($M)", 0.0, 100_000.0, 4100.0, 10.0)

    st.header("Scenario Ranges")
    st.subheader("Sales Growth")
    sg_lo = st.slider("Sales Growth — Low (%)", 0.0, 30.0, 3.0, 0.5) / 100
    sg_hi = st.slider("Sales Growth — High (%)", 0.0, 40.0, 11.0, 0.5) / 100

    st.subheader("Operating Margin")
    opm_lo = st.slider("OPM — Low (%)", 1.0, 50.0, max(1.0, pie_opm * 100 - 5.0), 0.5) / 100
    opm_hi = st.slider("OPM — High (%)", 1.0, 60.0, min(60.0, pie_opm * 100 + 5.0), 0.5) / 100

    st.subheader("Investment Rate (IFCR+IWCR)")
    inv_lo = st.slider("Investment Rate — Low (%)", 0.0, 60.0, max(0.0, (pie_ifcr + pie_iwcr) * 100 - 5.0), 1.0) / 100
    inv_hi = st.slider("Investment Rate — High (%)", 0.0, 100.0, min(100.0, (pie_ifcr + pie_iwcr) * 100 + 5.0), 1.0) / 100

# ── Baseline ──────────────────────────────────────────────────────────────────
base_inp = DCFInputs(
    base_sales=base_sales, sales_growth=pie_growth, op_margin=pie_opm,
    cash_tax_rate=cash_tax, ifcr=pie_ifcr, iwcr=pie_iwcr, wacc=wacc,
    forecast_years=forecast_yrs, inflation=inflation, pricing_power=pp,
    excess_cash=excess_cash, debt=debt,
)
base_sv = run_dcf(base_inp).shareholder_value

# ── Three trigger scenarios ───────────────────────────────────────────────────
def sv_at_growth(g):
    return run_dcf(DCFInputs(**{**base_inp.__dict__, 'sales_growth': g})).shareholder_value

def sv_at_opm(m):
    return run_dcf(DCFInputs(**{**base_inp.__dict__, 'op_margin': m})).shareholder_value

def sv_at_inv(combined):
    # split evenly between ifcr / iwcr
    half = combined / 2
    return run_dcf(DCFInputs(**{**base_inp.__dict__, 'ifcr': half, 'iwcr': half})).shareholder_value

sv_sg_lo = sv_at_growth(sg_lo)
sv_sg_hi = sv_at_growth(sg_hi)
sv_opm_lo = sv_at_opm(opm_lo)
sv_opm_hi = sv_at_opm(opm_hi)
sv_inv_lo = sv_at_inv(inv_lo)
sv_inv_hi = sv_at_inv(inv_hi)

# ── Hero metrics ──────────────────────────────────────────────────────────────
st.subheader("Baseline PIE Shareholder Value")
st.metric("PIE Shareholder Value", f"${base_sv:,.1f}M")

st.divider()
st.subheader("Scenario Impact by Trigger")

def pct_change(new, base):
    return (new - base) / abs(base) * 100 if base else 0

col1, col2, col3 = st.columns(3)
with col1:
    lo_chg = pct_change(sv_sg_lo, base_sv)
    hi_chg = pct_change(sv_sg_hi, base_sv)
    rng = sv_sg_hi - sv_sg_lo
    st.metric("📈 Sales Trigger", f"${rng:,.0f}M range")
    st.metric(f"Low ({sg_lo*100:.1f}%)", f"${sv_sg_lo:,.1f}M", f"{lo_chg:+.1f}%")
    st.metric(f"High ({sg_hi*100:.1f}%)", f"${sv_sg_hi:,.1f}M", f"{hi_chg:+.1f}%")

with col2:
    lo_chg2 = pct_change(sv_opm_lo, base_sv)
    hi_chg2 = pct_change(sv_opm_hi, base_sv)
    rng2 = sv_opm_hi - sv_opm_lo
    st.metric("💰 Cost / Margin Trigger", f"${rng2:,.0f}M range")
    st.metric(f"Low OPM ({opm_lo*100:.1f}%)", f"${sv_opm_lo:,.1f}M", f"{lo_chg2:+.1f}%")
    st.metric(f"High OPM ({opm_hi*100:.1f}%)", f"${sv_opm_hi:,.1f}M", f"{hi_chg2:+.1f}%")

with col3:
    lo_chg3 = pct_change(sv_inv_lo, base_sv)
    hi_chg3 = pct_change(sv_inv_hi, base_sv)
    rng3 = sv_inv_hi - sv_inv_lo
    st.metric("🏗️ Investment Trigger", f"${rng3:,.0f}M range")
    st.metric(f"Low rate ({inv_lo*100:.1f}%)", f"${sv_inv_lo:,.1f}M", f"{lo_chg3:+.1f}%")
    st.metric(f"High rate ({inv_hi*100:.1f}%)", f"${sv_inv_hi:,.1f}M", f"{hi_chg3:+.1f}%")

# ── Turbo trigger conclusion ───────────────────────────────────────────────────
ranges = {"Sales": rng, "Cost/Margin": rng2, "Investment": rng3}
turbo = max(ranges, key=ranges.get)
st.success(f"🎯 **Turbo Trigger: {turbo}** — widest shareholder-value impact (${max(ranges.values()):,.0f}M range)")

st.divider()

# ── Tornado chart ─────────────────────────────────────────────────────────────
st.subheader("Tornado Chart — Sensitivity to Each Trigger")

triggers = ["Sales Growth", "Op. Profit Margin", "Investment Rate"]
lo_vals  = [sv_sg_lo - base_sv, sv_opm_lo - base_sv, sv_inv_lo - base_sv]
hi_vals  = [sv_sg_hi - base_sv, sv_opm_hi - base_sv, sv_inv_hi - base_sv]

fig = go.Figure()
fig.add_bar(name="Downside", y=triggers, x=lo_vals, orientation="h",
            marker_color="#dc2626")
fig.add_bar(name="Upside", y=triggers, x=hi_vals, orientation="h",
            marker_color="#16a34a")
fig.add_vline(x=0, line=dict(color="#1e293b", width=1))
fig.update_layout(barmode="overlay", height=280, margin=dict(t=10, b=10),
                  xaxis_title="Change in Shareholder Value vs. PIE ($M)",
                  legend=dict(orientation="h", y=-0.25))
st.plotly_chart(fig, use_container_width=True)

# ── Full sensitivity sweep ────────────────────────────────────────────────────
st.subheader("Full Sensitivity Sweep")
tab1, tab2, tab3 = st.tabs(["Sales Growth", "Operating Margin", "WACC"])

with tab1:
    points = [g / 100 for g in range(0, 36)]
    rows = sensitivity_table(base_inp, "sales_growth", points)
    df = pd.DataFrame(rows)
    df.columns = ["Sales Growth (%)", "Shareholder Value ($M)"]
    df["Sales Growth (%)"] = (df["Sales Growth (%)"] * 100).round(1)
    df["Shareholder Value ($M)"] = df["Shareholder Value ($M)"].round(1)
    df["vs PIE"] = (df["Shareholder Value ($M)"] / base_sv - 1).mul(100).round(1).astype(str) + "%"

    fig2 = go.Figure()
    fig2.add_scatter(x=df["Sales Growth (%)"], y=df["Shareholder Value ($M)"],
                     mode="lines", line=dict(color="#2563eb", width=2))
    fig2.add_hline(y=base_sv, line=dict(color="#94a3b8", dash="dot"),
                   annotation_text="PIE baseline")
    fig2.add_vline(x=pie_growth * 100, line=dict(color="#f59e0b", dash="dot"),
                   annotation_text=f"PIE growth {pie_growth*100:.1f}%")
    fig2.update_layout(height=300, margin=dict(t=10, b=10),
                       xaxis_title="Sales Growth Rate (%)", yaxis_title="Shareholder Value ($M)")
    st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)

with tab2:
    opm_points = [m / 100 for m in range(1, 51)]
    rows2 = sensitivity_table(base_inp, "op_margin", opm_points)
    df2 = pd.DataFrame(rows2)
    df2.columns = ["OPM (%)", "Shareholder Value ($M)"]
    df2["OPM (%)"] = (df2["OPM (%)"] * 100).round(1)
    df2["Shareholder Value ($M)"] = df2["Shareholder Value ($M)"].round(1)
    fig3 = go.Figure()
    fig3.add_scatter(x=df2["OPM (%)"], y=df2["Shareholder Value ($M)"],
                     mode="lines", line=dict(color="#16a34a", width=2))
    fig3.add_vline(x=pie_opm * 100, line=dict(color="#f59e0b", dash="dot"),
                   annotation_text=f"PIE OPM {pie_opm*100:.1f}%")
    fig3.update_layout(height=300, margin=dict(t=10, b=10),
                       xaxis_title="Operating Profit Margin (%)", yaxis_title="Shareholder Value ($M)")
    st.plotly_chart(fig3, use_container_width=True)

with tab3:
    wacc_points = [w / 100 for w in range(2, 26)]
    rows3 = sensitivity_table(base_inp, "wacc", wacc_points)
    df3 = pd.DataFrame(rows3)
    df3.columns = ["WACC (%)", "Shareholder Value ($M)"]
    df3["WACC (%)"] = (df3["WACC (%)"] * 100).round(1)
    df3["Shareholder Value ($M)"] = df3["Shareholder Value ($M)"].round(1)
    fig4 = go.Figure()
    fig4.add_scatter(x=df3["WACC (%)"], y=df3["Shareholder Value ($M)"],
                     mode="lines", line=dict(color="#f59e0b", width=2))
    fig4.add_vline(x=wacc * 100, line=dict(color="#94a3b8", dash="dot"),
                   annotation_text=f"Baseline WACC {wacc*100:.2f}%")
    fig4.update_layout(height=300, margin=dict(t=10, b=10),
                       xaxis_title="WACC (%)", yaxis_title="Shareholder Value ($M)")
    st.plotly_chart(fig4, use_container_width=True)

st.divider()
st.subheader("📐 Turbo Trigger Framework (Ch 6)")
st.markdown("""
**Step 1** — Estimate high and low values for the **Sales Trigger**. Sales is typically the starting point
because revisions in sales expectations produce the most significant changes in shareholder value —
especially when the company earns above its cost of capital.

**Step 2** — **Select the Turbo Trigger.** Ask: how far would costs or investment rates need to vary 
from PIE to match the sales trigger's impact? If unrealistic, sales is the turbo trigger.

**Step 3** — **Refine** with leading indicators (customer retention, cycle times, store openings) 
that map to the turbo trigger.

**Value Factors (Expectations Infrastructure):**
| Factor | Value Driver Affected | Trigger |
|---|---|---|
| Volume | Sales Growth | Sales |
| Price & Mix | Sales Growth + OPM | Sales / Cost |
| Operating Leverage | OPM | Cost |
| Economies of Scale | OPM | Cost |
| Cost Efficiencies | OPM | Cost |
| Investment Efficiencies | Incremental Investment Rate | Investment |
""")
