"""Chapters 3 & 6 — Turbo Trigger, pre-filled from session state."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.calculations import DCFInputs, run_dcf, sensitivity_table

st.markdown('<span class="chapter-badge">CHAPTERS 3 & 6</span>', unsafe_allow_html=True)
st.title("⚡ Turbo Trigger — Expectations Infrastructure")

data = st.session_state.get("company_data")

if data:
    st.caption(f"Data loaded for **{data.name} ({data.ticker})**.")
    d = dict(base_sales=data.base_sales_m, sg=data.sales_growth_3yr,
             opm=data.op_margin_3yr, tax=data.cash_tax_rate_3yr,
             ifcr=data.ifcr_3yr, iwcr=data.iwcr_3yr, wacc=data.wacc,
             excess_cash=data.excess_cash_m, debt=data.total_debt_m)
else:
    st.info("No ticker loaded — using Domino's defaults. Go to **Ticker Lookup** to load a company.")
    d = dict(base_sales=3972.0, sg=0.07, opm=0.175, tax=0.165,
             ifcr=0.10, iwcr=0.15, wacc=0.0535, excess_cash=390.0, debt=4100.0)

with st.sidebar:
    st.header("Baseline (PIE)")
    base_sales   = st.number_input("Year 0 Sales ($M)", 1.0, 500_000.0, round(d["base_sales"],1), step=50.0)
    pie_growth   = st.number_input("PIE Sales Growth (%)", 0.0, 40.0, round(d["sg"]*100,1), step=0.5) / 100
    pie_opm      = st.number_input("PIE Op. Margin (%)", 1.0, 60.0, round(d["opm"]*100,1), step=0.5) / 100
    cash_tax     = st.number_input("Cash Tax Rate (%)", 5.0, 50.0, round(d["tax"]*100,1), step=0.5) / 100
    pie_ifcr     = st.number_input("IFCR (%)", 0.0, 100.0, round(d["ifcr"]*100,1), step=1.0) / 100
    pie_iwcr     = st.number_input("IWCR (%)", 0.0, 60.0, round(d["iwcr"]*100,1), step=1.0) / 100
    wacc         = st.number_input("WACC (%)", 1.0, 20.0, round(d["wacc"]*100,2), step=0.05) / 100
    forecast_yrs = st.number_input("Forecast Period (years)", 1, 20, 8, step=1)
    inflation    = st.number_input("Inflation (%)", 0.0, 6.0, 2.0, step=0.25) / 100
    pp           = st.number_input("Pricing Power (p)", 0.0, 1.0, 1.0, step=0.05)
    excess_cash  = st.number_input("Excess Cash ($M)", 0.0, 1_000_000.0, round(d["excess_cash"],1), step=10.0)
    debt         = st.number_input("Debt ($M)", 0.0, 1_000_000.0, round(d["debt"],1), step=10.0)

    st.header("Scenario Ranges")
    sg_lo  = st.number_input("Sales Growth — Low (%)",  0.0, 30.0, max(0.0, round(d["sg"]*100-4,1)), step=0.5) / 100
    sg_hi  = st.number_input("Sales Growth — High (%)", 0.0, 50.0, round(d["sg"]*100+4,1), step=0.5) / 100
    opm_lo = st.number_input("OPM — Low (%)",  1.0, 50.0, max(1.0, round(d["opm"]*100-4,1)), step=0.5) / 100
    opm_hi = st.number_input("OPM — High (%)", 1.0, 60.0, round(d["opm"]*100+4,1), step=0.5) / 100
    base_inv = (d["ifcr"] + d["iwcr"]) * 100
    inv_lo = st.number_input("Inv. Rate — Low (%)",  0.0, 60.0, max(0.0, round(base_inv-5,1)), step=1.0) / 100
    inv_hi = st.number_input("Inv. Rate — High (%)", 0.0, 100.0, round(base_inv+5,1), step=1.0) / 100

base_inp = DCFInputs(
    base_sales=base_sales, sales_growth=pie_growth, op_margin=pie_opm,
    cash_tax_rate=cash_tax, ifcr=pie_ifcr, iwcr=pie_iwcr, wacc=wacc,
    forecast_years=int(forecast_yrs), inflation=inflation, pricing_power=pp,
    excess_cash=excess_cash, debt=debt,
)
base_sv = run_dcf(base_inp).shareholder_value

def sv(g=None, opm=None, inv=None):
    kw = base_inp.__dict__.copy()
    if g   is not None: kw["sales_growth"] = g
    if opm is not None: kw["op_margin"]    = opm
    if inv is not None: kw["ifcr"] = kw["iwcr"] = inv / 2
    return run_dcf(DCFInputs(**kw)).shareholder_value

sv_sg_lo  = sv(g=sg_lo);   sv_sg_hi  = sv(g=sg_hi)
sv_opm_lo = sv(opm=opm_lo); sv_opm_hi = sv(opm=opm_hi)
sv_inv_lo = sv(inv=inv_lo); sv_inv_hi = sv(inv=inv_hi)

rng_sg  = sv_sg_hi  - sv_sg_lo
rng_opm = sv_opm_hi - sv_opm_lo
rng_inv = sv_inv_hi - sv_inv_lo
ranges  = {"Sales": rng_sg, "Cost/Margin": rng_opm, "Investment": rng_inv}
turbo   = max(ranges, key=ranges.get)

st.metric("PIE Baseline Shareholder Value", f"${base_sv:,.1f}M")
st.success(f"🎯 **Turbo Trigger: {turbo}** — widest value range (${max(ranges.values()):,.0f}M)")

st.divider()
c1, c2, c3 = st.columns(3)
for col, label, lo, hi, lo_v, hi_v, rng in [
    (c1, "📈 Sales Trigger", sg_lo, sg_hi, sv_sg_lo, sv_sg_hi, rng_sg),
    (c2, "💰 Margin Trigger", opm_lo, opm_hi, sv_opm_lo, sv_opm_hi, rng_opm),
    (c3, "🏗️ Investment Trigger", inv_lo, inv_hi, sv_inv_lo, sv_inv_hi, rng_inv),
]:
    with col:
        st.metric(label, f"${rng:,.0f}M range")
        st.metric(f"Low ({lo*100:.1f}%)", f"${lo_v:,.1f}M", f"{(lo_v-base_sv)/abs(base_sv)*100:+.1f}%")
        st.metric(f"High ({hi*100:.1f}%)", f"${hi_v:,.1f}M", f"{(hi_v-base_sv)/abs(base_sv)*100:+.1f}%")

st.divider()
st.subheader("Tornado Chart")
fig = go.Figure()
fig.add_bar(name="Downside", y=["Sales Growth","Op. Margin","Investment Rate"],
            x=[sv_sg_lo-base_sv, sv_opm_lo-base_sv, sv_inv_lo-base_sv],
            orientation="h", marker_color="#dc2626")
fig.add_bar(name="Upside", y=["Sales Growth","Op. Margin","Investment Rate"],
            x=[sv_sg_hi-base_sv, sv_opm_hi-base_sv, sv_inv_hi-base_sv],
            orientation="h", marker_color="#16a34a")
fig.add_vline(x=0, line=dict(color="#1e293b", width=1))
fig.update_layout(barmode="overlay", height=260, margin=dict(t=10,b=10),
                  xaxis_title="Change vs. PIE ($M)", legend=dict(orientation="h",y=-0.3))
st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("Full Sensitivity — Sales Growth")
points = [g/100 for g in range(0, 36)]
rows = sensitivity_table(base_inp, "sales_growth", points)
df = pd.DataFrame(rows)
df.columns = ["Sales Growth (%)", "Shareholder Value ($M)"]
df["Sales Growth (%)"] = (df["Sales Growth (%)"] * 100).round(1)
df["Shareholder Value ($M)"] = df["Shareholder Value ($M)"].round(1)
fig2 = go.Figure()
fig2.add_scatter(x=df["Sales Growth (%)"], y=df["Shareholder Value ($M)"],
                 mode="lines", line=dict(color="#2563eb", width=2))
fig2.add_hline(y=base_sv, line=dict(color="#94a3b8", dash="dot"), annotation_text="PIE baseline")
fig2.add_vline(x=pie_growth*100, line=dict(color="#f59e0b", dash="dot"),
               annotation_text=f"PIE {pie_growth*100:.1f}%")
fig2.update_layout(height=300, margin=dict(t=10,b=10),
                   xaxis_title="Sales Growth Rate (%)", yaxis_title="Shareholder Value ($M)")
st.plotly_chart(fig2, use_container_width=True)
