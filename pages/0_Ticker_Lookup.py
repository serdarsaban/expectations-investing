"""
Ticker Lookup — fetches live data and pre-fills all modules.
This is the entry point when using real company data.
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
st.caption("Enter any stock ticker to auto-populate all modules with real financials from Yahoo Finance.")

# ── Ticker input ──────────────────────────────────────────────────────────────
col_inp, col_btn = st.columns([3, 1])
with col_inp:
    ticker_input = st.text_input(
        "Stock ticker",
        value=st.session_state.get("ticker", ""),
        placeholder="e.g. AAPL, MSFT, DPZ, TSLA",
        label_visibility="collapsed",
    )
with col_btn:
    fetch_btn = st.button("Load Data", type="primary", use_container_width=True)

st.caption("Supports US equities (NYSE/NASDAQ). For UK stocks use suffix: SHEL.L  For European: SAP.DE")

# ── Fetch ─────────────────────────────────────────────────────────────────────
if fetch_btn and ticker_input:
    st.session_state["ticker"] = ticker_input.strip().upper()
    with st.spinner(f"Fetching data for {ticker_input.upper()}..."):
        try:
            data = fetch_company_data(ticker_input)
            st.session_state["company_data"] = data
            st.session_state["data_loaded"] = True
        except Exception as e:
            st.error(f"❌ {e}")
            st.session_state["data_loaded"] = False

# ── Display if data loaded ────────────────────────────────────────────────────
if st.session_state.get("data_loaded") and st.session_state.get("company_data"):
    data = st.session_state["company_data"]

    # Warnings
    if data.warnings:
        with st.expander("⚠️ Data quality notes", expanded=False):
            for w in data.warnings:
                st.warning(w)

    st.divider()

    # ── Company header ────────────────────────────────────────────────────────
    st.subheader(f"{data.name} ({data.ticker})")
    st.caption(f"{data.sector} → {data.industry} | {data.currency}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Price", f"${data.current_price:,.2f}")
    c2.metric("Market Cap", f"${data.market_cap_m:,.0f}M")
    c3.metric("Shares Outstanding", f"{data.shares_outstanding_m:,.1f}M")
    c4.metric("Beta", f"{data.beta:.2f}")

    st.divider()

    # ── Value drivers (editable) ──────────────────────────────────────────────
    st.subheader("📊 Value Drivers — 3-Year Historical Averages")
    st.caption("Pre-filled from Yahoo Finance financials. Adjust before running analysis.")

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**Operating drivers**")
        sales_growth = st.slider("Sales Growth Rate (%)",
            -20.0, 60.0, round(data.sales_growth_3yr * 100, 1), 0.5) / 100
        op_margin = st.slider("Operating Profit Margin (%)",
            0.1, 70.0, round(data.op_margin_3yr * 100, 1), 0.5) / 100
        cash_tax = st.slider("Cash Tax Rate (%)",
            5.0, 50.0, round(data.cash_tax_rate_3yr * 100, 1), 0.5) / 100

    with col_r:
        st.markdown("**Investment rates**")
        ifcr = st.slider("Incr. Fixed-Capital Rate (%)",
            0.0, 80.0, round(data.ifcr_3yr * 100, 1), 0.5) / 100
        iwcr = st.slider("Incr. Working-Capital Rate (%)",
            0.0, 50.0, round(data.iwcr_3yr * 100, 1), 0.5) / 100
        forecast_yrs = st.slider("Forecast Period (years)", 1, 20, 8, 1)

    st.markdown("**Capital structure**")
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        wacc = st.slider("WACC (%)",
            1.0, 25.0, round(data.wacc * 100, 2), 0.05) / 100
    with cc2:
        inflation = st.slider("Long-run Inflation (%)", 0.0, 6.0, 2.0, 0.25) / 100
    with cc3:
        pp = st.slider("Pricing Power (p)", 0.0, 1.0, 1.0, 0.05)

    excess_cash = st.number_input("Excess Cash & Non-Op Assets ($M)",
        0.0, 1_000_000.0, round(data.excess_cash_m, 1), 10.0)
    debt = st.number_input("Market Value of Debt ($M)",
        0.0, 1_000_000.0, round(data.total_debt_m, 1), 10.0)

    # ── Build DCF inputs ──────────────────────────────────────────────────────
    inp = DCFInputs(
        base_sales=data.base_sales_m,
        sales_growth=sales_growth,
        op_margin=op_margin,
        cash_tax_rate=cash_tax,
        ifcr=ifcr,
        iwcr=iwcr,
        wacc=wacc,
        forecast_years=forecast_yrs,
        inflation=inflation,
        pricing_power=pp,
        excess_cash=excess_cash,
        debt=debt,
    )
    res = run_dcf(inp)

    st.divider()

    # ── DCF result ────────────────────────────────────────────────────────────
    st.subheader("🏗️ DCF — Shareholder Value")

    sv_per_share = res.shareholder_value / data.shares_outstanding_m if data.shares_outstanding_m else 0
    premium = (sv_per_share - data.current_price) / data.current_price * 100 if data.current_price else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Shareholder Value", f"${res.shareholder_value:,.0f}M")
    m2.metric("Value Per Share", f"${sv_per_share:,.2f}",
              f"{premium:+.1f}% vs current price")
    m3.metric("PV of FCFs", f"${res.pv_fcfs:,.0f}M")
    m4.metric("PV of Cont. Value", f"${res.pv_continuing_value:,.0f}M")

    # FCF bar chart
    df_yby = pd.DataFrame([{
        "Year": r.year,
        "NOPAT ($M)": round(r.nopat, 1),
        "Investment ($M)": round(r.investment, 1),
        "FCF ($M)": round(r.fcf, 1),
        "PV FCF ($M)": round(r.pv_fcf, 1),
    } for r in res.rows])

    fig = go.Figure()
    fig.add_bar(x=df_yby["Year"], y=df_yby["NOPAT ($M)"],
                name="NOPAT", marker_color="#2563eb", opacity=0.8)
    fig.add_bar(x=df_yby["Year"], y=[-v for v in df_yby["Investment ($M)"]],
                name="Investment", marker_color="#f59e0b", opacity=0.8)
    fig.add_scatter(x=df_yby["Year"], y=df_yby["FCF ($M)"],
                    name="FCF", mode="lines+markers",
                    line=dict(color="#16a34a", width=2))
    fig.update_layout(barmode="relative", height=300,
                      margin=dict(t=10, b=10),
                      xaxis_title="Forecast Year", yaxis_title="$M",
                      legend=dict(orientation="h", y=-0.25))
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── PIE ───────────────────────────────────────────────────────────────────
    st.subheader("🔎 Price-Implied Expectations (PIE)")
    st.caption("What growth rate is the market currently pricing in?")

    target_sv = data.market_cap_m
    implied_growth = solve_pie_growth(target_sv, inp)
    implied_period = solve_pie_forecast_period(target_sv, inp, max_years=25)

    p1, p2, p3 = st.columns(3)
    p1.metric("Market Cap (target SV)", f"${target_sv:,.0f}M")
    p2.metric("PIE Sales Growth", f"{implied_growth*100:.2f}%",
              f"vs your assumption {sales_growth*100:.1f}%")
    p3.metric("Implied Forecast Period", f"{implied_period} yrs")

    if sales_growth > implied_growth * 1.1:
        st.success("Your growth assumption is **above PIE** — you see upside the market doesn't.")
    elif sales_growth < implied_growth * 0.9:
        st.warning("Your growth assumption is **below PIE** — you're more bearish than the market.")
    else:
        st.info("Your assumption is roughly **in line with PIE**.")

    st.divider()

    # ── Quick buy/sell/hold ───────────────────────────────────────────────────
    st.subheader("🎯 Quick Decision")
    st.caption("Simple 3-scenario expected value. Tune in the Buy/Sell/Hold page for full analysis.")

    bear_sv  = run_dcf(DCFInputs(**{**inp.__dict__, 'sales_growth': max(0, sales_growth - 0.04)})).shareholder_value
    bull_sv  = run_dcf(DCFInputs(**{**inp.__dict__, 'sales_growth': sales_growth + 0.04})).shareholder_value
    base_sv  = res.shareholder_value

    bear_ps = bear_sv / data.shares_outstanding_m if data.shares_outstanding_m else 0
    base_ps = base_sv / data.shares_outstanding_m if data.shares_outstanding_m else 0
    bull_ps = bull_sv / data.shares_outstanding_m if data.shares_outstanding_m else 0

    scenarios = [
        Scenario("Bear (-4% growth)", bear_ps, 0.25),
        Scenario("Base",              base_ps, 0.50),
        Scenario("Bull (+4% growth)", bull_ps, 0.25),
    ]
    ev = expected_value(scenarios)
    upside = (ev - data.current_price) / data.current_price * 100

    q1, q2, q3 = st.columns(3)
    q1.metric("Bear Value / Share", f"${bear_ps:,.2f}")
    q2.metric("Base Value / Share", f"${base_ps:,.2f}")
    q3.metric("Bull Value / Share", f"${bull_ps:,.2f}")

    ev_col, dec_col = st.columns(2)
    ev_col.metric("Expected Value (EV)", f"${ev:,.2f}", f"{upside:+.1f}% vs ${data.current_price:.2f}")

    if upside > 10:
        dec_col.success("🟢 Potential BUY — EV > price by >10%")
    elif upside < -10:
        dec_col.error("🔴 Potential SELL — Price > EV by >10%")
    else:
        dec_col.warning("🟡 HOLD — within ±10% of EV")

    st.divider()

    # ── WACC breakdown ────────────────────────────────────────────────────────
    with st.expander("📐 WACC Breakdown"):
        ke = capm(data.rf_rate, data.beta, data.equity_market_premium)
        st.markdown(f"""
