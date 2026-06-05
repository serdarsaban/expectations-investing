import streamlit as st

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
