"""
Core financial calculations for Expectations Investing.
All formulas sourced from Mauboussin & Rappaport chapters 2, 3, 5, 6, 7, 11.
"""
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class DCFInputs:
    base_sales: float          # Year 0 sales ($M)
    sales_growth: float        # Annual sales growth rate (decimal)
    op_margin: float           # Operating profit margin (decimal)
    cash_tax_rate: float       # Cash tax rate (decimal)
    ifcr: float                # Incremental fixed-capital rate (decimal)
    iwcr: float                # Incremental working-capital rate (decimal)
    wacc: float                # Weighted average cost of capital (decimal)
    forecast_years: int        # Number of forecast years
    inflation: float = 0.02    # Long-run inflation rate for CV (decimal)
    pricing_power: float = 1.0 # Pricing power factor 0–1
    excess_cash: float = 0.0   # Non-operating assets ($M)
    debt: float = 0.0          # Market value of debt ($M)


@dataclass
class YearRow:
    year: int
    sales: float
    op_profit: float
    nopat: float
    delta_sales: float
    investment: float
    fcf: float
    pv_fcf: float


@dataclass
class DCFResult:
    rows: List[YearRow]
    pv_fcfs: float
    continuing_value: float      # Terminal value at end of forecast period
    pv_continuing_value: float
    operating_value: float
    shareholder_value: float
    last_nopat: float


# ── Core DCF ─────────────────────────────────────────────────────────────────

def run_dcf(inp: DCFInputs) -> DCFResult:
    """
    Forward DCF: compute year-by-year FCF and shareholder value.
    Ch 2 formulas:
      Op. Profit = Sales × OPM
      NOPAT = Op. Profit × (1 – tax)
      Investment = (IFCR + IWCR) × ΔSales
      FCF = NOPAT – Investment
      CV = NOPAT_N × (1 + i×p) / (WACC – i×p)   [partial-inflation perpetuity]
      Shareholder Value = PV(FCFs) + PV(CV) + Non-op assets – Debt
    """
    g = inp.inflation * inp.pricing_power   # effective CV growth rate
    rows: List[YearRow] = []
    prev_sales = inp.base_sales
    total_pv_fcf = 0.0

    for t in range(1, inp.forecast_years + 1):
        sales = prev_sales * (1 + inp.sales_growth)
        delta_sales = sales - prev_sales
        op_profit = sales * inp.op_margin
        nopat = op_profit * (1 - inp.cash_tax_rate)
        investment = (inp.ifcr + inp.iwcr) * delta_sales
        fcf = nopat - investment
        df = (1 + inp.wacc) ** t
        pv_fcf = fcf / df
        total_pv_fcf += pv_fcf
        rows.append(YearRow(
            year=t, sales=sales, op_profit=op_profit, nopat=nopat,
            delta_sales=delta_sales, investment=investment, fcf=fcf, pv_fcf=pv_fcf
        ))
        prev_sales = sales

    last_nopat = rows[-1].nopat
    # Continuing value (partial-inflation perpetuity)
    if inp.wacc > g:
        cv = last_nopat * (1 + g) / (inp.wacc - g)
    else:
        cv = last_nopat * 50  # cap to avoid division by zero
    pv_cv = cv / (1 + inp.wacc) ** inp.forecast_years
    op_value = total_pv_fcf + pv_cv
    sv = op_value + inp.excess_cash - inp.debt

    return DCFResult(
        rows=rows,
        pv_fcfs=total_pv_fcf,
        continuing_value=cv,
        pv_continuing_value=pv_cv,
        operating_value=op_value,
        shareholder_value=sv,
        last_nopat=last_nopat,
    )


# ── PIE: reverse-engineer stock price ────────────────────────────────────────

def solve_pie_growth(
    target_sv: float,
    inp: DCFInputs,
    lo: float = 0.0,
    hi: float = 0.5,
    tol: float = 1e-5,
    max_iter: int = 200,
) -> Optional[float]:
    """
    Binary search: find the sales_growth rate that makes DCF shareholder value
    equal to target_sv (the market price × shares, or per-share if using
    per-share sales).
    Returns implied growth rate or None if not solvable in range.
    Ch 5: reverse-engineer PIE by holding OPM/Tax/Inv constant and solving
    for the growth rate that matches the market price.
    """
    def sv_at(g):
        i2 = DCFInputs(**{**inp.__dict__, 'sales_growth': g})
        return run_dcf(i2).shareholder_value

    lo_val = sv_at(lo)
    hi_val = sv_at(hi)
    if target_sv < lo_val or target_sv > hi_val:
        # Try wider range
        if target_sv < lo_val:
            return lo
        return hi

    for _ in range(max_iter):
        mid = (lo + hi) / 2
        mid_val = sv_at(mid)
        if abs(mid_val - target_sv) < tol:
            return mid
        if mid_val < target_sv:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def solve_pie_forecast_period(
    target_sv: float,
    inp: DCFInputs,
    max_years: int = 30,
) -> Optional[int]:
    """
    Ch 5: find market-implied forecast period by extending the DCF horizon
    until the shareholder value matches the stock price.
    """
    for yrs in range(1, max_years + 1):
        i2 = DCFInputs(**{**inp.__dict__, 'forecast_years': yrs})
        sv = run_dcf(i2).shareholder_value
        if sv >= target_sv:
            return yrs
    return max_years


