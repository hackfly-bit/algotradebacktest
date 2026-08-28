# AlgoTradeBacktest

Rules-based XAUUSD backtest pipeline.

- **Higgs/** — Django app (data layer, indicators, backtests, reports)
- **STRATEGY_DEVELOPMENT_PIPELINE.md** — research workflow
- **XAUUSD_Momentum_Pipeline.ipynb** — notebook experiments
- **exports/** — generated strategy reports

Minute-bar CSV data (`XAUUSD_2009_2026_M1.csv`) is kept local and is not in this repository (GitHub 100MB file limit). If missing, bootstrap from HuggingFace:

```text
prepare_dataset.bat
```

(or `py -3 prepare_dataset.py`). Then ingest into Higgs with `py manage.py ingest_dataset ..\XAUUSD_2009_2026_M1.csv` from the `Higgs` folder.

See `Higgs/docs/DESIGN.md` and `Higgs/AGENTS.md` for architecture and setup.
