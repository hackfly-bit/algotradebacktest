---
name: add-strategy
description: Adds a Higgs rules-based strategy plugin with @register_strategy, docstring logic_spec, and tests. Use when creating a new trading strategy, plugin, or when the user mentions adding a strategy to Higgs.
---

# Add strategy (Higgs)

## Do this

1. Query Codegraph / Codebase Memory (`project: Higgs`) for `register_strategy` and existing plugins.
2. Create **one** file `engine/strategies/<snake_name>.py`.
3. Implement `@register_strategy` with columns `signal`, `sl_atr`, `tp_atr`.
4. Docstring = human logic for MQL5 export (no ML language).
5. Add a test that the name appears in `list_strategies()` and isolation (no backtester import).
6. Do not edit `engine/backtester.py` unless the signal contract itself is broken.

## Contract

```python
@register_strategy
def my_strategy(df, params=None):
    """LONG if ... SHORT if ... Exit ATR multiples."""
    p = params or {}
    out = df.copy()
    out["signal"] = 0
    # fill signal with closed-bar conditions only
    out["sl_atr"] = float(p.get("atr_sl", 2.0))
    out["tp_atr"] = float(p.get("atr_tp", 4.0))
    return out
```

## Do not

- Download data, compute fees, Sharpe, or train models inside the plugin.
- Same-bar `Close` entry (backtester handles next open).
- Duplicate indicator engine code unless `_ensure_ema` for extra periods.
