# AlgoTradeBacktest

Rules-based XAUUSD backtest pipeline.

- **Higgs/** — Django app (data layer, indicators, backtests, reports)
- **STRATEGY_DEVELOPMENT_PIPELINE.md** — research workflow
- **XAUUSD_Momentum_Pipeline.ipynb** — notebook experiments
- **exports/** — generated strategy reports

Minute-bar CSV data (`XAUUSD_2009_2026_M1.csv`) is kept local and is not in this repository (GitHub 100MB file limit). Place it in the project root before running imports. If the file is missing, see **Fase 2b** in `Higgs/docs/CONVERSION_PLAN.md` (HuggingFace download + merge; not implemented yet).

See `Higgs/docs/DESIGN.md` and `Higgs/AGENTS.md` for architecture and setup.
