"""
Ticker Lookup — fetches live data and runs full Expectations Investing analysis.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.data_fetcher import fetch_company_data
from utils.calculations import (
    DCFInputs, run_dcf, solve_pie_growth, solve_pie_forecast_period,
    Scenario, expected_value, capm,
)

st.markdown('<span class="chapter-badge">LIVE DATA</span>', unsafe_allow_html=True)
st.title("🔍 Ticker Lookup")
st.caption("Enter any stock ticker to run a full Expectations Investing analysis with live data.")

# ── API key input ─────────────────────────────────────────────────────────────
with st.expander("⚙️ Data source — enter your free FMP API key", expanded=not st.session_state.get("fmp_key")):
    st.markdown(
        "Yahoo Finance blocks hosted servers. Get a **free API key** at "
        "[financialmodelingprep.com](https://financialmodelingprep.com/developer/docs) "
        "(takes 30 seconds, 250 free calls/day) and paste it below."
    )
    fmp_key_input = st.text_input(
        "FMP API Key", 
        value=st.session_state.get("fmp_key", ""),
        type="password",
        placeholder="paste your key here",
    )
    if fmp_key_input:
        st.session_state["fmp_key"] = fmp_key_input
        st.success("API key saved for this session.")

fmp_key = st.session_state.get("fmp_key", "")

# ── Ticker input ──────────────────────────────────────────────────────────────
col_inp, col_btn = st.columns([3, 1])
with col_inp:
    ticker_input = st.text_input(
        "ticker", value=st.session_state.get("ticker", "DPZ"),
        placeholder="e.g. AAPL, MSFT, DPZ, TSLA",
        label_visibility="collapsed",
    )
with col_btn:
    fetch_btn = st.button("Analyse", type="primary", use_container_width=True)

st.caption("US equities: AAPL · UK add suffix: SHEL.L · European: SAP.DE")

# ── Fetch ─────────────────────────────────────────────────────────────────────
if fetch_btn and ticker_input:
    st.session_state["ticker"] = ticker_input.strip().upper()
    with st.spinner(f"Fetching {ticker_input.upper()}..."):
        try:
            data = fetch_company_data(ticker_input, fmp_api_key=fmp_key)
            st.session_state["company_data"] = data
            st.session_state["data_loaded"] = True
        except Exception as e:
            st.error(f"❌ {e}")
            st.session_state["data_loaded"] = False

# ── Analysis ──────────────────────────────────────────────────────────────────
if st.session_state.get("data_loaded") and st.session_state.get("company_data"):
    data = st.session_state["company_data"]

    if data.warnings:
        for w in data.warnings:
            st.caption(f"⚠️ {w}")

    # ── Company header ────────────────────────────────────────────────────────
    st.divider()
    st.subheader(f"{data.name}  ({data.ticker})")
    st.caption(f"{data.sector} · {data.industry} · {data.currency}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Price", f"${data.current_price:,.2f}")
    c2.metric("Market Cap", f"${data.market_cap_m:,.0f}M")
    c3.metric("Shares", f"{data.shares_outstanding_m:,.1f}M")
    c4.metric("Beta", f"{data.beta:.2f}")

    # ── Value drivers table ───────────────────────────────────────────────────
    st.divider()
    st.subheader("Value Drivers — 3-Year Historical Averages")
    drivers = pd.DataFrame([
        {"Driver": "Sales — most recent ($M)",         "Value": f"${data.base_sales_m:,.1f}M"},
        {"Driver": "Sales Growth — 3yr CAGR",          "Value": f"{data.sales_growth_3yr*100:.1f}%"},
        {"Driver": "Operating Profit Margin — 3yr avg","Value": f"{data.op_margin_3yr*100:.1f}%"},
        {"Driver": "Cash Tax Rate — 3yr avg",          "Value": f"{data.cash_tax_rate_3yr*100:.1f}%"},
        {"Driver": "Incr. Fixed-Capital Rate (IFCR)",  "Value": f"{data.ifcr_3yr*100:.1f}%"},
        {"Driver": "Incr. Working-Capital Rate (IWCR)","Value": f"{data.iwcr_3yr*100:.1f}%"},
        {"Driver": "Excess Cash & Non-Op Assets ($M)", "Value": f"${data.excess_cash_m:,.1f}M"},
        {"Driver": "Market Value of Debt ($M)",        "Value": f"${data.total_debt_m:,.1f}M"},
        {"Driver": "WACC",                             "Value": f"{data.wacc*100:.2f}%"},
    ])
    st.dataframe(drivers, use_container_width=True, hide_index=True)

    # ── DCF ───────────────────────────────────────────────────────────────────
    inp = DCFInputs(
        base_sales=data.base_sales_m,
        sales_growth=data.sales_growth_3yr,
        op_margin=data.op_margin_3yr,
        cash_tax_rate=data.cash_tax_rate_3yr,
        ifcr=data.ifcr_3yr,
        iwcr=data.iwcr_3yr,
        wacc=data.wacc,
        forecast_years=8,
        inflation=0.02,
        pricing_power=1.0,
        excess_cash=data.excess_cash_m,
        debt=data.total_debt_m,
    )
    res = run_dcf(inp)
    sv_per_share = res.shareholder_value / data.shares_outstanding_m if data.shares_outstanding_m else 0
    premium = (sv_per_share - data.current_price) / data.current_price * 100 if data.current_price else 0

    st.divider()
    st.subheader("DCF — Shareholder Value")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Shareholder Value", f"${res.shareholder_value:,.0f}M")
    m2.metric("Value Per Share", f"${sv_per_share:,.2f}", f"{premium:+.1f}% vs price")
    m3.metric("PV of FCFs", f"${res.pv_fcfs:,.0f}M")
    m4.metric("PV of Cont. Value", f"${res.pv_continuing_value:,.0f}M")

    df_yby = pd.DataFrame([{
        "Year": r.year,
        "Sales ($M)": round(r.sales, 1),
        "NOPAT ($M)": round(r.nopat, 1),
        "Investment ($M)": round(r.investment, 1),
        "FCF ($M)": round(r.fcf, 1),
        "PV of FCF ($M)": round(r.pv_fcf, 1),
    } for r in res.rows])
    st.dataframe(df_yby, use_container_width=True, hide_index=True)

    fig = go.Figure()
    fig.add_bar(x=df_yby["Year"], y=df_yby["NOPAT ($M)"],
                name="NOPAT", marker_color="#2563eb", opacity=0.8)
    fig.add_bar(x=df_yby["Year"], y=[-v for v in df_yby["Investment ($M)"]],
                name="Investment", marker_color="#f59e0b", opacity=0.8)
    fig.add_scatter(x=df_yby["Year"], y=df_yby["FCF ($M)"],
                    name="FCF", mode="lines+markers",
                    line=dict(color="#16a34a", width=2))
    fig.update_layout(barmode="relative", height=280, margin=dict(t=10, b=10),
                      xaxis_title="Forecast Year", yaxis_title="$M",
                      legend=dict(orientation="h", y=-0.3))
    st.plotly_chart(fig, use_container_width=True)

    # ── PIE ───────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Price-Implied Expectations (PIE)")

    implied_growth = solve_pie_growth(data.market_cap_m, inp)
    implied_period = solve_pie_forecast_period(data.market_cap_m, inp, max_years=25)

    p1, p2, p3 = st.columns(3)
    p1.metric("Market Cap (PIE target)", f"${data.market_cap_m:,.0f}M")
    p2.metric("PIE — Implied Sales Growth", f"{implied_growth*100:.2f}%",
              f"your assumption: {data.sales_growth_3yr*100:.1f}%")
    p3.metric("Market-Implied Forecast Period", f"{implied_period} years")

    if data.sales_growth_3yr > implied_growth * 1.1:
        st.success("Historical growth is above PIE — the market may be under-pricing this company's growth.")
    elif data.sales_growth_3yr < implied_growth * 0.9:
        st.warning("Historical growth is below PIE — the market expects an acceleration not seen historically.")
    else:
        st.info("Historical growth is broadly in line with PIE.")

    # ── Buy / Sell / Hold ─────────────────────────────────────────────────────
    st.divider()
    st.subheader("Buy / Sell / Hold — Expected Value")

    bear_sv = run_dcf(DCFInputs(**{**inp.__dict__, 'sales_growth': max(0.001, data.sales_growth_3yr - 0.04)})).shareholder_value
    bull_sv = run_dcf(DCFInputs(**{**inp.__dict__, 'sales_growth': data.sales_growth_3yr + 0.04})).shareholder_value
    bear_ps = bear_sv / data.shares_outstanding_m if data.shares_outstanding_m else 0
    base_ps = sv_per_share
    bull_ps = bull_sv / data.shares_outstanding_m if data.shares_outstanding_m else 0

    scenarios = [
        Scenario("Bear (growth −4%)", bear_ps, 0.25),
        Scenario("Base",              base_ps, 0.50),
        Scenario("Bull (growth +4%)", bull_ps, 0.25),
    ]
    ev = expected_value(scenarios)
    upside = (ev - data.current_price) / data.current_price * 100 if data.current_price else 0

    sc_df = pd.DataFrame([{
        "Scenario": s.label,
        "Value / Share ($)": f"${s.stock_value:,.2f}",
        "Probability": f"{s.probability*100:.0f}%",
        "Weighted Value ($)": f"${s.weighted:,.2f}",
    } for s in scenarios] + [{
        "Scenario": "Expected Value (EV)",
        "Value / Share ($)": "",
        "Probability": "100%",
        "Weighted Value ($)": f"${ev:,.2f}",
    }])
    st.dataframe(sc_df, use_container_width=True, hide_index=True)

    e1, e2 = st.columns(2)
    e1.metric("Expected Value", f"${ev:,.2f}", f"{upside:+.1f}% vs current ${data.current_price:.2f}")
    if upside > 10:
        e2.success("🟢 BUY — EV exceeds price by more than 10%")
    elif upside < -10:
        e2.error("🔴 SELL — Price exceeds EV by more than 10%")
    else:
        e2.warning("🟡 HOLD — within ±10% of EV")

    # ── WACC breakdown ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("WACC Breakdown")
    ke = capm(data.rf_rate, data.beta, data.equity_market_premium)
    wacc_df = pd.DataFrame([
        {"Component": "Risk-free rate (10yr Treasury)",  "Value": f"{data.rf_rate*100:.2f}%"},
        {"Component": "Beta",                            "Value": f"{data.beta:.2f}"},
        {"Component": "Equity market premium",           "Value": f"{data.equity_market_premium*100:.1f}%"},
        {"Component": "Cost of equity (CAPM)",           "Value": f"{ke*100:.2f}%"},
        {"Component": "Pre-tax cost of debt",            "Value": f"{data.pretax_cost_of_debt*100:.2f}%"},
        {"Component": "After-tax cost of debt",          "Value": f"{data.pretax_cost_of_debt*(1-data.cash_tax_rate_3yr)*100:.2f}%"},
        {"Component": "Equity weight",                   "Value": f"{data.equity_weight*100:.1f}%"},
        {"Component": "Debt weight",                     "Value": f"{data.debt_weight*100:.1f}%"},
        {"Component": "WACC",                            "Value": f"{data.wacc*100:.2f}%"},
    ])
    st.dataframe(wacc_df, use_container_width=True, hide_index=True)