# ── Sensitivity / Turbo Trigger ───────────────────────────────────────────────

def sensitivity_table(inp: DCFInputs, driver: str, values: List[float]) -> List[dict]:
    """
    Ch 3 / 6: sweep one value driver and compute shareholder value at each level.
    driver: 'sales_growth' | 'op_margin' | 'wacc' | 'ifcr' | 'iwcr'
    """
    rows = []
    for v in values:
        i2 = DCFInputs(**{**inp.__dict__, driver: v})
        sv = run_dcf(i2).shareholder_value
        rows.append({'value': v, 'shareholder_value': sv})
    return rows


# ── Expected Value / Buy-Sell-Hold ────────────────────────────────────────────

@dataclass
class Scenario:
    label: str
    stock_value: float
    probability: float    # 0–1

    @property
    def weighted(self) -> float:
        return self.stock_value * self.probability


def expected_value(scenarios: List[Scenario]) -> float:
    """Ch 7: EV = Σ(payoff × probability)"""
    return sum(s.weighted for s in scenarios)


def annual_excess_return(current_price: float, ev: float, years_to_converge: float) -> float:
    """
    Ch 7: annualised excess return if stock converges to EV.
    = (EV / Price)^(1/T) – 1
    """
    if current_price <= 0 or years_to_converge <= 0:
        return 0.0
    return (ev / current_price) ** (1 / years_to_converge) - 1


def tax_hurdle(buy_price: float, sell_price: float, tax_rate: float, wacc: float) -> dict:
    """
    Ch 7: Calculate the minimum excess return needed to justify selling
    (after capital gains tax) vs. holding a fairly valued stock.
    """
    gain = sell_price - buy_price
    tax_paid = gain * tax_rate
    reinvest_amount = sell_price - tax_paid
    hurdle = wacc * (sell_price / reinvest_amount) - wacc
    return {
        'gain': gain,
        'tax_paid': tax_paid,
        'reinvest_amount': reinvest_amount,
        'excess_return_needed': hurdle,
    }


# ── Share Buyback ─────────────────────────────────────────────────────────────

def buyback_rate_of_return(cost_of_equity: float, price: float, expected_value: float) -> float:
    """
    Ch 11: Buyback ROR = Cost of Equity / (Price / Expected Value)
    Attractive when Price < Expected Value (ratio < 1).
    """
    if expected_value <= 0:
        return 0.0
    return cost_of_equity / (price / expected_value)


def eps_accretion_test(pe_ratio: float, after_tax_interest_rate: float) -> dict:
    """
    Ch 11: EPS accretion test.
    Accretive when 1/P/E > after-tax interest rate.
    """
    earnings_yield = 1 / pe_ratio if pe_ratio > 0 else 0
    accretive = earnings_yield > after_tax_interest_rate
    return {
        'earnings_yield': earnings_yield,
        'after_tax_interest_rate': after_tax_interest_rate,
        'accretive': accretive,
        'spread': earnings_yield - after_tax_interest_rate,
    }


def wealth_transfer(
    fair_value: float,
    shares_outstanding: float,
    buyback_dollars: float,
    buyback_price: float,
) -> dict:
    """
    Ch 11 Table 11.2: wealth transfer analysis.
    """
    if buyback_price <= 0:
        return {}
    shares_bought = buyback_dollars / buyback_price
    remaining_shares = shares_outstanding - shares_bought
    remaining_equity = shares_outstanding * fair_value - buyback_dollars
    new_value_per_share = remaining_equity / remaining_shares if remaining_shares > 0 else 0
    change = new_value_per_share - fair_value
    return {
        'shares_bought': shares_bought,
        'remaining_shares': remaining_shares,
        'new_value_per_share': new_value_per_share,
        'value_change_per_share': change,
        'wealth_transfer': 'To ongoing shareholders (undervalued)' if change > 0
                           else 'To sellers (overvalued)' if change < 0
                           else 'No transfer (fair value)',
    }


# ── WACC helper ───────────────────────────────────────────────────────────────

def calc_wacc(
    equity_weight: float,
    debt_weight: float,
    cost_of_equity: float,
    pretax_cost_of_debt: float,
    tax_rate: float,
) -> float:
    """WACC = w_e × r_e + w_d × r_d × (1 – t)"""
    return equity_weight * cost_of_equity + debt_weight * pretax_cost_of_debt * (1 - tax_rate)


def capm(rf: float, beta: float, market_premium: float) -> float:
    """Cost of equity = R_f + β × (E_m – R_f)"""
    return rf + beta * market_premium
