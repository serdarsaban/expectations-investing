"""
Unit tests for Expectations Investing calculations.
Reference values from the book's worked examples.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
from utils.calculations import (
    DCFInputs, run_dcf, expected_value, Scenario,
    annual_excess_return, tax_hurdle, buyback_rate_of_return,
    eps_accretion_test, wealth_transfer, calc_wacc, capm,
    solve_pie_growth,
)


# ── Book reference: Table 2.1 ─────────────────────────────────────────────────
# Inputs: $100M sales, 10% growth, 15% OPM, 25% tax, 15% IFCR, 10% IWCR, 8% WACC
# Expected: Shareholder value ≈ $257M

def book_inputs():
    return DCFInputs(
        base_sales=100, sales_growth=0.10, op_margin=0.15,
        cash_tax_rate=0.25, ifcr=0.15, iwcr=0.10, wacc=0.08,
        forecast_years=5, inflation=0.02, pricing_power=1.0,
        excess_cash=0.0, debt=0.0,
    )


def test_book_table_2_1_shareholder_value():
    """Table 2.1: SV should be approximately $257M."""
    res = run_dcf(book_inputs())
    assert 250 < res.shareholder_value < 265, \
        f"Expected ~$257M, got ${res.shareholder_value:.2f}M"


def test_book_pv_fcfs():
    """Table 2.1: PV of FCFs ≈ $47.44M."""
    res = run_dcf(book_inputs())
    assert 44 < res.pv_fcfs < 51, f"Expected ~$47M PV FCFs, got ${res.pv_fcfs:.2f}M"


def test_book_pv_continuing_value():
    """Table 2.1: PV of continuing value ≈ $209–210M."""
    res = run_dcf(book_inputs())
    assert 200 < res.pv_continuing_value < 220, \
        f"Expected ~$210M PV CV, got ${res.pv_continuing_value:.2f}M"


def test_year1_fcf():
    """Year 1 FCF: NOPAT – Investment."""
    res = run_dcf(book_inputs())
    r = res.rows[0]
    # Sales Y1 = 110, OPM 15% => Op.Profit = 16.5, NOPAT = 12.375
    # ΔSales = 10, IFCR+IWCR = 0.25, Investment = 2.5
    # FCF = 12.375 - 2.5 = 9.875
    assert abs(r.nopat - 12.375) < 0.01
    assert abs(r.investment - 2.5) < 0.01
    assert abs(r.fcf - 9.875) < 0.01


def test_dcf_forecast_years():
    """DCF produces exactly as many rows as forecast_years."""
    for yrs in [1, 5, 10, 15]:
        inp = DCFInputs(**{**book_inputs().__dict__, 'forecast_years': yrs})
        res = run_dcf(inp)
        assert len(res.rows) == yrs


def test_non_operating_items():
    """Non-operating assets add; debt subtracts."""
    inp = book_inputs()
    res_base = run_dcf(inp)
    inp2 = DCFInputs(**{**inp.__dict__, 'excess_cash': 50, 'debt': 30})
    res2 = run_dcf(inp2)
    assert abs((res2.shareholder_value - res_base.shareholder_value) - 20) < 0.01


# ── Expected Value (Ch 7) ─────────────────────────────────────────────────────

def test_expected_value_table_7_1():
    """Table 7.1: EV = $10×15% + $42×50% + $90×35% = $54."""
    scenarios = [Scenario("Low", 10, 0.15), Scenario("Cons", 42, 0.50), Scenario("High", 90, 0.35)]
    ev = expected_value(scenarios)
    assert abs(ev - 54.0) < 0.01, f"Expected $54, got ${ev:.2f}"


def test_expected_value_table_7_4_dominos():
    """Table 7.4 Domino's consensus: EV ≈ $419."""
    scenarios = [Scenario("Low", 290, 0.25), Scenario("Cons", 418, 0.55), Scenario("High", 586, 0.20)]
    ev = expected_value(scenarios)
    assert abs(ev - 419) < 2, f"Expected ~$419, got ${ev:.2f}"


def test_annual_excess_return():
    """Stock at 80% of EV converging in 2 years → ~12.5% excess return."""
    ev = 100
    price = 80
    aer = annual_excess_return(price, ev, 2)
    assert abs(aer - 0.118) < 0.005, f"Expected ~11.8%, got {aer*100:.2f}%"


# ── Tax hurdle ────────────────────────────────────────────────────────────────

def test_tax_hurdle_book_example():
    """Ch 7: Buy $100, sell $121, 20% tax. Tax = $4.20, reinvest $116.80."""
    th = tax_hurdle(100, 121, 0.20, 0.08)
    assert abs(th['gain'] - 21) < 0.01
    assert abs(th['tax_paid'] - 4.20) < 0.01
    assert abs(th['reinvest_amount'] - 116.80) < 0.01


# ── Buyback (Ch 11) ───────────────────────────────────────────────────────────

def test_buyback_ror_undervalued():
    """When price < EV, buyback ROR > cost of equity."""
    ke = 0.08
    ror = buyback_rate_of_return(ke, price=80, expected_value=100)
    assert ror > ke, f"Expected ROR > {ke}, got {ror:.4f}"


def test_buyback_ror_overvalued():
    """When price > EV, buyback ROR < cost of equity."""
    ke = 0.08
    ror = buyback_rate_of_return(ke, price=120, expected_value=100)
    assert ror < ke, f"Expected ROR < {ke}, got {ror:.4f}"


def test_eps_accretion():
    """EPS accretion test: 1/PE > after-tax rate."""
    r = eps_accretion_test(pe_ratio=20, after_tax_interest_rate=0.03)  # yield 5% > 3%
    assert r['accretive'] is True
    r2 = eps_accretion_test(pe_ratio=50, after_tax_interest_rate=0.03)  # yield 2% < 3%
    assert r2['accretive'] is False


def test_wealth_transfer_undervalued():
    """Buying back below fair value raises value/share for ongoing shareholders."""
    result = wealth_transfer(fair_value=100, shares_outstanding=1000,
                              buyback_dollars=20000, buyback_price=50)
    assert result['value_change_per_share'] > 0


def test_wealth_transfer_overvalued():
    """Buying back above fair value reduces value/share for ongoing shareholders."""
    result = wealth_transfer(fair_value=100, shares_outstanding=1000,
                              buyback_dollars=20000, buyback_price=200)
    assert result['value_change_per_share'] < 0


# ── CAPM & WACC ───────────────────────────────────────────────────────────────

def test_dominos_capm():
    """Ch 5 Domino's: Ke = 0.65% + 1.0×5.1% = 5.75%."""
    ke = capm(rf=0.0065, beta=1.0, market_premium=0.051)
    assert abs(ke - 0.0575) < 0.0001


def test_dominos_wacc():
    """Ch 5 Domino's: WACC = 0.80×5.75% + 0.20×3.80% = 5.35%."""
    wacc = calc_wacc(equity_weight=0.80, debt_weight=0.20,
                     cost_of_equity=0.0575, pretax_cost_of_debt=0.0455,
                     tax_rate=0.165)
    assert abs(wacc - 0.0535) < 0.0005


# ── PIE solver ────────────────────────────────────────────────────────────────

def test_solve_pie_roundtrip():
    """Solve for PIE growth, then verify DCF reproduces the target SV."""
    target = 257.0
    inp = book_inputs()
    g = solve_pie_growth(target, inp)
    inp2 = DCFInputs(**{**inp.__dict__, 'sales_growth': g})
    sv = run_dcf(inp2).shareholder_value
    assert abs(sv - target) < 1.0, f"Round-trip failed: got ${sv:.2f}M"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
