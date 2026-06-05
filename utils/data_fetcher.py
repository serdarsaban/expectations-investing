"""
Data fetcher for Expectations Investing app.
Sources:
  - Yahoo Finance (yfinance): price, market cap, beta, income statement,
    balance sheet, cash flow statement

All values are normalised to $M.
"""
import yfinance as yf
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
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    return float(val)


def _row(df, *candidates):
    for c in candidates:
        if c in df.index:
            return df.loc[c]
    return pd.Series(dtype=float)


def _col_vals(df, *candidates):
    s = _row(df, *candidates)
    if s.empty:
        return []
    return [float(v) for v in s.values if v is not None and not (isinstance(v, float) and np.isnan(v))]


def _cagr(start, end, years):
    if start <= 0 or end <= 0 or years <= 0:
        return 0.0
    return (end / start) ** (1 / years) - 1


def _avg(lst):
    clean = [x for x in lst if x is not None and not np.isnan(x)]
    return float(np.mean(clean)) if clean else 0.0


def _fetch_rf_rate():
    try:
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
        r = requests.get(url, timeout=8)
        lines = r.text.strip().split("\n")
        for line in reversed(lines):
            parts = line.split(",")
            if len(parts) == 2 and parts[1].strip() != ".":
                return float(parts[1].strip()) / 100
    except Exception:
        pass
    return 0.045


# ── Retry wrapper ─────────────────────────────────────────────────────────────

def fetch_company_data(ticker: str) -> CompanyData:
    """Fetch with exponential back-off on Yahoo Finance rate-limit errors."""
    ticker = ticker.upper().strip()
    last_err = None
    for attempt in range(4):
        if attempt > 0:
            time.sleep(2 * attempt)
        try:
            return _fetch(ticker)
        except Exception as e:
            last_err = e
            if any(x in str(e) for x in ("Too Many Requests", "Rate limit", "429")):
                continue
            raise
    raise ValueError(
        f"Yahoo Finance is rate-limiting this server. "
        f"Wait 30 seconds and try again. ({last_err})"
    )


# ── Core fetch ────────────────────────────────────────────────────────────────

