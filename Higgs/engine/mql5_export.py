"""MQL5 spec builder and file export. Do not import Django."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from engine.registry import get_strategy_spec


def fmt_pct(x: float) -> str:
    return f"{x:.2%}"


def fmt_num(x: float) -> str:
    return f"{x:,.2f}"


def gate_label(value: bool) -> str:
    return "PASS" if value else "FAIL"


@dataclass
class Mql5SpecContext:
    strategy_name: str
    symbol: str
    timeframe: str
    params: dict
    volume_usable: bool
    is_metrics: dict
    oos_metrics: dict
    gate: object
    mc: dict
    initial_equity: float
    fee: float
    commission_per_lot: float
    spread: float
    slippage: float
    risk_pct: float
    contract_size: float
    in_sample_end: str
    oos_start: str
    data_start: str
    data_end: str
    param_stable: bool
    perturb_stable: bool
    cost_pass: bool


def build_mql5_spec(ctx: Mql5SpecContext) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    p = ctx.params
    vol_note = (
        "applied"
        if (ctx.volume_usable and p.get("use_volume_filter", True))
        else "DISABLED (volume data dead / unused)"
    )
    logic = get_strategy_spec(ctx.strategy_name)
    boot = ctx.mc.get("bootstrap", {})
    rec_risk = ctx.risk_pct
    hard_dd = abs(
        min(
            float(ctx.oos_metrics.get("max_drawdown") or 0),
            float(boot.get("p95_worst_dd", ctx.oos_metrics.get("max_drawdown") or 0)),
        )
    )
    implement = "YES" if ctx.gate.implement_mql5 else "NO"
    g = ctx.gate

    return f"""# MQL5 Strategy Spec

## 1. Identity
- Strategy name     : {ctx.strategy_name}
- Version           : 1.0.0
- Status            : {g.status}
- Generated at      : {now}
- Source            : Higgs backtest cockpit
- Plugin function   : {ctx.strategy_name}

## 2. Market & execution
- Symbol            : {ctx.symbol}
- Timeframe         : PERIOD_H1
- Chart price       : Close of completed candle
- Entry timing      : next candle open after signal (no look-ahead)
- Magic number      : 2026081701
- Comment           : ATB_{ctx.strategy_name}

## 3. Input parameters (MQL5 `input`)
input int    InpEmaFast        = {int(p.get('ema_fast', 20))};
input int    InpEmaSlow        = {int(p.get('ema_slow', 50))};
input int    InpEmaTrend       = {int(p.get('ema_trend', 200))};
input int    InpLookback       = {int(p.get('lookback', 24))};
input int    InpRsiPeriod      = {int(p.get('rsi_period', 14))};
input double InpRsiThreshold   = {float(p.get('rsi_th', p.get('rsi_threshold', 50)))};
input double InpRsiLong        = {float(p.get('rsi_long', 52.0))};
input double InpRsiShort       = {float(p.get('rsi_short', 48.0))};
input double InpAdxMin         = {float(p.get('adx_th', p.get('adx_min', 20.0)))};
input int    InpAdxRise        = {int(p.get('adx_rise', 3))};
input int    InpVolumeMa       = {int(p.get('volume_ma', 20))};
input int    InpAtrPeriod      = {int(p.get('atr_period', 14))};
input double InpSlAtr          = {float(p.get('atr_sl', 2.0))};
input double InpTpAtr          = {float(p.get('atr_tp', 4.0))};
input bool   InpAllowShort     = {'true' if p.get('allow_short', False) else 'false'};
input double InpRiskPercent    = {ctx.risk_pct * 100:.2f};
input ulong  InpMagic          = 2026081701;

## 4. Indicators
- EMA fast/slow/trend on H1 closed bar [1]
- Donchian, RSI, ADX, ATR, Volume MA
- Volume filter: {vol_note}

## 5. Entry logic
{logic}

Sinyal dihitung pada bar [1]. Order dikirim pada open bar [0]. Max 1 posisi.

