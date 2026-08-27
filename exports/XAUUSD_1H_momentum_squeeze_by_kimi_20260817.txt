# MQL5 Strategy Spec

## 1. Identity
- Strategy name     : momentum_squeeze_by_kimi
- Version           : 1.0.0
- Status            : ACCEPTABLE
- Generated at      : 2026-08-17 22:03
- Source notebook   : XAUUSD_Momentum_Pipeline.ipynb
- Plugin function   : momentum_squeeze_by_kimi

## 2. Market & execution
- Symbol            : XAUUSD
- Timeframe         : PERIOD_H1
- Chart price       : Close of completed candle
- Entry timing      : next candle open after signal (no look-ahead)
- Magic number      : 2026081701
- Comment           : ATB_momentum_squeeze_by_kimi

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
Momentum Squeeze Breakout (by Kimi).
1. Regime       : Close vs EMA200 + EMA_fast vs EMA_slow (arah tren).
2. Volatility   : ADX > adx_th AND ADX rising (adx_14 > adx_14.shift(adx_rise)).
3. Compression  : Donchian width / ATR < rolling median 100 (squeeze).
4. Trigger      : Close menembus Donchian High/Low setelah squeeze (shift 1).
5. Momentum     : RSI > rsi_long (52) Long / RSI < rsi_short (48) Short.
6. Exit         : SL = 2.0 * ATR, TP = 4.0 * ATR.
Execution       : next bar open, sinyal pada candle yang sudah close.

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
- Max drawdown halt    : 20.76%

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
- Final capital IS     : 8,561.54
- Final capital OOS    : 12,533.20
- Total return IS      : -14.38%
- Total return OOS     : 25.33%
- CAGR IS / OOS        : -1.04% / 11.82%
- Sharpe IS / OOS      : -0.026 / 0.868
- Sortino OOS          : 44.544
- Max drawdown IS/OOS  : -53.17% / -11.54%
- Win rate OOS         : 40.62%
- Profit factor OOS    : 1.303
- Trades IS / OOS      : 980 / 128
- Average win / loss   : 209.38 / -109.93
- Longest losing streak: 8
- Volume filter        : DISABLED (volume data dead / unused)

## 10. Risk assessment
- Parameter stable     : NO
- Cost stress 2x fee   : YES
- Monte Carlo sims     : 10000
- Median final equity  : 12,521.96
- 5th percentile equity: 9,603.13
- Probability of loss  : 7.65%
- Median max DD        : -10.20%
- 95% worst DD         : -20.76%
- Probability DD > 30% : 0.61%
- Recommended live risk: 1.00% per trade
- Hard stop live DD    : 20.76%

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
