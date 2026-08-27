# Pipeline Pengembangan Strategy Trading

Panduan kerja untuk project **AlgoTradeBacktest**: membangun strategy trading **rules-based / momentum** di Google Colab (atau notebook lokal). Alur ini memisahkan **data, indikator, signal, backtest, validasi, dan robustness test**.

Jangan langsung `strategy → backtest → Monte Carlo`.

---

## Lingkup project

Project ini **bukan** sistem prediksi harga berbasis machine learning.

Yang dikerjakan:

- logika trade eksplisit (`if / and / or`)
- momentum dan trend following (EMA, RSI, ADX, breakout, volume)
- entry, exit, stop loss, take profit
- backtest, walk-forward, stress test, Monte Carlo
- export spesifikasi bot (`.md` / `.txt`) untuk implementasi MQL5

Yang **tidak** dikerjakan:

- supervised learning (XGBoost, CatBoost, Random Forest, neural net)
- label / target prediksi (`y_pred`, `fit()`, `predict()`)
- feature selection untuk model ML
- walk-forward sebagai training model

Istilah *in-sample* / *out-of-sample* / *walk-forward* di dokumen ini berarti **uji kestabilan aturan dan parameter**, bukan training model.

```text
BUKAN:
  data → fit model → predict → trade

YA:
  data → indikator → aturan momentum → signal → backtest → validasi
```

---

## Daftar Isi

