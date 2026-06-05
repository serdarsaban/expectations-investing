"""Chapter 2 — DCF Engine, pre-filled from Ticker Lookup session state."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.calculations import DCFInputs, run_dcf

st.markdown('<span class="chapter-badge">CHAPTER 2</span>', unsafe_allow_html=True)
st.title("🏗️ DCF Engine — Shareholder Value Road Map")

data = st.session_state.get("company_data")

if data:
    st.caption(f"Data loaded for **{data.name} ({data.ticker})**. Go to Ticker Lookup to change company.")
    defaults = dict(
        base_sales=data.base_sales_m,
        sales_growth=data.sales_growth_3yr,
        op_margin=data.op_margin_3yr,
        cash_tax_rate=data.cash_tax_rate_3yr,
        ifcr=data.ifcr_3yr,
        iwcr=data.iwcr_3yr,
        wacc=data.wacc,
        excess_cash=data.excess_cash_m,
        debt=data.total_debt_m,
    )
else:
    st.info("No ticker loaded — using default inputs. Go to **Ticker Lookup** to load a company.")
    defaults = dict(
        base_sales=100.0, sales_growth=0.10, op_margin=0.15,
        cash_tax_rate=0.25, ifcr=0.15, iwcr=0.10, wacc=0.08,
        excess_cash=0.0, debt=0.0,
    )

with st.sidebar:
    st.header("Inputs")
    base_sales   = st.number_input("Year 0 Sales ($M)", 1.0, 500_000.0, round(defaults["base_sales"], 1), step=10.0)
    sales_growth = st.number_input("Sales Growth Rate (%)", -20.0, 60.0, round(defaults["sales_growth"]*100, 1), step=0.5) / 100
    op_margin    = st.number_input("Operating Profit Margin (%)", 0.1, 70.0, round(defaults["op_margin"]*100, 1), step=0.5) / 100
    cash_tax     = st.number_input("Cash Tax Rate (%)", 5.0, 50.0, round(defaults["cash_tax_rate"]*100, 1), step=0.5) / 100
    ifcr         = st.number_input("Incr. Fixed-Capital Rate (%)", 0.0, 100.0, round(defaults["ifcr"]*100, 1), step=1.0) / 100
    iwcr         = st.number_input("Incr. Working-Capital Rate (%)", 0.0, 60.0, round(defaults["iwcr"]*100, 1), step=1.0) / 100
    wacc         = st.number_input("WACC (%)", 1.0, 25.0, round(defaults["wacc"]*100, 2), step=0.25) / 100
    forecast_yrs = st.number_input("Forecast Period (years)", 1, 20, 8, step=1)
    inflation    = st.number_input("Long-run Inflation (%)", 0.0, 6.0, 2.0, step=0.25) / 100
    pp           = st.number_input("Pricing Power (p)", 0.0, 1.0, 1.0, step=0.05)
    excess_cash  = st.number_input("Excess Cash ($M)", 0.0, 1_000_000.0, round(defaults["excess_cash"], 1), step=10.0)
    debt         = st.number_input("Debt ($M)", 0.0, 1_000_000.0, round(defaults["debt"], 1), step=10.0)

inp = DCFInputs(
    base_sales=base_sales, sales_growth=sales_growth, op_margin=op_margin,
    cash_tax_rate=cash_tax, ifcr=ifcr, iwcr=iwcr, wacc=wacc,
    forecast_years=int(forecast_yrs), inflation=inflation, pricing_power=pp,
    excess_cash=excess_cash, debt=debt,
)
res = run_dcf(inp)

# Formula strip
y1 = res.rows[0]
f1, f2, f3, f4, f5, f6, f7 = st.columns(7)
for col, lbl, val in zip(
    [f1, f2, f3, f4, f5, f6, f7],
    ["Sales Y1", "× OPM", "= Op. Profit", "− Tax", "= NOPAT", "− Investment", "= FCF"],
    [f"${y1.sales:,.1f}M", f"{op_margin*100:.1f}%", f"${y1.op_profit:,.1f}M",
     f"${y1.op_profit*cash_tax:,.1f}M", f"${y1.nopat:,.1f}M",
     f"${y1.investment:,.1f}M", f"${y1.fcf:,.1f}M"],
):
    col.metric(lbl, val)

st.divider()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Shareholder Value", f"${res.shareholder_value:,.1f}M")
m2.metric("PV of FCFs", f"${res.pv_fcfs:,.1f}M")
m3.metric("PV of Cont. Value", f"${res.pv_continuing_value:,.1f}M")
m4.metric("Operating Value", f"${res.operating_value:,.1f}M")

st.divider()

tab1, tab2, tab3 = st.tabs(["Year-by-Year", "Value Composition", "Formulas"])

with tab1:
    df = pd.DataFrame([{
        "Year": r.year, "Sales ($M)": round(r.sales, 1),
        "Op. Profit ($M)": round(r.op_profit, 1), "NOPAT ($M)": round(r.nopat, 1),
        "Investment ($M)": round(r.investment, 1), "FCF ($M)": round(r.fcf, 1),
        "PV of FCF ($M)": round(r.pv_fcf, 1),
    } for r in res.rows])
    st.dataframe(df, use_container_width=True, hide_index=True)

    fig = go.Figure()
    fig.add_bar(x=df["Year"], y=df["NOPAT ($M)"], name="NOPAT", marker_color="#2563eb", opacity=0.8)
    fig.add_bar(x=df["Year"], y=[-v for v in df["Investment ($M)"]], name="Investment", marker_color="#f59e0b", opacity=0.8)
    fig.add_scatter(x=df["Year"], y=df["FCF ($M)"], name="FCF", mode="lines+markers", line=dict(color="#16a34a", width=2))
    fig.update_layout(barmode="relative", height=300, margin=dict(t=10,b=10),
                      xaxis_title="Year", yaxis_title="$M", legend=dict(orientation="h", y=-0.3))
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    col_pie, col_wf = st.columns(2)
    with col_pie:
        fig2 = go.Figure(go.Pie(
            labels=["PV FCFs", "PV Cont. Value", "Excess Cash"],
            values=[max(0, res.pv_fcfs), max(0, res.pv_continuing_value), max(0, excess_cash)],
            hole=0.45, marker_colors=["#2563eb", "#16a34a", "#f59e0b"],
        ))
        fig2.update_layout(height=280, margin=dict(t=10, b=10), showlegend=True)
        st.plotly_chart(fig2, use_container_width=True)
    with col_wf:
        fig3 = go.Figure(go.Waterfall(
            x=["PV FCFs", "+ PV CV", "+ Non-Op", "− Debt", "= SV"],
            y=[res.pv_fcfs, res.pv_continuing_value, excess_cash, -debt, 0],
            measure=["relative","relative","relative","relative","total"],
            increasing=dict(marker_color="#2563eb"),
            decreasing=dict(marker_color="#dc2626"),
            totals=dict(marker_color="#1e293b"),
        ))
        fig3.update_layout(height=280, margin=dict(t=10, b=10), yaxis_title="$M", showlegend=False)
        st.plotly_chart(fig3, use_container_width=True)

with tab3:
    for f in [
        "Sales × OPM = Operating Profit",
        "Operating Profit × (1 – Tax) = NOPAT",
        "Investment = (IFCR + IWCR) × ΔSales",
        "FCF = NOPAT – Investment",
        "CV = NOPAT_N × (1 + i·p) / (WACC – i·p)",
        "Shareholder Value = PV(FCFs) + PV(CV) + Non-Op Assets – Debt",
    ]:
        st.markdown(f'<div class="formula-box">{f}</div>', unsafe_allow_html=True)
