"""
Data fetcher for Expectations Investing app.
Primary source: Financial Modeling Prep (FMP) API — reliable on hosted servers.
Fallback: yfinance — works locally but rate-limited on Streamlit Cloud.

Get a free FMP key at: https://financialmodelingprep.com/developer/docs
Free tier: 250 requests/day, no IP blocking.
"""
import requests
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List
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
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    try:
        return float(val)
    except Exception:
        return default


def _avg(lst: list) -> float:
    clean = [x for x in lst if x is not None and not (isinstance(x, float) and np.isnan(x))]
    return float(np.mean(clean)) if clean else 0.0


def _cagr(start, end, years) -> float:
    if start <= 0 or end <= 0 or years <= 0:
        return 0.0
    return (end / start) ** (1 / years) - 1


def _fetch_rf_rate() -> float:
    """Live 10-yr Treasury from FRED."""
    try:
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
        r = requests.get(url, timeout=8)
        for line in reversed(r.text.strip().split("\n")):
            parts = line.split(",")
            if len(parts) == 2 and parts[1].strip() not in (".", ""):
                return float(parts[1].strip()) / 100
    except Exception:
        pass
    return 0.045   # fallback


# ── FMP fetcher ───────────────────────────────────────────────────────────────

FMP_BASE = "https://financialmodelingprep.com/api/v3"


def _fmp_get(path: str, api_key: str, params: dict = None) -> dict | list:
    p = params or {}
    p["apikey"] = api_key
    r = requests.get(f"{FMP_BASE}/{path}", params=p, timeout=12)
    r.raise_for_status()
    return r.json()


def _fetch_fmp(ticker: str, api_key: str) -> CompanyData:
    warnings = []
    t = ticker.upper()

    # Profile (price, market cap, beta, shares, sector, etc.)
    profile_data = _fmp_get(f"profile/{t}", api_key)
    if not profile_data or not isinstance(profile_data, list):
        raise ValueError(f"No data found for '{t}'. Check the ticker symbol.")
    p = profile_data[0]

    name          = p.get("companyName", t)
    sector        = p.get("sector", "Unknown")
    industry      = p.get("industry", "Unknown")
    currency      = p.get("currency", "USD")
    current_price = _safe(p.get("price"), 0)
    market_cap_m  = _safe(p.get("mktCap"), 0) / 1e6
    shares_m      = _safe(p.get("sharesOutstanding"), 0) / 1e6
    beta          = _safe(p.get("beta"), 1.0)

    # Income statement (annual, last 4 years)
    income = _fmp_get(f"income-statement/{t}", api_key, {"limit": 4, "period": "annual"})
    if not income or not isinstance(income, list):
        raise ValueError(f"No financial statements found for '{t}'.")

    revenues    = [_safe(y.get("revenue"), 0)          for y in income]
    op_incomes  = [_safe(y.get("operatingIncome"), 0)  for y in income]
    tax_exps    = [_safe(y.get("incomeTaxExpense"), 0) for y in income]
    int_exps    = [_safe(y.get("interestExpense"), 0)  for y in income]
    net_incomes = [_safe(y.get("netIncome"), 0)        for y in income]

    # Balance sheet (annual, last 4 years)
    balance = _fmp_get(f"balance-sheet-statement/{t}", api_key, {"limit": 4, "period": "annual"})
    if not balance:
        balance = []

    total_assets_list = [_safe(y.get("totalAssets"), 0)            for y in balance]
    cash_list         = [_safe(y.get("cashAndCashEquivalents"), 0)  for y in balance]
    ca_list           = [_safe(y.get("totalCurrentAssets"), 0)      for y in balance]
    cl_list           = [_safe(y.get("totalCurrentLiabilities"), 0) for y in balance]
    std_list          = [_safe(y.get("shortTermDebt"), 0)           for y in balance]
    ltd_list          = [_safe(y.get("longTermDebt"), 0)            for y in balance]

    total_debt_m = (_safe(balance[0].get("totalDebt"), 0) if balance else 0) / 1e6

    # Cash flow statement
    cashflow = _fmp_get(f"cash-flow-statement/{t}", api_key, {"limit": 4, "period": "annual"})
    if not cashflow:
        cashflow = []

    capex_list = [abs(_safe(y.get("capitalExpenditure"), 0))        for y in cashflow]
    depr_list  = [_safe(y.get("depreciationAndAmortization"), 0)    for y in cashflow]

    # ── Value drivers ─────────────────────────────────────────────────────────

    # Sales growth (3-yr CAGR, most recent = index 0)
    base_sales_m = revenues[0] / 1e6 if revenues else 0
    if len(revenues) >= 2:
        sales_growth_3yr = _cagr(revenues[-1], revenues[0], len(revenues) - 1)
    else:
        sales_growth_3yr = 0.05
        warnings.append("Limited revenue history; defaulting growth to 5%.")

    # Operating margin (3-yr avg)
    margins = [o / r for o, r in zip(op_incomes, revenues) if r > 0]
    op_margin_3yr = _avg(margins[:3]) if margins else 0.15

    # Cash tax rate (tax / op income, 3-yr avg)
    tax_rates = [abs(tx) / oi for tx, oi in zip(tax_exps, op_incomes) if oi > 0]
    cash_tax_rate_3yr = min(max(_avg(tax_rates[:3]) if tax_rates else 0.21, 0.05), 0.50)

    # IFCR = (CapEx - Dep) / ΔSales
    ifcr_list = []
    for i in range(min(len(capex_list), len(depr_list), len(revenues) - 1)):
        d_sales = revenues[i] - revenues[i + 1]
        if d_sales > 0:
            ifcr_list.append((capex_list[i] - depr_list[i]) / d_sales)
    ifcr_3yr = max(0.0, _avg(ifcr_list) if ifcr_list else 0.10)

    # IWCR = ΔOp. Working Capital / ΔSales
    iwcr_list = []
    for i in range(min(len(ca_list), len(cl_list), len(cash_list), len(revenues) - 1)):
        st_i  = std_list[i]     if i     < len(std_list) else 0
        st_i1 = std_list[i + 1] if i + 1 < len(std_list) else 0
        owc_c = ca_list[i]     - cash_list[i]     - (cl_list[i]     - st_i)
        owc_p = ca_list[i + 1] - cash_list[i + 1] - (cl_list[i + 1] - st_i1)
        d_owc   = owc_c - owc_p
        d_sales = revenues[i] - revenues[i + 1]
        if d_sales > 0:
            iwcr_list.append(d_owc / d_sales)
    iwcr_3yr = min(max(_avg(iwcr_list) if iwcr_list else 0.05, 0.0), 0.50)

    # Non-operating
    total_cash_m  = cash_list[0] / 1e6 if cash_list else 0
    excess_cash_m = max(0.0, total_cash_m - base_sales_m * 0.01)

    # WACC
    rf_rate = _fetch_rf_rate()
    emp     = 0.055
    ke      = rf_rate + beta * emp

    if int_exps and total_debt_m > 0:
        pretax_kd = min(max(abs(int_exps[0]) / (total_debt_m * 1e6), 0.01), 0.15)
    else:
        pretax_kd = rf_rate + 0.015

    total_cap = market_cap_m + total_debt_m
    we = market_cap_m / total_cap if total_cap > 0 else 0.8
    wd = total_debt_m / total_cap if total_cap > 0 else 0.2
    wacc = we * ke + wd * pretax_kd * (1 - cash_tax_rate_3yr)

    # P/E
    pe_ratio = current_price / (net_incomes[0] / (shares_m * 1e6)) if (net_incomes and shares_m > 0 and net_incomes[0] > 0) else 20.0

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
        currency=currency, warnings=warnings, raw=p,
    )