1. [Lingkup project](#lingkup-project)
2. [Alur yang direkomendasikan](#alur-yang-direkomendasikan)
3. [Universe & timeframe](#1-tentukan-universe--timeframe)
4. [Historical data](#2-ambil-historical-data)
5. [Indikator teknikal](#3-buat-indikator-teknikal)
6. [Strategy plugin](#31-strategy-plugin-copot-pasang)
7. [Backtester](#4-buat-backtester)
8. [Pisahkan data](#5-pisahkan-data)
9. [Optimasi parameter](#6-optimasi-parameter)
10. [Metrics](#7-metrics-yang-harus-disimpan)
11. [Robustness test](#8-robustness-test)
12. [Stress test](#9-stress-test)
13. [Monte Carlo](#10-baru-monte-carlo)
14. [Output Monte Carlo](#11-output-monte-carlo)
15. [Varian Monte Carlo](#12-monte-carlo-yang-lebih-bagus)
16. [Struktur notebook](#13-struktur-notebook-colab)
17. [Final decision gate](#14-final-decision-gate)
18. [Export spec MQL5](#15-export-spec-untuk-mql5)
19. [Stack Python](#stack-python-yang-cocok)
20. [Prinsip utama](#yang-paling-penting)

---

## Alur yang direkomendasikan

```text
                    ┌─────────────────┐
                    │ Historical Data │
                    │ OHLCV / Volume  │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │ Data Cleaning   │
                    │ & Validation    │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │ Indikator       │
                    │ RSI / EMA / ATR │
                    │ Volume / ADX    │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │ Strategy Plugin │
                    │ def nama_...    │
                    │ auto-registry   │
                    └────────┬────────┘
                             ↓
              ┌──────────────┴──────────────┐
              ↓                             ↓
       ┌──────────────┐              ┌──────────────┐
       │ In-Sample    │              │ Out-of-Sample│
       │ Development  │              │ Validation   │
       └──────┬───────┘              └──────┬───────┘
              │                             │
              └──────────────┬──────────────┘
                             ↓
                    ┌─────────────────┐
                    │ Walk Forward    │
                    │ Validation      │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │ Realistic Costs │
                    │ Fee + Slippage  │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │ Robustness Test │
                    │ Parameter       │
                    │ Sensitivity     │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │ Monte Carlo     │
                    │ Simulation      │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │ Export Spec     │
                    │ .md / .txt      │
                    │ acuan bot MQL5  │
                    └─────────────────┘
```

---

## 1. Tentukan universe & timeframe

Contoh instrumen:

- BTC/USDT
- ETH/USDT
- saham Indonesia
- forex
- XAU/USD

Timeframe: `15m` / `1h` / `4h` / `1D`.

Jangan mencampur terlalu banyak instrumen pada tahap awal.

Untuk project ini, mulai dari satu instrumen. Data yang sudah ada: `XAUUSD`.

Contoh konfigurasi awal:

```text
Asset       : XAUUSD
Timeframe   : 1H  (resample dari M1 jika perlu)
Period      : 2009–2026
Initial Cap : $10,000
Fee         : sesuai broker
Slippage    : sesuai volatilitas emas
Style       : momentum / trend following
Mode        : rules-based, tanpa ML
```

---

## 2. Ambil historical data

Di Colab, simpan data mentah terpisah:

```text
/raw_data
    btcusdt_1h.csv
```

Kemudian validasi:

- missing candle
- duplicate timestamp
- timezone
- OHLC invalid
- volume
- gap harga

Data yang buruk bisa menghasilkan strategy yang terlihat bagus padahal palsu.

---

## 3. Buat indikator teknikal

Ini **bukan feature engineering untuk ML**. Indikator hanya bahan baku aturan momentum.

Contoh indikator yang relevan:

```text
Price / Momentum
 ├── EMA 20
 ├── EMA 50
 ├── EMA 200
 ├── RSI 14
 ├── ATR 14
 ├── ADX
 ├── Volume MA
 └── Volatility
```

Jangan langsung mengoptimasi 30 indikator. Mulai dari sedikit aturan yang bisa dibaca manusia.

Engine indikator **tidak boleh** berisi aturan entry/exit, dan **tidak boleh** menghasilkan label prediksi. Indikator dihitung sekali, lalu dipakai semua strategy plugin.

---

## 3.1 Strategy plugin (copot-pasang)

Strategy adalah **aturan momentum yang bisa dibaca manusia**, bukan model prediksi. Harus **copot-pasang**. Backtester, walk-forward, stress test, dan Monte Carlo **tidak diubah** saat strategy baru ditambahkan.

Cara pakai:

1. Tulis `def nama_strategy(...)` dengan kontrak di bawah.
2. Pasang decorator `@register_strategy`.
3. Function langsung masuk registry dan bisa dipilih dari config.

Tidak perlu menyentuh cell backtest.

### Kontrak wajib

Setiap strategy menerima dataframe OHLCV + indikator, mengembalikan sinyal standar:

```text
Input
  df      : OHLCV + indikator (EMA, RSI, ATR, Volume, ...)
  params  : dict parameter aturan (bukan hyperparameter model ML)

Output (kolom wajib)
  signal  :  1 = long, -1 = short, 0 = flat
  sl_atr  :  jarak stop loss dalam ATR
  tp_atr  :  jarak take profit dalam ATR
```

Exit default:

```text
SL = sl_atr × ATR
TP = tp_atr × ATR
```

Kalau suatu strategy ingin exit sendiri (misalnya trailing atau opposite signal), boleh menambah kolom opsional `exit_signal`. Backtester tetap membaca format yang sama.

Setiap plugin juga wajib punya deskripsi aturan dalam teks (docstring atau `logic_spec`). Teks itu yang nanti diekspor ke file acuan MQL5.

### Registry otomatis

Satu cell di notebook (atau file `strategy_registry.py`):

```python
STRATEGY_REGISTRY = {}


def register_strategy(fn):
    """Decorator: def nama_strategy langsung terbaca."""
    STRATEGY_REGISTRY[fn.__name__] = fn
    return fn


def list_strategies():
    return sorted(STRATEGY_REGISTRY.keys())


def get_strategy(name):
    if name not in STRATEGY_REGISTRY:
        available = ", ".join(list_strategies()) or "(kosong)"
        raise KeyError(f"Strategy '{name}' tidak ditemukan. Tersedia: {available}")
    return STRATEGY_REGISTRY[name]
```

### Contoh strategy pertama

Ini strategy default. Copot kapan saja; ganti dengan `def` baru.

```python
@register_strategy
def ema_rsi_volume(df, params=None):
    p = params or {}
    ema_fast = p.get("ema_fast", 20)
    ema_slow = p.get("ema_slow", 50)
    rsi_th = p.get("rsi_threshold", 50)
    vol_ma = p.get("volume_ma", 20)

    long_cond = (
        (df[f"ema_{ema_fast}"] > df[f"ema_{ema_slow}"])
        & (df["rsi_14"] > rsi_th)
        & (df["volume"] > df[f"volume_ma_{vol_ma}"])
    )

    out = df.copy()
    out["signal"] = 0
    out.loc[long_cond, "signal"] = 1
    out["sl_atr"] = p.get("atr_sl", 1.5)
    out["tp_atr"] = p.get("atr_tp", 3.0)
    return out
```

Aturan bisnisnya:

```text
LONG jika:

EMA20 > EMA50
AND
RSI > 50
AND
Volume > Volume_MA20

Exit:

SL = 1.5 ATR
TP = 3 ATR
```

### Menambah strategy baru

Cukup tulis function baru. Tidak perlu edit backtester.

```python
@register_strategy
def breakout_atr(df, params=None):
    p = params or {}
    lookback = p.get("lookback", 20)
    out = df.copy()
    out["signal"] = 0
    out.loc[df["close"] > df["high"].rolling(lookback).max().shift(1), "signal"] = 1
    out["sl_atr"] = p.get("atr_sl", 1.5)
    out["tp_atr"] = p.get("atr_tp", 3.0)
    return out
```

Setelah cell dijalankan:

```text
list_strategies()
→ ['breakout_atr', 'ema_rsi_volume']
```

### Memilih strategy dari config

```python
ACTIVE_STRATEGY = "ema_rsi_volume"

PARAMS = {
    "ema_fast": 20,
    "ema_slow": 50,
    "rsi_threshold": 50,
    "atr_sl": 1.5,
    "atr_tp": 3.0,
}

strategy_fn = get_strategy(ACTIVE_STRATEGY)
signals = strategy_fn(df_indicators, PARAMS)
```

Ganti strategy = ganti string `ACTIVE_STRATEGY`. Parameter sweep, walk-forward, dan Monte Carlo memakai `strategy_fn` yang sama.

### Menjalankan semua strategy yang terdaftar

Berguna untuk banding cepat, tanpa mengubah pipeline:

```python
for name, fn in STRATEGY_REGISTRY.items():
    signals = fn(df_indicators, PARAMS)
    result = run_backtest(signals)
    print(name, result["sharpe"], result["max_drawdown"])
```

### Aturan isolasi

```text
Indikator        →  hanya EMA / RSI / ATR / ADX / volume
Strategy plugin  →  hanya aturan momentum + SL/TP
Backtester       →  hanya eksekusi + biaya + PnL
```

Strategy **tidak boleh**:

- download data
- menghitung fee / slippage
- menghitung Sharpe / drawdown
- mengubah split in-sample / out-of-sample
- `fit()` / `predict()` / training model
- menghasilkan probabilitas atau score ML

Setiap `def nama_strategy` harus bisa dijelaskan dalam bahasa manusia, misalnya: *"long jika EMA cepat di atas EMA lambat dan RSI di atas 50."*

Kalau logic data, biaya, atau model ML masuk ke dalam `def nama_strategy`, plugin tidak lagi copot-pasang.

### Opsi folder (nanti, jika notebook pecah jadi file)

```text
/strategies
    ema_rsi_volume.py
    breakout_atr.py
    adx_trend.py
```

Setiap file berisi satu `@register_strategy`. Loader mengimpor semua `.py` di folder itu, lalu registry terisi otomatis. Pola decorator tetap sama.

---

## 4. Buat backtester

Backtester **tidak mengenal nama strategy**. Ia hanya menerima output plugin (`signal`, `sl_atr`, `tp_atr`).

```python
strategy_fn = get_strategy(ACTIVE_STRATEGY)
signals = strategy_fn(df_indicators, PARAMS)
result = run_backtest(signals, fee=FEE, slippage=SLIPPAGE)
```

Backtester harus memperhitungkan kondisi nyata:

```text
Signal
   ↓
Next candle execution
   ↓
Entry price
   ↓
Position sizing
   ↓
Fee
   ↓
Slippage
   ↓
Stop Loss / Take Profit
   ↓
Exit
   ↓
PnL
```

Jangan menggunakan harga candle yang sama untuk mengetahui signal dan melakukan entry jika itu menyebabkan **look-ahead bias**.

---

## 5. Pisahkan data

Split ini untuk **validasi aturan**, bukan training model.

Contoh split sederhana:

```text
2020 ───────────── 2024 │ 2025 ───── 2026
     IN-SAMPLE          │  OUT-OF-SAMPLE
   (kembangkan aturan)  │  (uji tanpa ubah aturan)
```

Atau:

```text
70% → development (tweak aturan & parameter)
30% → out-of-sample (jangan diutak-atik lagi)
```

Lebih bagus lagi menggunakan **walk-forward validation** untuk parameter aturan (EMA length, RSI threshold, ATR multiplier), bukan untuk `fit()` model.

```text
Develop: 2020 ─ 2022
Validate:      2023

Develop: 2021 ─ 2023
Validate:            2024

Develop: 2022 ─ 2024
Validate:                  2025

Develop: 2023 ─ 2025
Validate:                        2026
```

Walk-forward jauh lebih kuat daripada hanya satu kali in-sample / out-of-sample split.

---

## 6. Optimasi parameter

Ini **grid / sensitivity search pada aturan**, bukan hyperparameter tuning model ML.

Contoh parameter strategy:

```python
ema_fast = 20
ema_slow = 50
rsi_threshold = 50
atr_sl = 1.5
atr_tp = 3.0
```

Jangan mencari **parameter terbaik absolut**. Cari **area parameter yang stabil**.

Contoh hasil sehat:

```text
EMA Fast

10   → Sharpe 0.91
15   → Sharpe 1.08
20   → Sharpe 1.21
25   → Sharpe 1.18
30   → Sharpe 1.15
35   → Sharpe 0.52
```

Ini lebih sehat daripada:

```text
EMA = 22 → Sharpe 1.87
```

Angka 22 mungkin hanya hasil overfitting.

---

## 7. Metrics yang harus disimpan

Jangan hanya melihat profit. Minimal simpan:

```text
Total Return
CAGR
Sharpe Ratio
Sortino Ratio
Calmar Ratio
Maximum Drawdown
Win Rate
Profit Factor
Expectancy
Average Win
Average Loss
Number of Trades
Average Trade
Longest Losing Streak
Recovery Factor
```

Contoh hasil:

```text
Initial Capital     $10,000
Final Capital       $24,830
Total Return        148.3%
CAGR                18.4%

Sharpe              1.42
Sortino             2.01
Max Drawdown        -17.8%

Win Rate            47.2%
Profit Factor       1.63
Trades              1,284
```

Win rate 47% tidak otomatis buruk. Kalau average winner jauh lebih besar daripada average loser, strategy tetap bisa profitable.

---

## 8. Robustness test

Sebelum Monte Carlo, lakukan **parameter perturbation**.

Misalnya strategy `EMA 20 / EMA 50`, uji:

```text
EMA 18 / EMA 48
EMA 19 / EMA 49
EMA 20 / EMA 50
EMA 21 / EMA 51
EMA 22 / EMA 52
```

Kalau semuanya masih profitable → bagus.

Kalau hasilnya seperti ini:

```text
20/50 → +180%
19/49 → -12%
21/51 → -30%
```

Red flag: **overfitting**.

---

## 9. Stress test

Uji strategy dengan kondisi lebih buruk:

```text
Fee × 1
Fee × 2
Fee × 3

Slippage × 1
Slippage × 2
Slippage × 3
```

Contoh yang bagus:

```text
Normal:
Return +120%

Fee 2×:
Return +102%

Fee 3×:
Return +87%
```

Contoh yang buruk:

```text
Normal:
+120%

Fee 2×:
-5%
```

Artinya strategy sangat sensitif terhadap transaction cost.

---

## 10. Baru Monte Carlo

Jangan hanya: *"acak harga kemudian lihat profit."*

Monte Carlo lebih berguna jika dilakukan terhadap **hasil trading strategy**.

Misalnya strategy menghasilkan:

```text
+2.1%
-1.2%
+3.4%
-0.8%
+1.7%
...
```

Misalnya ada 1.000 trade. Kemudian randomisasi urutan trade tersebut:

```text
Original:

W W L W L L W W W L ...

Simulation 1:
L W W L W W L ...

Simulation 2:
W L L W W L W ...

Simulation 3:
L W W W L L W ...
```

Lakukan `10,000` atau `50,000` simulasi.

---

## 11. Output Monte Carlo

Yang dicari bukan cuma average return.

Contoh output:

```text
Monte Carlo
Simulations: 50,000

Median Final Equity       $31,200
5th Percentile             $17,800
25th Percentile            $24,100
50th Percentile            $31,200
75th Percentile            $40,500
95th Percentile            $57,800

Median Max Drawdown        -21.4%
95% Worst Drawdown         -38.7%

Probability of Loss         3.2%
Probability DD > 30%       11.7%
```

Ini jauh lebih berguna, karena kita bisa mengatakan:

> Berdasarkan distribusi trade historis, strategy memiliki sekitar 3.2% kemungkinan berakhir rugi dalam simulasi tersebut.

Bukan berarti masa depan pasti demikian. Monte Carlo **bukan prediksi masa depan**, melainkan robustness / risk analysis berdasarkan asumsi tertentu.

---

## 12. Monte Carlo yang lebih bagus

Gunakan beberapa jenis Monte Carlo, bukan satu.

### A. Shuffle trades

```text
W L W W L ...
```

Urutannya diacak.

Tujuan: mengetahui kemungkinan drawdown berdasarkan **sequence risk**.

### B. Bootstrap trades

Trade diambil secara random **dengan replacement**.

Tujuan: melihat distribusi kemungkinan equity curve.

### C. Perturbasi return

```text
Original return = +2.5%

Monte Carlo:
+2.31%
+2.74%
+1.98%
+2.83%
...
```

Tujuan: menguji sensitivitas terhadap noise.

### D. Slippage Monte Carlo

Setiap trade diberi slippage random:

```text
0.01%
0.03%
0.07%
0.12%
...
```

Ini lebih realistis untuk market yang volatile.

---

## 13. Struktur notebook Colab

Opsi A — beberapa notebook terpisah:

```text
00_config.ipynb
│
├── 01_import
│
├── 02_download_data
│
├── 03_data_validation
│
├── 04_indicators          # EMA / RSI / ATR / ADX, bukan ML features
│
├── 05_strategy_registry   # @register_strategy, auto-discover
│
├── 06_backtest
│
├── 07_parameter_optimization
│
├── 08_walk_forward
│
├── 09_transaction_cost_stress
│
├── 10_parameter_sensitivity
│
├── 11_monte_carlo
│
├── 12_final_report
│
└── 13_export_mql5_spec.md / .txt
```

Opsi B — satu Colab (lebih praktis):

```text
# 1. Configuration
# 2. Data
# 3. Indicators (teknikal, bukan ML features)
# 4. Strategy plugin (aturan momentum, @register_strategy)
# 5. Backtest
# 6. Optimization
# 7. Walk Forward
# 8. Robustness
# 9. Monte Carlo
# 10. Strategy preview (post Monte Carlo)
# 11. Final Evaluation + export spec MQL5 (.md / .txt)
```

---

## 14. Final decision gate

Buat **strategy scorecard**:

```text
                    PASS?
                     │
          ┌──────────┴──────────┐
          ↓                     ↓
     In Sample              Out Sample
     Sharpe > 1             Sharpe > 0.8
          │                     │
          └──────────┬──────────┘
                     ↓
              Walk Forward
                     │
                     ↓
              Parameter Stable?
                     │
                     ↓
             Cost Stress Test
                     │
                     ↓
              Monte Carlo
                     │
          ┌──────────┴──────────┐
          ↓                     ↓
       Robust                Fragile
          │                     │
          ↓                     ↓
      PAPER TEST             REJECT
```

Status akhir:

```text
❌ FAIL
⚠️ FRAGILE
🟡 ACCEPTABLE
🟢 ROBUST
```

Hanya status `🟡 ACCEPTABLE` atau `🟢 ROBUST` yang boleh diekspor sebagai spesifikasi bot. Status `FAIL` / `FRAGILE` tetap disimpan sebagai log, tetapi ditandai **JANGAN IMPLEMENTASI KE MQL5**.

---

## 15. Export spec untuk MQL5

Output akhir backtest **bukan** hanya angka di notebook. Pipeline wajib menulis file acuan untuk membuat Expert Advisor di MetaTrader 5.

Format:

```text
/exports
    XAUUSD_H1_ema_rsi_volume_20260817.md
    XAUUSD_H1_ema_rsi_volume_20260817.txt
```

`.md` untuk dibaca manusia. `.txt` untuk salin cepat ke komentar / requirement EA. Isi keduanya **identik secara substansi**.

File ini harus bisa dibaca developer MQL5 **tanpa membuka notebook**. Semua aturan ditulis sebagai kondisi boolean, bukan sebagai model.

### Isi wajib file export

```text
1. Identity
2. Market & execution
3. Input parameters (mapping ke input MQL5)
4. Indicators
5. Entry logic
6. Exit logic
7. Risk & position sizing
8. Order / filling notes
9. Backtest summary
10. Risk assessment
11. Decision gate
12. MQL5 implementation checklist
```

### Template `.md`

```markdown
# MQL5 Strategy Spec

## 1. Identity
- Strategy name     : ema_rsi_volume
- Version           : 1.0.0
- Status            : ROBUST / ACCEPTABLE / FRAGILE / FAIL
- Generated at      : 2026-08-17 18:52 UTC+7
- Source notebook   : XAUUSD_Momentum_Pipeline.ipynb
- Plugin function   : ema_rsi_volume

## 2. Market & execution
- Symbol            : XAUUSD
- Timeframe         : PERIOD_H1
- Chart price       : Close of completed candle
- Entry timing      : next candle open after signal (no look-ahead)
- Magic number      : 2026081701
- Comment           : ATB_ema_rsi_volume

## 3. Input parameters (MQL5 `input`)
input int    InpEmaFast        = 20;
input int    InpEmaSlow        = 50;
input int    InpRsiPeriod      = 14;
input double InpRsiThreshold   = 50.0;
input int    InpVolumeMa       = 20;
input int    InpAtrPeriod      = 14;
input double InpSlAtr          = 1.5;
input double InpTpAtr          = 3.0;
input double InpRiskPercent    = 1.0;
input ulong  InpMagic          = 2026081701;

## 4. Indicators
- EMA fast   : iMA(_Symbol, PERIOD_H1, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE)
- EMA slow   : iMA(_Symbol, PERIOD_H1, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE)
- RSI        : iRSI(_Symbol, PERIOD_H1, InpRsiPeriod, PRICE_CLOSE)
- ATR        : iATR(_Symbol, PERIOD_H1, InpAtrPeriod)
- Volume MA  : SMA(tick_volume atau real_volume, InpVolumeMa)

Pakai nilai bar [1] (candle yang sudah close). Jangan pakai bar [0] untuk keputusan entry.

## 5. Entry logic
LONG jika SEMUA benar pada bar [1]:
  EMA_fast[1] > EMA_slow[1]
  AND RSI[1] > InpRsiThreshold
  AND Volume[1] > VolumeMA[1]
  AND tidak ada posisi terbuka dengan magic yang sama

SHORT: tidak dipakai pada versi ini.

Jangan entry di bar yang sama saat sinyal baru terbentuk jika backtest memakai next-bar execution.

## 6. Exit logic
- Stop Loss   : entry_price - InpSlAtr * ATR[1]   (long)
- Take Profit : entry_price + InpTpAtr * ATR[1]   (long)
- SL/TP dipasang saat OrderSend / PositionOpen
- Tidak ada trailing pada versi ini
- Exit tambahan: tidak ada (hanya SL/TP)

## 7. Risk & position sizing
- Risiko per trade     : InpRiskPercent % dari equity
- Lot                  : risk_money / (SL_distance_in_price * tick_value)
- Max positions        : 1
- Max daily loss       : (isi dari risk assessment, contoh 3%)
- Max drawdown halt    : (contoh 20%)

## 8. Order / filling notes
- Filling              : SYMBOL_FILLING_FOK atau IOC sesuai broker
- Deviation / slippage : sesuai stress test
- Spread filter        : tolak entry jika spread > N points
- Trading hours        : (isi jika ada; default 24h XAU)

## 9. Backtest summary
- Period               : 2009-01-01 → 2026-08-01
- In-sample            : ...
- Out-of-sample        : ...
- Initial capital      : 10000
- Final capital        : ...
- Total return         : ...
- CAGR                 : ...
- Sharpe               : ...
- Sortino              : ...
- Max drawdown         : ...
- Win rate             : ...
- Profit factor        : ...
- Trades               : ...
- Average win / loss   : ...
- Longest losing streak: ...

## 10. Risk assessment
- Parameter stable     : YES / NO
- Cost stress 2x fee   : masih profit YES / NO
- Cost stress 3x fee   : masih profit YES / NO
- Monte Carlo sims     : 50000
- Median final equity  : ...
- 5th percentile equity: ...
- Probability of loss  : ...
- Median max DD        : ...
- 95% worst DD         : ...
- Probability DD > 30% : ...
- Recommended live risk: ... % per trade
- Hard stop live DD    : ... %

## 11. Decision gate
- In-sample            : PASS / FAIL
- Out-of-sample        : PASS / FAIL
- Walk-forward         : PASS / FAIL
- Parameter stability  : PASS / FAIL
- Cost stress          : PASS / FAIL
- Monte Carlo          : PASS / FAIL
- FINAL STATUS         : ROBUST
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
- [ ] Strategy Tester: every tick / 1H OHLC sesuai catatan
- [ ] Paper test sebelum live
```

### Bagian yang paling penting untuk bot

Developer MQL5 hanya wajib meniru **bagian 3–8**. Bagian 9–11 adalah bukti bahwa aturan itu lolos risk assessment, bukan logic runtime.

```text
Python backtest                  MQL5 EA
─────────────────────            ─────────────────────
params dict               →      input variables
indikator pandas          →      iMA / iRSI / iATR
if EMA20 > EMA50 ...      →      if(ema_fast[1] > ema_slow[1] ...)
sl_atr * ATR              →      sl = entry - sl_atr * atr[1]
next candle execution     →      sinyal bar[1], order di bar[0] open
risk assessment           →      batas lot, max DD, halt trading
```

Jangan menerjemahkan Python ke MQL5 secara literal (tidak ada pandas di EA). Terjemahkan **aturan**, bukan kode dataframe.

### Generator di notebook

Satu function menulis kedua file:

```python
def export_mql5_spec(
    strategy_name: str,
    params: dict,
    logic_text: str,
    metrics: dict,
    risk: dict,
    status: str,
    out_dir: str = "exports",
) -> tuple[str, str]:
    """Tulis acuan bot MQL5 (.md dan .txt)."""
    ...
```

Setiap plugin strategy sebaiknya punya docstring atau `logic_spec()` agar teks entry/exit tidak ditulis manual:

```python
@register_strategy
def ema_rsi_volume(df, params=None):
    """
    LONG jika EMA_fast > EMA_slow AND RSI > threshold AND Volume > Volume_MA.
    Exit: SL = sl_atr * ATR, TP = tp_atr * ATR.
    Execution: next bar open.
    """
    ...
```

### Nama file

```text
{SYMBOL}_{TF}_{strategy}_{YYYYMMDD}.{md|txt}
```

Contoh: `XAUUSD_H1_ema_rsi_volume_20260817.md`

Jika status bukan `ACCEPTABLE` atau `ROBUST`, prefix `REJECTED_`:

```text
REJECTED_XAUUSD_H1_ema_rsi_volume_20260817.md
```

---

## Stack Python yang cocok

Untuk Colab:

```text
Python
├── pandas
├── numpy
├── matplotlib
├── seaborn
├── numba
└── vectorbt   (opsional, untuk parameter sweep)
```

Tidak memakai `scikit-learn`, XGBoost, CatBoost, TensorFlow, atau library ML lain.

Kalau ingin eksperimen aturan momentum dengan cepat, `vectorbt` menarik karena vectorized backtesting dan parameter sweep-nya cocok untuk Colab.

Kalau ingin backtester yang lebih custom dan realistis:

```text
pandas + numpy + numba
```

lebih fleksibel. Cukup untuk logika `if EMA20 > EMA50` plus eksekusi SL/TP.

---

## Yang paling penting

Jangan membuat alur:

```text
Cari parameter terbaik
        ↓
Backtest
        ↓
Bagus
        ↓
Monte Carlo
        ↓
Trading
```

Tetapi:

```text
Hipotesis momentum
(contoh: harga emas mengikuti trend EMA)
    ↓
Data
    ↓
Indikator
    ↓
Aturan trade (plugin)
    ↓
Backtest
    ↓
Out-of-Sample
    ↓
Walk Forward
    ↓
Cost / Slippage Stress
    ↓
Parameter Stability
    ↓
Monte Carlo
    ↓
Risk Assessment
    ↓
Export spec MQL5 (.md / .txt)
    ↓
Paper Trading (MT5 Strategy Tester / demo)
    ↓
Live Trading
```

**Monte Carlo sebaiknya menjadi salah satu filter terakhir untuk robustness, bukan alat untuk membuat strategy terlihat bagus.**
