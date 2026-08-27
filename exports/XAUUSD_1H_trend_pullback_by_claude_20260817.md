# MQL5 Strategy Spec

## 1. Identity
- Strategy name     : trend_pullback_by_claude
- Version           : 1.0.0
- Status            : ACCEPTABLE
- Generated at      : 2026-08-17 22:03
- Source notebook   : XAUUSD_Momentum_Pipeline.ipynb
- Plugin function   : trend_pullback_by_claude

## 2. Market & execution
- Symbol            : XAUUSD
- Timeframe         : PERIOD_H1
- Chart price       : Close of completed candle
- Entry timing      : next candle open after signal (no look-ahead)
- Magic number      : 2026081701
- Comment           : ATB_trend_pullback_by_claude

## 3. Input parameters (MQL5 `input`)
input int    InpEmaFast        = 20;
input int    InpEmaSlow        = 50;
input int    InpEmaTrend       = 200;
input int    InpLookback       = 24;
input int    InpRsiPeriod      = 14;
input double InpRsiThreshold   = 50.0;
input double InpRsiLong        = 52.0;
input double InpRsiShort       = 48.0;
input double InpAdxMin         = 20.0;
input int    InpAdxRise        = 3;
input int    InpVolumeMa       = 20;
input int    InpAtrPeriod      = 14;
input double InpSlAtr          = 2.0;
input double InpTpAtr          = 4.0;
input bool   InpAllowShort     = true;
input double InpRiskPercent    = 1.00;
input ulong  InpMagic          = 2026081701;

## 4. Indicators
- EMA fast   : iMA(_Symbol, PERIOD_H1, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE)
- EMA slow   : iMA(_Symbol, PERIOD_H1, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE)
- EMA trend  : iMA(_Symbol, PERIOD_H1, InpEmaTrend, 0, MODE_EMA, PRICE_CLOSE)
- Donchian   : Highest(High, InpLookback) / Lowest(Low, InpLookback) on bar [1]
- RSI        : iRSI(_Symbol, PERIOD_H1, InpRsiPeriod, PRICE_CLOSE)
- ADX        : iADX(_Symbol, PERIOD_H1, 14)  (filter ADX > InpAdxMin)
- ATR        : iATR(_Symbol, PERIOD_H1, InpAtrPeriod)
- Volume MA  : SMA(tick_volume atau real_volume, InpVolumeMa)  [DISABLED (volume data dead / unused)]

Pakai nilai bar [1] (candle yang sudah close). Jangan pakai bar [0] untuk keputusan entry.

## 5. Entry logic
Plugin docstring (source of truth for EA rules):
Trend-pullback momentum (by Claude).
Regime : Close > EMA200 AND EMA200 naik (vs 5 bar lalu) -> hanya ikut uptrend besar.
Kualitas: ADX > adx_min (trend nyata, bukan ranging) AND EMA_fast > EMA_slow.
Trigger : pullback -- Low menyentuh/di bawah EMA_fast dalam pull_bars bar terakhir,
          lalu Close kembali di atas EMA_fast dan RSI > 50 (momentum resume).
SHORT tidak dipakai.
Exit    : SL = sl_atr * ATR (2.0), TP = tp_atr * ATR (4.0) -> minimal 2R.
Execution: next bar open, sinyal pada candle yang sudah close.

Sinyal dihitung pada bar [1] (candle close). Order dikirim pada open bar [0] (next-bar execution).
Max 1 posisi. Jangan entry jika sudah ada posisi dengan magic yang sama.

## 6. Exit logic
- Long  SL : entry_price - InpSlAtr * ATR[1]
- Long  TP : entry_price + InpTpAtr * ATR[1]
- Short SL : entry_price + InpSlAtr * ATR[1]
- Short TP : entry_price - InpTpAtr * ATR[1]
- SL/TP dipasang saat OrderSend / PositionOpen
- Tidak ada trailing pada versi ini
- Exit tambahan: tidak ada (hanya SL/TP)
- Jika SL dan TP tersentuh di bar yang sama: anggap SL (konservatif, sama dengan backtest)

## 7. Risk & position sizing
- Risiko per trade     : InpRiskPercent % dari equity
- Lot                  : risk_money / (SL_distance_in_price * contract_size)
- Contract size        : 100
- Max positions        : 1
- Max daily loss       : n/a (set di EA jika perlu)
- Max drawdown halt    : 21.17%

## 8. Order / filling notes
- Filling              : SYMBOL_FILLING_FOK atau IOC sesuai broker
- Deviation / slippage : 0.0100% plus spread 0.25 (backtest)
- Spread filter        : tolak entry jika spread > ATR[1] * 0.15
- Trading hours        : 24h XAU (broker server)
- Commission           : 7.00 USD round-turn per 1.00 lot
- Fee %                : 0.0000% notional per side

## 9. Backtest summary
- Period               : 2009-03-15 17:00:00 → 2026-01-09 16:00:00
- In-sample            : ≤ 2023-12-31
- Out-of-sample        : ≥ 2024-01-01
- Initial capital      : 10,000.00
- Final capital IS     : 8,699.64
- Final capital OOS    : 17,654.05
- Total return IS      : -13.00%
- Total return OOS     : 76.54%
- CAGR IS / OOS        : -0.94% / 32.49%
- Sharpe IS / OOS      : -0.005 / 1.570
- Sortino OOS          : 2.929
- Max drawdown IS/OOS  : -49.11% / -7.37%
- Win rate OOS         : 44.79%
- Profit factor OOS    : 1.494
- Trades IS / OOS      : 1125 / 192
- Average win / loss   : 269.32 / -146.30
- Longest losing streak: 5
- Volume filter        : DISABLED (volume data dead / unused)

## 10. Risk assessment
- Parameter stable     : NO
- Cost stress 2x fee   : YES
- Monte Carlo sims     : 10000
- Median final equity  : 17,632.00
- 5th percentile equity: 12,865.47
- Probability of loss  : 0.29%
- Median max DD        : -10.98%
- 95% worst DD         : -21.17%
- Probability DD > 30% : 0.68%
- Recommended live risk: 1.00% per trade
- Hard stop live DD    : 21.17%

## 11. Decision gate
- In-sample            : FAIL
- Out-of-sample        : PASS
- Walk-forward         : PASS
- Parameter stability  : FAIL
- Cost stress          : PASS
- Monte Carlo          : PASS
- FINAL STATUS         : ACCEPTABLE
- Implement to MQL5    : YES

## 12. MQL5 checklist
- [ ] Copy input parameters exactly
- [ ] Indicators on closed bar [1]
- [ ] Next-bar entry
- [ ] SL/TP in price from ATR
- [ ] One position per magic
- [ ] Risk % lot sizing
- [ ] Spread filter
- [ ] Journal log setiap entry/exit (alasan aturan)
- [ ] Strategy Tester: every tick based on real ticks jika tersedia
- [ ] Paper test sebelum live