def _fetch(ticker: str) -> CompanyData:
    warnings = []
    t = yf.Ticker(ticker)

    try:
        info = t.info
    except Exception as e:
        raise ValueError(f"Could not fetch data for '{ticker}'. Check the ticker symbol. ({e})")

    if not info or (info.get("regularMarketPrice") is None and info.get("currentPrice") is None):
        raise ValueError(f"No data found for ticker '{ticker}'. Please check the symbol.")

    name     = info.get("longName") or info.get("shortName") or ticker
    sector   = info.get("sector", "Unknown")
    industry = info.get("industry", "Unknown")
    currency = info.get("currency", "USD")

    current_price  = _safe(info.get("currentPrice") or info.get("regularMarketPrice"), 0)
    market_cap_m   = _safe(info.get("marketCap"), 0) / 1e6
    shares_m       = _safe(info.get("sharesOutstanding"), 0) / 1e6
    beta           = _safe(info.get("beta"), 1.0)
    pe_ratio       = _safe(info.get("trailingPE") or info.get("forwardPE"), 20.0)
    total_debt_m   = _safe(info.get("totalDebt"), 0) / 1e6
    total_cash_m   = _safe(info.get("totalCash"), 0) / 1e6

    try:
        income   = t.income_stmt
        balance  = t.balance_sheet
        cashflow = t.cashflow
    except Exception as e:
        warnings.append(f"Could not load financial statements: {e}")
        income = balance = cashflow = pd.DataFrame()

    # Sales
    rev_vals = _col_vals(income, "Total Revenue", "Revenue", "Net Revenue",
                          "Total Net Revenue", "Net Sales")
    if len(rev_vals) >= 2:
        base_sales_m     = rev_vals[0] / 1e6
        sales_growth_3yr = _cagr(rev_vals[-1] / 1e6, base_sales_m, len(rev_vals) - 1)
    elif len(rev_vals) == 1:
        base_sales_m     = rev_vals[0] / 1e6
        sales_growth_3yr = _safe(info.get("revenueGrowth"), 0.05)
        warnings.append("Only 1 year of revenue data; using analyst estimate for growth.")
    else:
        base_sales_m     = _safe(info.get("totalRevenue"), 1e9) / 1e6
        sales_growth_3yr = _safe(info.get("revenueGrowth"), 0.05)
        warnings.append("Revenue data unavailable from statements.")

    # Operating margin
    op_inc_vals = _col_vals(income, "Operating Income", "EBIT", "Operating Profit",
                             "Total Operating Income As Reported")
    rev_for_margin = rev_vals if rev_vals else [base_sales_m * 1e6] * 4
    if op_inc_vals and rev_for_margin:
        margins = [o / r for o, r in zip(op_inc_vals, rev_for_margin) if r != 0]
        op_margin_3yr = _avg(margins[:3])
    else:
        op_margin_3yr = _safe(info.get("operatingMargins"), 0.15)
        warnings.append("Using operating margin from info field.")

    # Cash tax rate
    tax_vals = _col_vals(income, "Tax Provision", "Income Tax Expense",
                          "Provision For Income Taxes")
    cash_tax_rates = []
    for i in range(min(len(tax_vals), len(op_inc_vals), 3)):
        if op_inc_vals[i] > 0:
            cash_tax_rates.append(abs(tax_vals[i]) / op_inc_vals[i])
    cash_tax_rate_3yr = _avg(cash_tax_rates) if cash_tax_rates else _safe(info.get("effectiveTaxRate"), 0.21)
    cash_tax_rate_3yr = min(max(cash_tax_rate_3yr, 0.05), 0.50)

    # IFCR
    capex_vals = _col_vals(cashflow, "Capital Expenditure",
                            "Purchase Of Property Plant And Equipment",
                            "Purchases Of Property And Equipment",
                            "Capital Expenditures")
    depr_vals  = _col_vals(cashflow, "Depreciation And Amortization",
                            "Depreciation Amortization Depletion", "Depreciation")
    if not depr_vals:
        depr_vals = _col_vals(income, "Reconciled Depreciation",
                               "Depreciation And Amortization In Income Statement")
    ifcr_list = []
    for i in range(min(len(capex_vals), len(depr_vals), len(rev_vals) - 1)):
        delta_sales = rev_vals[i] - rev_vals[i + 1]
        if delta_sales > 0:
            net_capex = abs(capex_vals[i]) - abs(depr_vals[i])
            ifcr_list.append(net_capex / delta_sales)
    ifcr_3yr = max(0.0, _avg(ifcr_list) if ifcr_list else 0.10)

    # IWCR
    ca_vals  = _col_vals(balance, "Current Assets", "Total Current Assets")
    cl_vals  = _col_vals(balance, "Current Liabilities", "Total Current Liabilities")
    csh_vals = _col_vals(balance, "Cash And Cash Equivalents", "Cash",
                          "Cash Cash Equivalents And Short Term Investments")
    stdebt   = _col_vals(balance, "Current Debt", "Short Term Debt",
                          "Current Debt And Capital Lease Obligation")
    iwcr_list = []
    for i in range(min(len(ca_vals), len(cl_vals), len(csh_vals), len(rev_vals) - 1)):
        st_i   = stdebt[i]   if i     < len(stdebt) else 0
        st_i1  = stdebt[i+1] if i + 1 < len(stdebt) else 0
        owc_c  = ca_vals[i]   - csh_vals[i]   - (cl_vals[i]   - st_i)
        owc_p  = ca_vals[i+1] - csh_vals[i+1] - (cl_vals[i+1] - st_i1)
        d_owc  = owc_c - owc_p
        d_sale = rev_vals[i] - rev_vals[i+1]
        if d_sale > 0:
            iwcr_list.append(d_owc / d_sale)
    iwcr_3yr = min(max(_avg(iwcr_list) if iwcr_list else 0.05, 0.0), 0.50)

    # Non-operating
    excess_cash_m        = max(0.0, total_cash_m - base_sales_m * 0.01)
    underfunded_pension_m = 0.0

    # WACC
    rf_rate = _fetch_rf_rate()
    emp     = 0.055
    ke      = rf_rate + beta * emp

    int_exp = _col_vals(income, "Interest Expense", "Interest Expense Non Operating")
    if int_exp and total_debt_m > 0:
        pretax_kd = min(max(abs(int_exp[0]) / (total_debt_m * 1e6), 0.01), 0.15)
    else:
        pretax_kd = rf_rate + 0.015

    total_capital = market_cap_m + total_debt_m
    we = market_cap_m / total_capital if total_capital > 0 else 0.8
    wd = total_debt_m / total_capital if total_capital > 0 else 0.2

    wacc = we * ke + wd * pretax_kd * (1 - cash_tax_rate_3yr)

    return CompanyData(
        ticker=ticker, name=name, sector=sector, industry=industry,
        current_price=current_price, market_cap_m=market_cap_m,
        shares_outstanding_m=shares_m, beta=beta, pe_ratio=pe_ratio,
        base_sales_m=base_sales_m, sales_growth_3yr=sales_growth_3yr,
        op_margin_3yr=op_margin_3yr, cash_tax_rate_3yr=cash_tax_rate_3yr,
        ifcr_3yr=ifcr_3yr, iwcr_3yr=iwcr_3yr,
        excess_cash_m=excess_cash_m, total_debt_m=total_debt_m,
        underfunded_pension_m=underfunded_pension_m,
        rf_rate=rf_rate, equity_market_premium=emp,
        equity_weight=we, debt_weight=wd,
        pretax_cost_of_debt=pretax_kd, wacc=wacc,
        currency=currency, warnings=warnings, raw=info,
    )
