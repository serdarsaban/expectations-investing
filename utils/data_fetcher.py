"""
Data fetcher for Expectations Investing app.
Primary: Alpha Vantage (free API key, no IP blocking, works on Streamlit Cloud).
Fallback: yfinance (local use only).

Get a free Alpha Vantage key at: https://www.alphavantage.co/support/#api-key
Free tier: 25 calls/day, 5/min. One ticker uses ~5 calls.
"""
import requests
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
import time


# ── Output structure ──────────────────────────────────────────────────────────

@dataclass
class CompanyData:
    ticker: str
    name: str
    sector: str
    industry: str
    current_price: float
    market_cap_m: float
    shares_outstanding_m: float
    beta: float
    pe_ratio: float
    base_sales_m: float
    sales_growth_3yr: float
    op_margin_3yr: float
    cash_tax_rate_3yr: float
    ifcr_3yr: float
    iwcr_3yr: float
    excess_cash_m: float
    total_debt_m: float
    underfunded_pension_m: float
    rf_rate: float
    equity_market_premium: float
    equity_weight: float
    debt_weight: float
    pretax_cost_of_debt: float
    wacc: float
    currency: str = "USD"
    warnings: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe(val, default=0.0):
    if val is None or val == "None" or val == "-":
        return default
    try:
        v = float(str(val).replace(",", ""))
        return default if np.isnan(v) else v
    except Exception:
        return default


def _avg(lst):
    clean = [x for x in lst if x is not None and not np.isnan(x)]
    return float(np.mean(clean)) if clean else 0.0


def _cagr(start, end, years):
    if start <= 0 or end <= 0 or years <= 0:
        return 0.0
    return (end / start) ** (1 / years) - 1


def _fetch_rf_rate():
    try:
        r = requests.get(
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10",
            timeout=8
        )
        for line in reversed(r.text.strip().split("\n")):
            parts = line.split(",")
            if len(parts) == 2 and parts[1].strip() not in (".", ""):
                return float(parts[1].strip()) / 100
    except Exception:
        pass
    return 0.045


AV_BASE = "https://www.alphavantage.co/query"