# ── yfinance fallback ─────────────────────────────────────────────────────────

def _fetch_yfinance(ticker: str) -> CompanyData:
    """Fallback for local use. Rate-limited on Streamlit Cloud."""
    import yfinance as yf
    warnings = ["Using yfinance fallback — may be rate-limited on hosted servers."]
    t = yf.Ticker(ticker)
    info = t.info

    if not info or (info.get("regularMarketPrice") is None and info.get("currentPrice") is None):
        raise ValueError(f"No data found for '{ticker}'.")

    def col_vals(df, *candidates):
        for c in candidates:
            if c in df.index:
                s = df.loc[c]
                return [float(v) for v in s.values
                        if v is not None and not (isinstance(v, float) and np.isnan(v))]
        return []

    income  = t.income_stmt
    balance = t.balance_sheet
    cf      = t.cashflow

    rev   = col_vals(income, "Total Revenue", "Revenue")
    op_i  = col_vals(income, "Operating Income", "EBIT")
    tax_v = col_vals(income, "Tax Provision", "Income Tax Expense")
    capex = col_vals(cf, "Capital Expenditure", "Purchase Of Property Plant And Equipment")
    depr  = col_vals(cf, "Depreciation And Amortization", "Depreciation Amortization Depletion")
    ca    = col_vals(balance, "Current Assets", "Total Current Assets")
    cl    = col_vals(balance, "Current Liabilities", "Total Current Liabilities")
    csh   = col_vals(balance, "Cash And Cash Equivalents", "Cash")
    std   = col_vals(balance, "Current Debt", "Short Term Debt")

    base_sales_m     = rev[0] / 1e6 if rev else _safe(info.get("totalRevenue"), 1e9) / 1e6
    sales_growth_3yr = _cagr(rev[-1], rev[0], len(rev) - 1) if len(rev) >= 2 else _safe(info.get("revenueGrowth"), 0.05)
    margins          = [o / r for o, r in zip(op_i, rev) if r > 0]
    op_margin_3yr    = _avg(margins[:3]) if margins else _safe(info.get("operatingMargins"), 0.15)
    tax_rates_       = [abs(tx) / oi for tx, oi in zip(tax_v, op_i) if oi > 0]
    cash_tax_rate_3yr = min(max(_avg(tax_rates_[:3]) if tax_rates_ else _safe(info.get("effectiveTaxRate"), 0.21), 0.05), 0.50)

    ifcr_list = []
    for i in range(min(len(capex), len(depr), len(rev) - 1)):
        ds = rev[i] - rev[i + 1]
        if ds > 0:
            ifcr_list.append((abs(capex[i]) - abs(depr[i])) / ds)
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

    rf_rate   = _fetch_rf_rate()
    emp       = 0.055
    ke        = rf_rate + beta * emp
    pretax_kd = rf_rate + 0.015
    total_cap = market_cap_m + total_debt_m
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

def fetch_company_data(ticker: str, fmp_api_key: str = "") -> CompanyData:
    """
    Fetch company data.
    - If fmp_api_key is provided: use FMP (reliable on all servers).
    - Otherwise: fall back to yfinance (works locally, rate-limited on cloud).
    """
    ticker = ticker.upper().strip()
    if fmp_api_key and fmp_api_key.strip():
        return _fetch_fmp(ticker, fmp_api_key.strip())
    else:
        return _fetch_yfinance(ticker)