| Component | Value |
|---|---|
| Risk-free rate (10yr Treasury) | {data.rf_rate*100:.2f}% |
| Beta | {data.beta:.2f} |
| Equity market premium | {data.equity_market_premium*100:.1f}% |
| Cost of equity (CAPM) | {ke*100:.2f}% |
| Pre-tax cost of debt | {data.pretax_cost_of_debt*100:.2f}% |
| After-tax cost of debt | {data.pretax_cost_of_debt*(1-cash_tax)*100:.2f}% |
| Equity weight | {data.equity_weight*100:.1f}% |
| Debt weight | {data.debt_weight*100:.1f}% |
| **WACC** | **{wacc*100:.2f}%** |
""")

    # ── Raw data ──────────────────────────────────────────────────────────────
    with st.expander("🗂️ Raw financial data (last 3 years)"):
        import yfinance as yf
        tabs = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow"])
        ticker_obj = yf.Ticker(data.ticker)
        for tab, stmt in zip(tabs, [ticker_obj.income_stmt,
                                     ticker_obj.balance_sheet,
                                     ticker_obj.cashflow]):
            with tab:
                if stmt is not None and not stmt.empty:
                    st.dataframe(stmt.iloc[:, :4].applymap(
                        lambda x: f"${x/1e6:,.1f}M" if isinstance(x, (int, float)) and not pd.isna(x) else x
                    ), use_container_width=True)
                else:
                    st.info("No data available.")

    st.divider()
    st.info(
        "Use the **sidebar pages** to run the full analysis — "
        "all inputs have been pre-populated with this company's data."
    )

else:
    st.markdown("""
    ### How it works
    1. Enter a ticker above and click **Load Data**
    2. The app fetches 3 years of financials from Yahoo Finance
    3. All value drivers are computed and pre-filled:
       - Sales growth (3-year CAGR)
       - Operating profit margin (3-year average)
       - Cash tax rate (3-year average)
       - IFCR & IWCR (from capex, depreciation, working capital)
       - WACC (CAPM cost of equity + market-weight cost of debt)
       - Excess cash & debt (from balance sheet)
    4. Run DCF, PIE, Turbo Trigger and Buy/Sell/Hold — all with real numbers

    ---
    **Example tickers to try:** `AAPL` `MSFT` `DPZ` `AMZN` `NVDA` `JPM` `TSLA`
    """)
