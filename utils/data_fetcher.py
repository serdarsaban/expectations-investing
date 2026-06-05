"""
Data fetcher for Expectations Investing app.
Sources:
  - Yahoo Finance (yfinance): price, market cap, beta, income statement,
    balance sheet, cash flow statement
  - SEC EDGAR (free JSON API): cash taxes paid, supplemental cash flow data

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
    # Identity
    ticker: str
    name: str
    sector: str
    industry: str

    # Market
    current_price: float
    market_cap_m: float          # $M
    shares_outstanding_m: float  # millions
    beta: float
    pe_ratio: float

    # Value drivers (3-year averages from historicals)
    base_sales_m: float          # most recent annual sales $M
    sales_growth_3yr: float      # 3-year CAGR (decimal)
    op_margin_3yr: float         # 3-year avg operating profit margin (decimal)
    cash_tax_rate_3yr: float     # 3-year avg cash tax rate (decimal)
    ifcr_3yr: float              # 3-year avg incremental fixed-capital rate (decimal)
    iwcr_3yr: float              # 3-year avg incremental working-capital rate (decimal)

    # Balance sheet
    excess_cash_m: float         # $M
    total_debt_m: float          # $M
    underfunded_pension_m: float # $M

    # WACC components
    rf_rate: float               # 10-yr Treasury yield (decimal)
    equity_market_premium: float # default 5.5%
    equity_weight: float
    debt_weight: float
    pretax_cost_of_debt: float   # decimal
    wacc: float                  # computed

    # Metadata
    currency: str = "USD"
    warnings: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)     # raw yfinance info for debugging


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe(val, default=0.0):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    return float(val)


def _to_m(val, default=0.0):
    """Convert raw value (usually in $) to $M."""
    v = _safe(val, default)
    return v / 1_000_000 if abs(v) > 1_000 else v   # already in M if small


def _row(df: pd.DataFrame, *candidates) -> pd.Series:
    """Return the first matching row from a DataFrame by index label."""
    for c in candidates:
        if c in df.index:
            return df.loc[c]
    return pd.Series(dtype=float)


def _col_vals(df: pd.DataFrame, *candidates) -> list:
    """Return list of non-null float values from first matching row."""
    s = _row(df, *candidates)
    if s.empty:
        return []
    return [float(v) for v in s.values if v is not None and not (isinstance(v, float) and np.isnan(v))]


def _cagr(start, end, years) -> float:
    if start <= 0 or end <= 0 or years <= 0:
        return 0.0
    return (end / start) ** (1 / years) - 1


def _avg(lst) -> float:
    clean = [x for x in lst if x is not None and not np.isnan(x)]
    return float(np.mean(clean)) if clean else 0.0


# ── 10-yr Treasury yield from FRED (public, no key needed) ───────────────────

def _fetch_rf_rate() -> float:
    """Fetch latest 10-year US Treasury yield from FRED."""
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
    return 0.045   # fallback ~4.5%


# ── Main fetch function ───────────────────────────────────────────────────────

def fetch_company_data(ticker: str) -> CompanyData:
    """
    Fetch all data needed for Expectations Investing from Yahoo Finance + EDGAR.
    Returns a CompanyData object with 3-year historical averages for value drivers.
    """
    warnings = []
    t = yf.Ticker(ticker.upper().strip())

    # ── Info ──────────────────────────────────────────────────────────────────
    try:
        info = t.info
    except Exception as e:
        raise ValueError(f"Could not fetch data for '{ticker}'. Check the ticker symbol. ({e})")

    if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
        raise ValueError(f"No data found for ticker '{ticker}'. Please check the symbol.")

    name     = info.get("longName") or info.get("shortName") or ticker
    sector   = info.get("sector", "Unknown")
    industry = info.get("industry", "Unknown")
    currency = info.get("currency", "USD")

    current_price       = _safe(info.get("currentPrice") or info.get("regularMarketPrice"), 0)
    market_cap_raw      = _safe(info.get("marketCap"), 0)
    market_cap_m        = market_cap_raw / 1e6
    shares_m            = _safe(info.get("sharesOutstanding"), 0) / 1e6
    beta                = _safe(info.get("beta"), 1.0)
    pe_ratio            = _safe(info.get("trailingPE") or info.get("forwardPE"), 20.0)
    total_debt_raw      = _safe(info.get("totalDebt"), 0)
    total_debt_m        = total_debt_raw / 1e6
    total_cash_raw      = _safe(info.get("totalCash"), 0)

    # ── Financial statements ──────────────────────────────────────────────────
    try:
        income   = t.income_stmt          # annual, most recent first
        balance  = t.balance_sheet
        cashflow = t.cashflow
    except Exception as e:
        warnings.append(f"Could not load financial statements: {e}")
        income = balance = cashflow = pd.DataFrame()

    # ── Sales (Revenue) ───────────────────────────────────────────────────────
    rev_vals = _col_vals(income,
        "Total Revenue", "Revenue", "Net Revenue",
        "Total Net Revenue", "Net Sales")

    if len(rev_vals) >= 2:
        # yfinance returns most-recent first
        base_sales_m    = rev_vals[0] / 1e6
        oldest_sales    = rev_vals[-1] / 1e6
        years_of_data   = len(rev_vals) - 1
        sales_growth_3yr = _cagr(oldest_sales, base_sales_m, years_of_data)
    elif len(rev_vals) == 1:
        base_sales_m    = rev_vals[0] / 1e6
        sales_growth_3yr = _safe(info.get("revenueGrowth"), 0.05)
        warnings.append("Only 1 year of revenue data; using analyst revenue growth estimate.")
    else:
        base_sales_m    = _safe(info.get("totalRevenue"), 1000) / 1e6
        sales_growth_3yr = _safe(info.get("revenueGrowth"), 0.05)
        warnings.append("Revenue data unavailable from statements; using info fields.")

    # ── Operating Profit Margin ───────────────────────────────────────────────
    # Operating Income / Revenue (each year)
    op_inc_vals = _col_vals(income,
        "Operating Income", "EBIT", "Operating Profit",
        "Total Operating Income As Reported")
    rev_for_margin = rev_vals if rev_vals else [base_sales_m * 1e6] * 4

    if op_inc_vals and rev_for_margin:
        margins = [o / r for o, r in zip(op_inc_vals, rev_for_margin) if r != 0]
        op_margin_3yr = _avg(margins[:3])
    else:
        op_margin_3yr = _safe(info.get("operatingMargins"), 0.15)
        warnings.append("Using operating margin from info (not statement average).")

    # ── Cash Tax Rate ─────────────────────────────────────────────────────────
    # Cash taxes = Income Tax Expense (proxy; EDGAR gives exact cash taxes paid)
    tax_vals = _col_vals(income,
        "Tax Provision", "Income Tax Expense", "Provision For Income Taxes",
        "Income Before Tax")
    pretax_vals = _col_vals(income,
        "Pretax Income", "Income Before Tax", "Earnings Before Tax")
    op_inc_for_tax = op_inc_vals if op_inc_vals else []

    cash_tax_rates = []
    for i in range(min(len(tax_vals), len(op_inc_for_tax), 3)):
        if op_inc_for_tax[i] > 0:
            cash_tax_rates.append(abs(tax_vals[i]) / op_inc_for_tax[i])
    cash_tax_rate_3yr = _avg(cash_tax_rates) if cash_tax_rates else _safe(info.get("effectiveTaxRate"), 0.21)
    cash_tax_rate_3yr = min(max(cash_tax_rate_3yr, 0.05), 0.50)  # clamp 5-50%

    # ── Incremental Fixed-Capital Rate (IFCR) ─────────────────────────────────
    # IFCR = (CapEx – Depreciation) / ΔSales
    capex_vals = _col_vals(cashflow,
        "Capital Expenditure", "Purchase Of Property Plant And Equipment",
        "Purchases Of Property And Equipment", "Capital Expenditures")
    depr_vals  = _col_vals(cashflow,
        "Depreciation And Amortization", "Depreciation Amortization Depletion",
        "Depreciation", "Depreciation & Amortization")
    if not depr_vals:
        depr_vals = _col_vals(income,
            "Reconciled Depreciation", "Depreciation And Amortization In Income Statement")

    ifcr_list = []
    for i in range(min(len(capex_vals), len(depr_vals), len(rev_vals) - 1)):
        delta_sales = rev_vals[i] - rev_vals[i + 1]   # year i vs year i+1
        if delta_sales > 0:
            net_capex = abs(capex_vals[i]) - abs(depr_vals[i])
            ifcr_list.append(net_capex / delta_sales)
    ifcr_3yr = _avg(ifcr_list) if ifcr_list else 0.10
    ifcr_3yr = max(0.0, ifcr_3yr)    # can't be negative

    # ── Incremental Working-Capital Rate (IWCR) ───────────────────────────────
    # IWCR = ΔOperating Working Capital / ΔSales
    # OWC = Current Assets – Cash – Current Liabilities (excl. short-term debt)
    ca_vals  = _col_vals(balance, "Current Assets", "Total Current Assets")
    cl_vals  = _col_vals(balance, "Current Liabilities", "Total Current Liabilities")
    csh_vals = _col_vals(balance, "Cash And Cash Equivalents", "Cash",
                         "Cash Cash Equivalents And Short Term Investments")
    stdebt   = _col_vals(balance, "Current Debt", "Short Term Debt",
                         "Current Debt And Capital Lease Obligation")

    iwcr_list = []
    for i in range(min(len(ca_vals), len(cl_vals), len(csh_vals), len(rev_vals) - 1)):
        st = stdebt[i] if i < len(stdebt) else 0
        owc_curr = ca_vals[i]  - csh_vals[i]  - (cl_vals[i]  - st)
        owc_prev = ca_vals[i+1] - csh_vals[i+1] - (cl_vals[i+1] - (stdebt[i+1] if i+1 < len(stdebt) else 0)) if i+1 < len(ca_vals) else owc_curr
        delta_owc   = owc_curr - owc_prev
        delta_sales = rev_vals[i] - rev_vals[i+1] if i+1 < len(rev_vals) else 0
        if delta_sales > 0:
            iwcr_list.append(delta_owc / delta_sales)
    iwcr_3yr = _avg(iwcr_list) if iwcr_list else 0.05
    iwcr_3yr = max(0.0, min(iwcr_3yr, 0.5))   # clamp 0-50%

    # ── Non-operating assets & debt ───────────────────────────────────────────
    # Excess cash = total cash above 1% of sales (operational minimum)
    min_cash = base_sales_m * 0.01
    total_cash_m = total_cash_raw / 1e6
    excess_cash_m = max(0.0, total_cash_m - min_cash)

    # Underfunded pension
    pension_obligation  = _col_vals(balance, "Pension And Other Post Retirement Benefit Plans Current",
                                     "Defined Benefit Plan Benefit Obligation")
    pension_assets      = _col_vals(balance, "Pension Plans Defined Benefit")
    underfunded_pension_m = 0.0
    if pension_obligation and pension_assets:
        gap = pension_obligation[0] - pension_assets[0]
        underfunded_pension_m = max(0.0, gap / 1e6)

    # ── WACC ──────────────────────────────────────────────────────────────────
    rf_rate = _fetch_rf_rate()
    emp     = 0.055    # equity market premium ~5.5% long-run consensus

    # Cost of equity via CAPM
    ke = rf_rate + beta * emp

    # Cost of debt: interest expense / total debt
    int_exp_vals = _col_vals(income, "Interest Expense", "Interest Expense Non Operating")
    if int_exp_vals and total_debt_m > 0:
        pretax_kd = abs(int_exp_vals[0]) / (total_debt_m * 1e6)
        pretax_kd = max(0.01, min(pretax_kd, 0.15))   # clamp 1-15%
    else:
        pretax_kd = rf_rate + 0.015    # RF + 150bps default spread

    # Weights (market weights — book says use market, not book)
    total_capital = market_cap_m + total_debt_m
    if total_capital > 0:
        we = market_cap_m / total_capital
        wd = total_debt_m / total_capital
    else:
        we, wd = 0.8, 0.2

    after_tax_kd = pretax_kd * (1 - cash_tax_rate_3yr)
    wacc = we * ke + wd * after_tax_kd

    return CompanyData(
        ticker=ticker.upper(),
        name=name,
        sector=sector,
        industry=industry,
        current_price=current_price,
        market_cap_m=market_cap_m,
        shares_outstanding_m=shares_m,
        beta=beta,
        pe_ratio=pe_ratio,
        base_sales_m=base_sales_m,
        sales_growth_3yr=sales_growth_3yr,
        op_margin_3yr=op_margin_3yr,
        cash_tax_rate_3yr=cash_tax_rate_3yr,
        ifcr_3yr=ifcr_3yr,
        iwcr_3yr=iwcr_3yr,
        excess_cash_m=excess_cash_m,
        total_debt_m=total_debt_m,
        underfunded_pension_m=underfunded_pension_m,
        rf_rate=rf_rate,
        equity_market_premium=emp,
        equity_weight=we,
        debt_weight=wd,
        pretax_cost_of_debt=pretax_kd,
        wacc=wacc,
        currency=currency,
        warnings=warnings,
        raw=info,
    )