def _av(function: str, symbol: str, api_key: str, extra: dict = None) -> dict:
    """Single Alpha Vantage request with rate-limit retry."""
    params = {"function": function, "symbol": symbol, "apikey": api_key}
    if extra:
        params.update(extra)
    for attempt in range(3):
        r = requests.get(AV_BASE, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        # AV rate-limit message
        if "Note" in data or "Information" in data:
            if attempt < 2:
                time.sleep(15)
                continue
            raise ValueError(
                "Alpha Vantage rate limit reached (5 calls/min on free tier). "
                "Wait 60 seconds and try again."
            )
        return data
    return {}


# ── Alpha Vantage fetcher ─────────────────────────────────────────────────────

def _fetch_av(ticker: str, api_key: str) -> CompanyData:
    warnings = []
    t = ticker.upper()

    # 1. Company overview (price, market cap, beta, sector, etc.)
    overview = _av("OVERVIEW", t, api_key)
    if not overview or "Symbol" not in overview:
        raise ValueError(
            f"No data found for '{t}'. "
            "Check the ticker symbol — Alpha Vantage uses US exchange symbols (e.g. DPZ, AAPL)."
        )

    # 2. Current price
    quote = _av("GLOBAL_QUOTE", t, api_key)
    current_price = _safe(quote.get("Global Quote", {}).get("05. price"), 0)

    # 3. Income statement
    time.sleep(12)   # stay under 5 calls/min on free tier
    inc_raw = _av("INCOME_STATEMENT", t, api_key)
    inc_years = inc_raw.get("annualReports", [])[:4]   # most recent first

    # 4. Balance sheet
    time.sleep(12)
    bal_raw = _av("BALANCE_SHEET", t, api_key)
    bal_years = bal_raw.get("annualReports", [])[:4]

    # 5. Cash flow
    time.sleep(12)
    cf_raw = _av("CASH_FLOW", t, api_key)
    cf_years = cf_raw.get("annualReports", [])[:4]

    # ── Parse overview ────────────────────────────────────────────────────────
    name          = overview.get("Name", t)
    sector        = overview.get("Sector", "Unknown")
    industry      = overview.get("Industry", "Unknown")
    currency      = overview.get("Currency", "USD")
    market_cap_m  = _safe(overview.get("MarketCapitalization"), 0) / 1e6
    shares_m      = _safe(overview.get("SharesOutstanding"), 0) / 1e6
    beta          = _safe(overview.get("Beta"), 1.0)
    pe_ratio      = _safe(overview.get("TrailingPE") or overview.get("ForwardPE"), 20.0)

    # ── Income statement ──────────────────────────────────────────────────────
    revenues   = [_safe(y.get("totalRevenue"), 0)          for y in inc_years]
    op_incomes = [_safe(y.get("operatingIncome"), 0)       for y in inc_years]
    tax_exps   = [_safe(y.get("incomeTaxExpense"), 0)      for y in inc_years]
    int_exps   = [_safe(y.get("interestExpense"), 0)       for y in inc_years]

    # ── Balance sheet ─────────────────────────────────────────────────────────
    ca_list    = [_safe(y.get("totalCurrentAssets"), 0)    for y in bal_years]
    cl_list    = [_safe(y.get("totalCurrentLiabilities"), 0) for y in bal_years]
    cash_list  = [_safe(y.get("cashAndCashEquivalentsAtCarryingValue"), 0) for y in bal_years]
    std_list   = [_safe(y.get("currentDebt") or y.get("shortTermDebt"), 0) for y in bal_years]
    ltd_list   = [_safe(y.get("longTermDebt"), 0)          for y in bal_years]

    total_debt_m = ((ltd_list[0] if ltd_list else 0) + (std_list[0] if std_list else 0)) / 1e6

    # ── Cash flow ─────────────────────────────────────────────────────────────
    capex_list = [abs(_safe(y.get("capitalExpenditures"), 0))       for y in cf_years]
    depr_list  = [_safe(y.get("depreciationDepletionAndAmortization") or
                         y.get("depreciation"), 0)                   for y in cf_years]

    # ── Value drivers ─────────────────────────────────────────────────────────

    base_sales_m = revenues[0] / 1e6 if revenues else 0
    if len(revenues) >= 2:
        sales_growth_3yr = _cagr(revenues[-1], revenues[0], len(revenues) - 1)
    else:
        sales_growth_3yr = _safe(overview.get("QuarterlyRevenueGrowthYOY"), 0.05)
        warnings.append("Limited revenue history.")

    margins = [o / r for o, r in zip(op_incomes, revenues) if r > 0]
    op_margin_3yr = _avg(margins[:3]) if margins else 0.15

    tax_rates = [abs(tx) / oi for tx, oi in zip(tax_exps, op_incomes) if oi > 0]
    cash_tax_rate_3yr = min(max(_avg(tax_rates[:3]) if tax_rates else 0.21, 0.05), 0.50)

    ifcr_list = []
    for i in range(min(len(capex_list), len(depr_list), len(revenues) - 1)):
        ds = revenues[i] - revenues[i + 1]
        if ds > 0:
            ifcr_list.append((capex_list[i] - depr_list[i]) / ds)
    ifcr_3yr = max(0.0, _avg(ifcr_list) if ifcr_list else 0.10)

    iwcr_list = []
    for i in range(min(len(ca_list), len(cl_list), len(cash_list), len(revenues) - 1)):
        st_i  = std_list[i]     if i     < len(std_list) else 0
        st_i1 = std_list[i + 1] if i + 1 < len(std_list) else 0
        owc_c = ca_list[i]     - cash_list[i]     - (cl_list[i]     - st_i)
        owc_p = ca_list[i + 1] - cash_list[i + 1] - (cl_list[i + 1] - st_i1)
        ds    = revenues[i] - revenues[i + 1]
        if ds > 0:
            iwcr_list.append((owc_c - owc_p) / ds)
    iwcr_3yr = min(max(_avg(iwcr_list) if iwcr_list else 0.05, 0.0), 0.50)

    total_cash_m  = cash_list[0] / 1e6 if cash_list else 0
    excess_cash_m = max(0.0, total_cash_m - base_sales_m * 0.01)

    # ── WACC ─────────────────────────────────────────────────────────────────
    rf_rate   = _fetch_rf_rate()
    emp       = 0.055
    ke        = rf_rate + beta * emp
    pretax_kd = (abs(int_exps[0]) / (total_debt_m * 1e6)
                 if int_exps and total_debt_m > 0
                 else rf_rate + 0.015)
    pretax_kd = min(max(pretax_kd, 0.01), 0.15)
    total_cap = market_cap_m + total_debt_m
    we = market_cap_m / total_cap if total_cap > 0 else 0.8
    wd = total_debt_m / total_cap if total_cap > 0 else 0.2
    wacc = we * ke + wd * pretax_kd * (1 - cash_tax_rate_3yr)

    return CompanyData(
        ticker=t, name=name, sector=sector, industry=industry,
        current_price=current_price, market_cap_m=market_cap_m,
        shares_outstanding_m=shares_m, beta=beta, pe_ratio=pe_ratio,
        base_sales_m=base_sales_m, sales_growth_3yr=sales_growth_3yr,
        op_margin_3yr=op_margin_3yr, cash_tax_rate_3yr=cash_tax_rate_3yr,
        ifcr_3yr=ifcr_3yr, iwcr_3yr=iwcr_3yr,
        excess_cash_m=excess_cash_m, total_debt_m=total_debt_m,
        underfunded_pension_m=0.0, rf_rate=rf_rate,
        equity_market_premium=emp, equity_weight=we, debt_weight=wd,
        pretax_cost_of_debt=pretax_kd, wacc=wacc,
        currency=currency, warnings=warnings, raw=overview,
    )


# ── yfinance fallback (local only) ────────────────────────────────────────────

def _fetch_yfinance(ticker: str) -> CompanyData:
    import yfinance as yf
    warnings = ["Using yfinance — may be rate-limited on Streamlit Cloud."]
    t = yf.Ticker(ticker)
    info = t.info
    if not info or (info.get("regularMarketPrice") is None and info.get("currentPrice") is None):
        raise ValueError(f"No data found for '{ticker}'.")

    def col_vals(df, *keys):
        for k in keys:
            if k in df.index:
                return [float(v) for v in df.loc[k].values
                        if v is not None and not (isinstance(v, float) and np.isnan(v))]
        return []

    inc = t.income_stmt
    bal = t.balance_sheet
    cf  = t.cashflow

    rev  = col_vals(inc, "Total Revenue", "Revenue")
    opi  = col_vals(inc, "Operating Income", "EBIT")
    tax  = col_vals(inc, "Tax Provision", "Income Tax Expense")
    cap  = col_vals(cf,  "Capital Expenditure", "Purchase Of Property Plant And Equipment")
    dep  = col_vals(cf,  "Depreciation And Amortization", "Depreciation Amortization Depletion")
    ca   = col_vals(bal, "Current Assets", "Total Current Assets")
    cl   = col_vals(bal, "Current Liabilities", "Total Current Liabilities")
    csh  = col_vals(bal, "Cash And Cash Equivalents", "Cash")
    std  = col_vals(bal, "Current Debt", "Short Term Debt")

    base_sales_m     = rev[0] / 1e6 if rev else _safe(info.get("totalRevenue"), 1e9) / 1e6
    sales_growth_3yr = _cagr(rev[-1], rev[0], len(rev) - 1) if len(rev) >= 2 else _safe(info.get("revenueGrowth"), 0.05)
    margins          = [o / r for o, r in zip(opi, rev) if r > 0]
    op_margin_3yr    = _avg(margins[:3]) if margins else _safe(info.get("operatingMargins"), 0.15)
    tax_rates        = [abs(tx) / oi for tx, oi in zip(tax, opi) if oi > 0]
    cash_tax_rate_3yr = min(max(_avg(tax_rates[:3]) if tax_rates else 0.21, 0.05), 0.50)

    ifcr_list = []
    for i in range(min(len(cap), len(dep), len(rev) - 1)):
        ds = rev[i] - rev[i + 1]
        if ds > 0:
            ifcr_list.append((abs(cap[i]) - abs(dep[i])) / ds)
    ifcr_3yr = max(0.0, _avg(ifcr_list) if ifcr_list else 0.10)

    iwcr_list = []
    for i in range(min(len(ca), len(cl), len(csh), len(rev) - 1)):
        st_i = std[i] if i < len(std) else 0
        st_i1 = std[i+1] if i+1 < len(std) else 0
        owc_c = ca[i]   - csh[i]   - (cl[i]   - st_i)
        owc_p = ca[i+1] - csh[i+1] - (cl[i+1] - st_i1)
        ds = rev[i] - rev[i+1]
        if ds > 0:
            iwcr_list.append((owc_c - owc_p) / ds)
    iwcr_3yr = min(max(_avg(iwcr_list) if iwcr_list else 0.05, 0.0), 0.50)

    market_cap_m  = _safe(info.get("marketCap"), 0) / 1e6
    total_debt_m  = _safe(info.get("totalDebt"), 0) / 1e6
    total_cash_m  = _safe(info.get("totalCash"), 0) / 1e6
    shares_m      = _safe(info.get("sharesOutstanding"), 0) / 1e6
    beta          = _safe(info.get("beta"), 1.0)
    excess_cash_m = max(0.0, total_cash_m - base_sales_m * 0.01)
    rf_rate       = _fetch_rf_rate()
    emp           = 0.055
    ke            = rf_rate + beta * emp
    pretax_kd     = rf_rate + 0.015
    total_cap     = market_cap_m + total_debt_m
    we = market_cap_m / total_cap if total_cap > 0 else 0.8
    wd = total_debt_m / total_cap if total_cap > 0 else 0.2
    wacc = we * ke + wd * pretax_kd * (1 - cash_tax_rate_3yr)

    return CompanyData(
        ticker=ticker.upper(), name=info.get("longName", ticker),
        sector=info.get("sector", "Unknown"), industry=info.get("industry", "Unknown"),
        current_price=_safe(info.get("currentPrice") or info.get("regularMarketPrice"), 0),
        market_cap_m=market_cap_m, shares_outstanding_m=shares_m,
        beta=beta, pe_ratio=_safe(info.get("trailingPE"), 20.0),
        base_sales_m=base_sales_m, sales_growth_3yr=sales_growth_3yr,
        op_margin_3yr=op_margin_3yr, cash_tax_rate_3yr=cash_tax_rate_3yr,
        ifcr_3yr=ifcr_3yr, iwcr_3yr=iwcr_3yr,
        excess_cash_m=excess_cash_m, total_debt_m=total_debt_m,
        underfunded_pension_m=0.0, rf_rate=rf_rate,
        equity_market_premium=emp, equity_weight=we, debt_weight=wd,
        pretax_cost_of_debt=pretax_kd, wacc=wacc,
        currency=info.get("currency", "USD"), warnings=warnings, raw=info,
    )


# ── Public entry point ────────────────────────────────────────────────────────

def fetch_company_data(ticker: str, api_key: str = "") -> CompanyData:
    """
    Fetch company data.
    - api_key provided: use Alpha Vantage (reliable on all servers).
    - no key: fall back to yfinance (works locally, often rate-limited on cloud).
    """
    ticker = ticker.upper().strip()
    if api_key and api_key.strip():
        return _fetch_av(ticker, api_key.strip())
    return _fetch_yfinance(ticker)
