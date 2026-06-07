import streamlit as st
import datetime
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from utils.calculations import (
    DCFInputs, run_dcf, solve_pie_growth, solve_pie_forecast_period,
    Scenario, expected_value, buyback_rate_of_return, eps_accretion_test,
    wealth_transfer, capm, annual_excess_return, tax_hurdle,
)

st.set_page_config(
    page_title="Expectations Investing",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── shared CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* sidebar nav links */
[data-testid="stSidebarNav"] a { font-size: 0.92rem; }

/* metric delta colour overrides */
.positive { color: #16a34a; font-weight: 600; }
.negative { color: #dc2626; font-weight: 600; }

/* formula boxes */
.formula-box {
    background: #f8fafc;
    border-left: 3px solid #2563eb;
    border-radius: 4px;
    padding: 0.6rem 1rem;
    font-family: monospace;
    font-size: 0.85rem;
    margin-bottom: 0.5rem;
}

/* chapter badge */
.chapter-badge {
    display: inline-block;
    background: #dbeafe;
    color: #1e40af;
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    margin-bottom: 0.4rem;
}
</style>
""", unsafe_allow_html=True)

# ── home page ────────────────────────────────────────────────────────────────
st.title("📈 Expectations Investing")
st.caption("Based on *Expectations Investing* by Michael Mauboussin & Alfred Rappaport")

st.markdown("""
Expectations Investing is a three-step framework for finding stocks where the **market's 
price-implied expectations (PIE)** are likely to be revised.

---

### Three-step process
""")

col1, col2, col3 = st.columns(3)
with col1:
    st.info("**Step 1 — Estimate PIE**\n\nReverse-engineer the current stock price to reveal what financial performance the market is already pricing in.")
with col2:
    st.info("**Step 2 — Identify Opportunities**\n\nUse the Expectations Infrastructure and competitive strategy analysis to find where revisions are likely.")
with col3:
    st.info("**Step 3 — Buy, Sell, or Hold**\n\nCalculate Expected Value across scenarios and compare to current price to make confident decisions.")

st.markdown("---")
st.markdown("""
### Navigate the modules

| Page | Chapter | What it does |
|---|---|---|
| 🏗️ DCF Engine | Ch 2 | Build the shareholder value road map from scratch |
| 🔎 PIE Estimator | Ch 5 | Reverse-engineer the stock price to find implied growth |
| ⚡ Turbo Trigger | Ch 3 & 6 | Sensitivity analysis to find the high-leverage value driver |
| 🎯 Buy / Sell / Hold | Ch 7 | Expected Value calculator with scenario probabilities |
| 🔁 Share Buybacks | Ch 11 | Golden Rule buyback analyser |

Use the **sidebar** to navigate.
""")

st.markdown("---")
st.caption("All formulas sourced directly from the book's chapter content and formula appendix.")

# ── Full Report Download ─────────────────────────────────────────────────────

def build_full_report():
    data      = st.session_state.get("company_data")
    generated = datetime.datetime.now().strftime("%d %b %Y %H:%M")
    company   = data.name if data else "No Ticker Loaded"
    ticker    = f" ({data.ticker})" if data else ""

    # ── helpers ───────────────────────────────────────────────────────────────
    def sec(title, badge=None):
        badge_html = f'<span class="badge">{badge}</span>' if badge else ""
        return f'<div class="section-title">{badge_html}{title}</div>'

    def card(label, value, sub=""):
        sub_html = f'<div class="card-sub">{sub}</div>' if sub else ""
        return f'<div class="card"><div class="card-label">{label}</div><div class="card-value">{value}</div>{sub_html}</div>'

    def table_from_rows(headers, rows):
        ths = "".join(f"<th>{h}</th>" for h in headers)
        trs = "".join(
            "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
            for row in rows
        )
        return f"<table><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>"

    # ── SECTION 1 — Company Overview ─────────────────────────────────────────
    if data:
        overview_cards = "".join([
            card("Price",      f"${data.current_price:,.2f}"),
            card("Market Cap", f"${data.market_cap_m:,.0f}M"),
            card("Shares",     f"{data.shares_outstanding_m:,.1f}M"),
            card("Beta",       f"{data.beta:.2f}"),
            card("Sector",     data.sector),
            card("Industry",   data.industry),
        ])
        driver_rows = [
            ["Sales — most recent",          f"${data.base_sales_m:,.1f}M"],
            ["Sales Growth — 3yr CAGR",      f"{data.sales_growth_3yr*100:.1f}%"],
            ["Op. Profit Margin — 3yr avg",  f"{data.op_margin_3yr*100:.1f}%"],
            ["Cash Tax Rate — 3yr avg",      f"{data.cash_tax_rate_3yr*100:.1f}%"],
            ["IFCR",                         f"{data.ifcr_3yr*100:.1f}%"],
            ["IWCR",                         f"{data.iwcr_3yr*100:.1f}%"],
            ["Excess Cash ($M)",             f"${data.excess_cash_m:,.1f}M"],
            ["Debt ($M)",                    f"${data.total_debt_m:,.1f}M"],
            ["WACC",                         f"{data.wacc*100:.2f}%"],
        ]
        ke = capm(data.rf_rate, data.beta, data.equity_market_premium)
        wacc_rows = [
            ["Risk-free rate",         f"{data.rf_rate*100:.2f}%"],
            ["Beta",                   f"{data.beta:.2f}"],
            ["Equity market premium",  f"{data.equity_market_premium*100:.1f}%"],
            ["Cost of equity (CAPM)",  f"{ke*100:.2f}%"],
            ["Pre-tax cost of debt",   f"{data.pretax_cost_of_debt*100:.2f}%"],
            ["After-tax cost of debt", f"{data.pretax_cost_of_debt*(1-data.cash_tax_rate_3yr)*100:.2f}%"],
            ["Equity weight",          f"{data.equity_weight*100:.1f}%"],
            ["Debt weight",            f"{data.debt_weight*100:.1f}%"],
            ["WACC",                   f"{data.wacc*100:.2f}%"],
        ]
        section_overview = f"""
        {sec("Company Overview", "TICKER LOOKUP")}
        <h3>{data.name} &nbsp;<span style="color:#64748b;font-weight:400">{data.ticker} · {data.sector} · {data.currency}</span></h3>
        <div class="cards">{overview_cards}</div>
        <h4>Value Drivers — 3-Year Historical Averages</h4>
        {table_from_rows(["Driver", "Value"], driver_rows)}
        <h4>WACC Breakdown</h4>
        {table_from_rows(["Component", "Value"], wacc_rows)}
        """
    else:
        section_overview = f"""
        {sec("Company Overview", "TICKER LOOKUP")}
        <p class="muted">No ticker loaded. Go to <strong>Ticker Lookup</strong>, enter a symbol and click <strong>Analyse</strong>, then return here to download.</p>
        """

    # ── SECTION 2 — DCF Engine ────────────────────────────────────────────────
    if data:
        dcf_inp = DCFInputs(
            base_sales=data.base_sales_m, sales_growth=data.sales_growth_3yr,
            op_margin=data.op_margin_3yr, cash_tax_rate=data.cash_tax_rate_3yr,
            ifcr=data.ifcr_3yr, iwcr=data.iwcr_3yr, wacc=data.wacc,
            forecast_years=8, inflation=0.02, pricing_power=1.0,
            excess_cash=data.excess_cash_m, debt=data.total_debt_m,
        )
        dcf = run_dcf(dcf_inp)
        sv_ps   = dcf.shareholder_value / data.shares_outstanding_m if data.shares_outstanding_m else 0
        premium = (sv_ps - data.current_price) / data.current_price * 100 if data.current_price else 0
        y1      = dcf.rows[0]

        strip = "".join([
            f'<div class="formula-cell"><div class="f-label">Sales Y1</div><div class="f-val">${y1.sales:,.1f}M</div></div>',
            f'<div class="formula-cell"><div class="f-label">× OPM</div><div class="f-val">{data.op_margin_3yr*100:.1f}%</div></div>',
            f'<div class="formula-cell"><div class="f-label">= Op. Profit</div><div class="f-val">${y1.op_profit:,.1f}M</div></div>',
            f'<div class="formula-cell"><div class="f-label">− Tax</div><div class="f-val">${y1.op_profit*data.cash_tax_rate_3yr:,.1f}M</div></div>',
            f'<div class="formula-cell"><div class="f-label">= NOPAT</div><div class="f-val">${y1.nopat:,.1f}M</div></div>',
            f'<div class="formula-cell"><div class="f-label">− Investment</div><div class="f-val">${y1.investment:,.1f}M</div></div>',
            f'<div class="formula-cell"><div class="f-label">= FCF</div><div class="f-val">${y1.fcf:,.1f}M</div></div>',
        ])

        dcf_metrics = "".join([
            card("Shareholder Value", f"${dcf.shareholder_value:,.1f}M"),
            card("Value Per Share",   f"${sv_ps:,.2f}", f"{premium:+.1f}% vs ${data.current_price:.2f}"),
            card("PV of FCFs",        f"${dcf.pv_fcfs:,.1f}M"),
            card("PV of Cont. Value", f"${dcf.pv_continuing_value:,.1f}M"),
            card("Operating Value",   f"${dcf.operating_value:,.1f}M"),
        ])

        dcf_table_rows = [
            [r.year, f"${r.sales:,.1f}M", f"${r.op_profit:,.1f}M",
             f"${r.nopat:,.1f}M", f"${r.investment:,.1f}M",
             f"${r.fcf:,.1f}M",   f"${r.pv_fcf:,.1f}M"]
            for r in dcf.rows
        ]

        pv_fcfs_pct = dcf.pv_fcfs / dcf.operating_value * 100 if dcf.operating_value else 0
        pv_cv_pct   = dcf.pv_continuing_value / dcf.operating_value * 100 if dcf.operating_value else 0

        section_dcf = f"""
        {sec("DCF Engine — Shareholder Value Road Map", "CHAPTER 2")}
        <h4>Year 1 Value Driver Summary</h4>
        <div class="formula-strip">{strip}</div>
        <h4>Key Valuation Metrics</h4>
        <div class="cards">{dcf_metrics}</div>
        <h4>Year-by-Year Free Cash Flow Forecast</h4>
        {table_from_rows(
            ["Year","Sales ($M)","Op. Profit ($M)","NOPAT ($M)","Investment ($M)","FCF ($M)","PV of FCF ($M)"],
            dcf_table_rows
        )}
        <h4>Value Composition</h4>
        <div class="breakdown">
          <div class="brow"><span class="blabel">PV of Free Cash Flows</span>
            <span class="bval">${dcf.pv_fcfs:,.1f}M <span class="bpct">({pv_fcfs_pct:.0f}%)</span></span></div>
          <div class="brow"><span class="blabel">PV of Continuing Value</span>
            <span class="bval">${dcf.pv_continuing_value:,.1f}M <span class="bpct">({pv_cv_pct:.0f}%)</span></span></div>
          <div class="brow"><span class="blabel">Operating Value</span>
            <span class="bval">${dcf.operating_value:,.1f}M</span></div>
          <div class="brow"><span class="blabel">+ Excess Cash &amp; Non-Op Assets</span>
            <span class="bval">+${data.excess_cash_m:,.1f}M</span></div>
          <div class="brow"><span class="blabel">− Debt</span>
            <span class="bval neg">−${data.total_debt_m:,.1f}M</span></div>
          <div class="brow total"><span class="blabel">= Shareholder Value</span>
            <span class="bval pos">${dcf.shareholder_value:,.1f}M</span></div>
        </div>
        <h4>Formulas Used</h4>
        <div class="fbox">Sales × OPM = Operating Profit</div>
        <div class="fbox">Operating Profit × (1 – Tax) = NOPAT</div>
        <div class="fbox">Investment = (IFCR + IWCR) × ΔSales</div>
        <div class="fbox">FCF = NOPAT – Investment</div>
        <div class="fbox">CV = NOPAT_N × (1 + i·p) / (WACC – i·p)</div>
        <div class="fbox">Shareholder Value = PV(FCFs) + PV(CV) + Non-Op Assets – Debt</div>
        """
    else:
        section_dcf = f"{sec('DCF Engine — Shareholder Value Road Map', 'CHAPTER 2')}<p class='muted'>Load a ticker to populate this section.</p>"

    # ── SECTION 3 — PIE Estimator ─────────────────────────────────────────────
    if data:
        pie_inp = DCFInputs(
            base_sales=data.base_sales_m, sales_growth=0.07,
            op_margin=data.op_margin_3yr, cash_tax_rate=data.cash_tax_rate_3yr,
            ifcr=data.ifcr_3yr, iwcr=data.iwcr_3yr, wacc=data.wacc,
            forecast_years=15, inflation=0.02, pricing_power=1.0,
            excess_cash=data.excess_cash_m, debt=data.total_debt_m,
        )
        implied_g  = solve_pie_growth(data.market_cap_m, pie_inp)
        implied_fp = solve_pie_forecast_period(data.market_cap_m, pie_inp, 25)

        if data.sales_growth_3yr > implied_g * 1.1:
            pie_signal = '<div class="signal green">Historical growth is ABOVE PIE — the market may be under-pricing this company\'s growth.</div>'
        elif data.sales_growth_3yr < implied_g * 0.9:
            pie_signal = '<div class="signal amber">Historical growth is BELOW PIE — the market expects an acceleration not seen historically.</div>'
        else:
            pie_signal = '<div class="signal blue">Historical growth is broadly IN LINE with PIE.</div>'

        pie_metrics = "".join([
            card("Market Cap (PIE target)",       f"${data.market_cap_m:,.0f}M"),
            card("PIE — Implied Sales Growth",    f"{implied_g*100:.2f}%",
                 f"hist. avg: {data.sales_growth_3yr*100:.1f}%"),
            card("Market-Implied Forecast Period", f"{implied_fp} years"),
        ])

        yby_rows = []
        for yrs in range(1, 16):
            i2  = DCFInputs(**{**pie_inp.__dict__, 'sales_growth': implied_g, 'forecast_years': yrs})
            sv2 = run_dcf(i2).shareholder_value
            yby_rows.append([yrs, f"${sv2:,.1f}M", f"{(sv2/data.market_cap_m-1)*100:+.1f}%"])

        section_pie = f"""
        {sec("PIE Estimator — Price-Implied Expectations", "CHAPTER 5")}
        <div class="cards">{pie_metrics}</div>
        {pie_signal}
        <h4>Year-by-Year Value Build at PIE Growth ({implied_g*100:.2f}%)</h4>
        {table_from_rows(["Forecast Years", "Shareholder Value ($M)", "vs Target"], yby_rows)}
        """
    else:
        section_pie = f"{sec('PIE Estimator — Price-Implied Expectations', 'CHAPTER 5')}<p class='muted'>Load a ticker to populate this section.</p>"

    # ── SECTION 4 — Turbo Trigger ─────────────────────────────────────────────
    if data:
        tt_inp = DCFInputs(
            base_sales=data.base_sales_m, sales_growth=data.sales_growth_3yr,
            op_margin=data.op_margin_3yr, cash_tax_rate=data.cash_tax_rate_3yr,
            ifcr=data.ifcr_3yr, iwcr=data.iwcr_3yr, wacc=data.wacc,
            forecast_years=8, inflation=0.02, pricing_power=1.0,
            excess_cash=data.excess_cash_m, debt=data.total_debt_m,
        )
        base_sv  = run_dcf(tt_inp).shareholder_value
        sg       = data.sales_growth_3yr
        opm      = data.op_margin_3yr
        inv_base = data.ifcr_3yr + data.iwcr_3yr

        def tt_sv(g=None, margin=None, inv=None):
            kw = tt_inp.__dict__.copy()
            if g      is not None: kw["sales_growth"] = g
            if margin is not None: kw["op_margin"]    = margin
            if inv    is not None: kw["ifcr"] = kw["iwcr"] = inv / 2
            return run_dcf(DCFInputs(**kw)).shareholder_value

        sv_sg_lo  = tt_sv(g=max(0.001, sg - 0.04));    sv_sg_hi  = tt_sv(g=sg + 0.04)
        sv_opm_lo = tt_sv(margin=max(0.01, opm - 0.04)); sv_opm_hi = tt_sv(margin=opm + 0.04)
        sv_inv_lo = tt_sv(inv=max(0, inv_base - 0.05)); sv_inv_hi = tt_sv(inv=inv_base + 0.05)

        rng_sg  = sv_sg_hi  - sv_sg_lo
        rng_opm = sv_opm_hi - sv_opm_lo
        rng_inv = sv_inv_hi - sv_inv_lo
        ranges  = {"Sales Growth": rng_sg, "Cost / Margin": rng_opm, "Investment Rate": rng_inv}
        turbo   = max(ranges, key=ranges.get)

        tt_table_rows = [
            ["Sales Growth",
             f"{max(0.001, sg-0.04)*100:.1f}%", f"{(sg+0.04)*100:.1f}%",
             f"${sv_sg_lo:,.1f}M", f"${sv_sg_hi:,.1f}M", f"${rng_sg:,.1f}M"],
            ["Op. Margin",
             f"{max(0.01, opm-0.04)*100:.1f}%", f"{(opm+0.04)*100:.1f}%",
             f"${sv_opm_lo:,.1f}M", f"${sv_opm_hi:,.1f}M", f"${rng_opm:,.1f}M"],
            ["Investment Rate",
             f"{max(0, inv_base-0.05)*100:.1f}%", f"{(inv_base+0.05)*100:.1f}%",
             f"${sv_inv_lo:,.1f}M", f"${sv_inv_hi:,.1f}M", f"${rng_inv:,.1f}M"],
        ]

        section_tt = f"""
        {sec("Turbo Trigger — Expectations Infrastructure", "CHAPTERS 3 & 6")}
        <div class="cards">
          {card("PIE Baseline Shareholder Value", f"${base_sv:,.1f}M")}
          {card("🎯 Turbo Trigger", turbo, f"${ranges[turbo]:,.0f}M value range")}
        </div>
        <h4>Sensitivity — ±4 pp Scenario Ranges</h4>
        {table_from_rows(
            ["Value Driver", "Low", "High", "SV at Low", "SV at High", "Range"],
            tt_table_rows
        )}
        """
    else:
        section_tt = f"{sec('Turbo Trigger — Expectations Infrastructure', 'CHAPTERS 3 & 6')}<p class='muted'>Load a ticker to populate this section.</p>"

    # ── SECTION 5 — Buy / Sell / Hold ─────────────────────────────────────────
    if data:
        sg = data.sales_growth_3yr

        def bsh_sv(g):
            kw = dict(
                base_sales=data.base_sales_m, sales_growth=g,
                op_margin=data.op_margin_3yr, cash_tax_rate=data.cash_tax_rate_3yr,
                ifcr=data.ifcr_3yr, iwcr=data.iwcr_3yr, wacc=data.wacc,
                forecast_years=8, inflation=0.02, pricing_power=1.0,
                excess_cash=data.excess_cash_m, debt=data.total_debt_m,
            )
            return run_dcf(DCFInputs(**kw)).shareholder_value / data.shares_outstanding_m

        sv_lo  = bsh_sv(max(0.001, sg - 0.04))
        sv_mid = bsh_sv(sg)
        sv_hi  = bsh_sv(sg + 0.04)

        scenarios = [
            Scenario("Bear (growth −4%)", sv_lo,  0.25),
            Scenario("Base",              sv_mid, 0.50),
            Scenario("Bull (growth +4%)", sv_hi,  0.25),
        ]
        ev     = expected_value(scenarios)
        upside = (ev - data.current_price) / data.current_price * 100 if data.current_price else 0
        ann_exc = annual_excess_return(data.current_price, ev, 2)

        if upside > 10:
            decision = '<div class="signal green">🟢 BUY — Expected Value exceeds current price by more than 10%</div>'
        elif upside < -10:
            decision = '<div class="signal red">🔴 SELL — Current price exceeds Expected Value by more than 10%</div>'
        else:
            decision = '<div class="signal amber">🟡 HOLD — within ±10% of Expected Value</div>'

        bsh_metrics = "".join([
            card("Expected Value",       f"${ev:,.2f}"),
            card("Current Price",        f"${data.current_price:,.2f}"),
            card("EV vs Price",          f"{upside:+.1f}%"),
            card("Annual Excess Return", f"{ann_exc*100:.1f}%", "over 2 years"),
        ])

        bsh_table_rows = [
            [s.label,
             f"{[max(0.001,sg-0.04), sg, sg+0.04][i]*100:.1f}%",
             f"${s.stock_value:,.2f}",
             f"{s.probability*100:.0f}%",
             f"${s.weighted:,.2f}"]
            for i, s in enumerate(scenarios)
        ] + [["Expected Value", "", "", "100%", f"${ev:,.2f}"]]

        section_bsh = f"""
        {sec("Buy / Sell / Hold — Expected Value Analysis", "CHAPTER 7")}
        <div class="cards">{bsh_metrics}</div>
        {decision}
        <h4>Scenario Table</h4>
        {table_from_rows(
            ["Scenario", "Sales Growth", "Value / Share ($)", "Probability", "Weighted Value ($)"],
            bsh_table_rows
        )}
        """
    else:
        section_bsh = f"{sec('Buy / Sell / Hold — Expected Value Analysis', 'CHAPTER 7')}<p class='muted'>Load a ticker to populate this section.</p>"

    # ── SECTION 6 — Share Buybacks ────────────────────────────────────────────
    if data:
        ke_bb    = capm(data.rf_rate, data.beta, data.equity_market_premium)
        after_kd = data.pretax_cost_of_debt * (1 - data.cash_tax_rate_3yr)
        fair_val = data.current_price * 1.1
        bb_ror   = buyback_rate_of_return(ke_bb, data.current_price, fair_val)
        accretion = eps_accretion_test(data.pe_ratio, after_kd)
        ratio     = data.current_price / fair_val
        bb_amount = data.shares_outstanding_m * data.current_price * 0.05

        bb_metrics = "".join([
            card("Price / Fair Value",     f"{ratio:.2f}×",
                 "Undervalued ✅" if ratio < 1 else "Overvalued ⚠️"),
            card("Buyback Rate of Return", f"{bb_ror*100:.2f}%",
                 f"cost of equity {ke_bb*100:.2f}%"),
            card("Excess Return",          f"{(bb_ror-ke_bb)*100:.2f}%"),
            card("EPS Accretive?",
                 "✅ Yes" if accretion["accretive"] else "⚠️ No",
                 f"spread {accretion['spread']*100:.2f}%"),
        ])

        golden_rule = (
            f'<div class="signal green">✅ Golden Rule: FAVOURABLE — buyback ROR {bb_ror*100:.2f}% > cost of equity {ke_bb*100:.2f}%</div>'
            if ratio < 1.0 else
            f'<div class="signal red">⚠️ Golden Rule: UNFAVOURABLE — stock is overvalued ({ratio:.2f}× fair value)</div>'
        )

        wt_rows_data = []
        for label, pm in [("Overvalued (2× FV)", 2.0), ("Undervalued (0.5× FV)", 0.5),
                           ("At Fair Value", 1.0), ("At Current Price", ratio)]:
            bp = fair_val * pm
            wt = wealth_transfer(fair_val, data.shares_outstanding_m, bb_amount, bp)
            wt_rows_data.append([
                label, f"${bp:,.2f}",
                f"${wt.get('new_value_per_share', 0):,.2f}",
                f"{wt.get('value_change_per_share', 0):+.2f}",
                wt.get("wealth_transfer", "—"),
            ])

        section_bb = f"""
        {sec("Share Buybacks — Golden Rule Analyser", "CHAPTER 11")}
        <p style="color:#475569;font-style:italic;margin-bottom:12px">
          Golden Rule: Repurchase only when price &lt; Expected Value and no better internal investments exist.
        </p>
        <div class="cards">{bb_metrics}</div>
        {golden_rule}
        <h4>Wealth Transfer Analysis</h4>
        {table_from_rows(
            ["Scenario", "Buyback Price", "New Value/Share", "Δ Value/Share", "Wealth Transfer"],
            wt_rows_data
        )}
        """
    else:
        section_bb = f"{sec('Share Buybacks — Golden Rule Analyser', 'CHAPTER 11')}<p class='muted'>Load a ticker to populate this section.</p>"

    # ── ASSEMBLE ──────────────────────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Expectations Investing Report — {company}{ticker}</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
      background:#f8fafc;color:#1e293b;font-size:14px;line-height:1.6}}
.page{{max-width:960px;margin:0 auto;padding:40px 32px}}

.header{{background:#1e293b;color:#fff;border-radius:12px;padding:28px 32px;margin-bottom:28px}}
.header h1{{font-size:22px;font-weight:700;margin-bottom:4px}}
.header .meta{{font-size:12px;color:#94a3b8}}
.toc{{margin-top:14px;display:flex;flex-wrap:wrap;gap:8px}}
.toc a{{color:#93c5fd;font-size:12px;text-decoration:none;background:rgba(255,255,255,.08);
         padding:4px 12px;border-radius:20px}}

.section{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:28px;margin-bottom:20px}}
.section-title{{display:flex;align-items:center;gap:10px;font-size:17px;font-weight:700;
                color:#1e293b;margin-bottom:18px;padding-bottom:10px;border-bottom:2px solid #e2e8f0}}
.badge{{background:#3b82f6;color:#fff;font-size:10px;font-weight:700;letter-spacing:.08em;
        padding:3px 10px;border-radius:20px;text-transform:uppercase;white-space:nowrap}}
h3{{font-size:15px;font-weight:700;margin:16px 0 10px}}
h4{{font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;
    letter-spacing:.08em;margin:20px 0 8px}}

.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:10px;margin-bottom:16px}}
.card{{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px;text-align:center}}
.card-label{{font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}}
.card-value{{font-size:17px;font-weight:700;color:#2563eb}}
.card-sub{{font-size:11px;color:#94a3b8;margin-top:2px}}

.formula-strip{{display:grid;grid-template-columns:repeat(7,1fr);gap:6px;margin-bottom:14px}}
.formula-cell{{background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;padding:8px 4px;text-align:center}}
.f-label{{font-size:9px;color:#3b82f6;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px}}
.f-val{{font-size:12px;font-weight:700;color:#1e293b}}

table{{width:100%;border-collapse:collapse;border-radius:8px;overflow:hidden;
       border:1px solid #e2e8f0;margin-bottom:16px}}
thead tr{{background:#1e293b;color:#fff}}
th{{padding:9px 12px;text-align:right;font-size:11px;font-weight:600}}
th:first-child{{text-align:left}}
td{{padding:8px 12px;text-align:right;font-size:12px;border-bottom:1px solid #f1f5f9}}
td:first-child{{text-align:left;font-weight:500}}
tbody tr:last-child td{{border-bottom:none}}
tbody tr:nth-child(even){{background:#f8fafc}}

.breakdown{{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin-bottom:16px}}
.brow{{display:flex;justify-content:space-between;align-items:center;
       padding:7px 0;border-bottom:1px solid #f1f5f9}}
.brow:last-child{{border-bottom:none;padding-top:10px}}
.blabel{{color:#475569;font-size:13px}}
.bval{{font-weight:600;color:#2563eb;font-size:13px}}
.bval.pos{{color:#16a34a;font-size:15px;font-weight:700}}
.bval.neg{{color:#dc2626}}
.bpct{{font-size:11px;color:#94a3b8;margin-left:4px}}
.total .blabel{{font-weight:700;color:#1e293b}}

.signal{{border-radius:8px;padding:10px 16px;font-size:13px;font-weight:500;margin-bottom:14px}}
.signal.green{{background:#f0fdf4;color:#166534;border:1px solid #bbf7d0}}
.signal.amber{{background:#fffbeb;color:#92400e;border:1px solid #fde68a}}
.signal.red{{background:#fef2f2;color:#991b1b;border:1px solid #fecaca}}
.signal.blue{{background:#eff6ff;color:#1e40af;border:1px solid #bfdbfe}}

.fbox{{background:#f0fdf4;border-left:4px solid #16a34a;border-radius:6px;
       padding:8px 14px;margin-bottom:6px;font-family:"Courier New",monospace;
       font-size:12px;color:#166534}}
.muted{{color:#94a3b8;font-style:italic}}
.footer{{margin-top:36px;text-align:center;font-size:11px;color:#94a3b8;padding-bottom:20px}}

@media print{{
  body{{background:#fff}}
  .page{{padding:20px}}
  .section{{break-inside:avoid}}
}}
</style>
</head>
<body>
<div class="page">
  <div class="header">
    <h1>📈 Expectations Investing — Full Analysis Report</h1>
    <div class="meta">{company}{ticker} &nbsp;·&nbsp; Generated {generated} &nbsp;·&nbsp; Mauboussin &amp; Rappaport Framework</div>
    <div class="toc">
      <a href="#s1">Company Overview</a>
      <a href="#s2">DCF Engine</a>
      <a href="#s3">PIE Estimator</a>
      <a href="#s4">Turbo Trigger</a>
      <a href="#s5">Buy / Sell / Hold</a>
      <a href="#s6">Share Buybacks</a>
    </div>
  </div>
  <div class="section" id="s1">{section_overview}</div>
  <div class="section" id="s2">{section_dcf}</div>
  <div class="section" id="s3">{section_pie}</div>
  <div class="section" id="s4">{section_tt}</div>
  <div class="section" id="s5">{section_bsh}</div>
  <div class="section" id="s6">{section_bb}</div>
  <div class="footer">Expectations Investing · Full Analysis Report · {generated}</div>
</div>
</body>
</html>"""


# ── Render the download button ────────────────────────────────────────────────
st.markdown("---")

data = st.session_state.get("company_data")
if data:
    st.success(f"**{data.name} ({data.ticker})** is loaded — click below to download the full report.")
else:
    st.info("💡 Go to **Ticker Lookup**, enter a symbol and click **Analyse**, then return here to download the full report.")

filename = (
    f"EI_Report_{data.ticker}_{datetime.datetime.now().strftime('%Y%m%d')}.html"
    if data else
    f"EI_Report_{datetime.datetime.now().strftime('%Y%m%d')}.html"
)

st.download_button(
    label="⬇️ Download Full Expectations Investing Report (HTML)",
    data=build_full_report(),
    file_name=filename,
    mime="text/html",
    use_container_width=True,
    type="primary",
)
