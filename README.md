# Expectations Investing — Streamlit App

A full interactive implementation of the **Expectations Investing** framework by Michael Mauboussin & Alfred Rappaport.

## Modules

| Page | Chapter | Description |
|---|---|---|
| Home | — | Framework overview |
| 🏗️ DCF Engine | Ch 2 | Shareholder Value Road Map from scratch |
| 🔎 PIE Estimator | Ch 5 | Reverse-engineer stock price to implied growth |
| ⚡ Turbo Trigger | Ch 3 & 6 | Sensitivity / tornado analysis for value drivers |
| 🎯 Buy / Sell / Hold | Ch 7 | Expected Value calculator with scenario probabilities |
| 🔁 Share Buybacks | Ch 11 | Golden Rule analyser, EPS accretion, wealth transfer |

## Local Development

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/expectations-investing.git
cd expectations-investing

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v

# Launch app
streamlit run app.py
```

## Deploy to Streamlit Community Cloud

1. Push this repository to GitHub (public or private).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app**.
4. Select your repository, branch (`main`), and set **Main file path** to `app.py`.
5. Click **Deploy**.

Streamlit Cloud will install `requirements.txt` automatically and serve the app.

## Project Structure

```
expectations_investing/
├── app.py                        # Home page & app entry point
├── requirements.txt
├── .streamlit/
│   └── config.toml               # Theme configuration
├── pages/
│   ├── 1_DCF_Engine.py           # Chapter 2
│   ├── 2_PIE_Estimator.py        # Chapter 5
│   ├── 3_Turbo_Trigger.py        # Chapters 3 & 6
│   ├── 4_Buy_Sell_Hold.py        # Chapter 7
│   └── 5_Share_Buybacks.py       # Chapter 11
├── utils/
│   └── calculations.py           # All financial formulas
└── tests/
    └── test_calculations.py      # Unit tests (pytest)
```

## Formulas Implemented

- Free Cash Flow: `FCF = NOPAT − Investment`
- NOPAT: `Op. Profit × (1 − Cash Tax Rate)`
- Investment: `(IFCR + IWCR) × ΔSales`
- Continuing Value: `NOPAT × (1 + i·p) / (WACC − i·p)`
- Shareholder Value: `PV(FCFs) + PV(CV) + Non-Op Assets − Debt`
- Cost of Equity (CAPM): `R_f + β × (E_m − R_f)`
- WACC: `w_e × r_e + w_d × r_d × (1 − t)`
- Expected Value: `Σ(Payoff × Probability)`
- Buyback ROR: `Cost of Equity / (Price / Expected Value)`
- EPS Accretion Test: `1/P·E > After-tax Interest Rate`