## 6. Exit logic
- SL/TP from ATR multiples on entry bar
- SL priority if both hit same bar
- EOD close for open positions at series end

## 7. Risk & position sizing
- Risk per trade     : {rec_risk:.2%}
- Contract size      : {ctx.contract_size}
- Max positions      : 1
- Hard DD halt       : {hard_dd:.2%}

## 8. Order / filling notes
- Slippage           : {ctx.slippage:.4%}
- Spread             : {ctx.spread}
- Commission         : {ctx.commission_per_lot:.2f} USD / lot
- Fee                : {ctx.fee:.4%} notional per side

## 9. Backtest summary
- Period             : {ctx.data_start} → {ctx.data_end}
- In-sample          : ≤ {ctx.in_sample_end}
- Out-of-sample      : ≥ {ctx.oos_start}
- Initial capital    : {fmt_num(ctx.initial_equity)}
- Final capital IS   : {fmt_num(float(ctx.is_metrics.get('final_equity') or 0))}
- Final capital OOS  : {fmt_num(float(ctx.oos_metrics.get('final_equity') or 0))}
- Total return IS    : {fmt_pct(float(ctx.is_metrics.get('total_return') or 0))}
- Total return OOS   : {fmt_pct(float(ctx.oos_metrics.get('total_return') or 0))}
- Sharpe IS / OOS    : {float(ctx.is_metrics.get('sharpe') or 0):.3f} / {float(ctx.oos_metrics.get('sharpe') or 0):.3f}
- Max DD IS / OOS    : {fmt_pct(float(ctx.is_metrics.get('max_drawdown') or 0))} / {fmt_pct(float(ctx.oos_metrics.get('max_drawdown') or 0))}
- Trades IS / OOS    : {int(ctx.is_metrics.get('trades') or 0)} / {int(ctx.oos_metrics.get('trades') or 0)}

## 10. Risk assessment
- Parameter stable   : {'YES' if ctx.param_stable and ctx.perturb_stable else 'NO'}
- Cost stress 2x     : {'YES' if ctx.cost_pass else 'NO'}
- Median final (MC)  : {fmt_num(float(boot.get('median_final', float('nan'))))}
- P(loss) bootstrap  : {fmt_pct(float(boot.get('prob_loss', float('nan'))))}
- Median max DD (MC) : {fmt_pct(float(boot.get('median_max_dd', float('nan'))))}
- 95% worst DD (MC)  : {fmt_pct(float(boot.get('p95_worst_dd', float('nan'))))}

## 11. Decision gate
- In-sample          : {gate_label(g.in_sample)}
- Out-of-sample      : {gate_label(g.out_of_sample)}
- Walk-forward       : {gate_label(g.walk_forward)}
- Parameter stability: {gate_label(g.parameter_stability)}
- Cost stress        : {gate_label(g.cost_stress)}
- Monte Carlo        : {gate_label(g.monte_carlo)}
- FINAL STATUS       : {g.status}
- Implement to MQL5  : {implement}

## 12. MQL5 checklist
- [ ] Copy input parameters exactly
- [ ] Indicators on closed bar [1]
- [ ] Next-bar entry
- [ ] SL/TP in price from ATR
- [ ] One position per magic
- [ ] Risk % lot sizing
- [ ] Spread filter
- [ ] Strategy Tester validation
- [ ] Paper test before live
"""


def export_mql5_spec(text: str, status: str, export_dir: Path, symbol: str, timeframe: str, strategy_name: str) -> tuple[Path, Path]:
    export_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    prefix = "" if status in {"ROBUST", "ACCEPTABLE"} else "REJECTED_"
    tf = timeframe.replace(" ", "")
    stem = f"{prefix}{symbol}_{tf}_{strategy_name}_{stamp}"
    md_path = export_dir / f"{stem}.md"
    txt_path = export_dir / f"{stem}.txt"
    md_path.write_text(text, encoding="utf-8")
    txt_path.write_text(text, encoding="utf-8")
    return md_path, txt_path
