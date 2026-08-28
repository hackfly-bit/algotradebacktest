# Rencana Konversi Notebook ke Higgs

Dokumen ini adalah sumber kebenaran implementasi aplikasi **Higgs**: backtester rules-based XAUUSD yang di-port dari notebook ke Django 6.1 + SQLite + Tailwind CSS v4.

Bahasa dokumen: Indonesia. Kode, identifier, URL, dan nama file: Inggris.

---

## 1. Tujuan

Mengubah [`XAUUSD_Momentum_Pipeline.ipynb`](../../XAUUSD_Momentum_Pipeline.ipynb) menjadi aplikasi web lokal yang:

1. Mengunggah dan memvalidasi data OHLCV.
2. Menghitung indikator teknikal sekali, dipakai semua strategy.
3. Menjalankan plugin strategy copot-pasang (`@register_strategy`).
4. Menjalankan backtest realistis (next-bar, biaya, SL/TP ATR).
5. Menyimpan run, trade, metrik, walk-forward, robustness, Monte Carlo.
6. Menampilkan dashboard modern lengkap (bukan Django admin mentah).
7. Mengekspor spesifikasi MQL5 (`.md` / `.txt`) setelah decision gate.

Bukan sistem prediksi harga. Tidak ada supervised learning.

---

## 2. Sumber kebenaran

| Artefak | Peran |
|---------|--------|
| [`XAUUSD_Momentum_Pipeline.ipynb`](../../XAUUSD_Momentum_Pipeline.ipynb) | Implementasi yang harus di-port (angka regresi) |
| [`STRATEGY_DEVELOPMENT_PIPELINE.md`](../../STRATEGY_DEVELOPMENT_PIPELINE.md) | Aturan domain, isolasi layer, template export |
| [`XAUUSD_2009_2026_M1.csv`](../../XAUUSD_2009_2026_M1.csv) | Dataset awal (~5,89 juta bar M1, 2009-03-15 s.d. 2026-01-09). **Tidak di-commit** (limit GitHub 100MB). Jika file tidak ada, kerjakan [Fase 2b](#fase-2b--bootstrap-dataset-jika-csv-merged-tidak-ada). |
| Folder [`exports/`](../../exports/) | Contoh spec MQL5 yang sudah dihasilkan notebook |

Notebook lama ML (`archive/BackTestXau_ML.ipynb`) **tidak** di-port.

---

## 3. Non-goals

- Machine learning (`fit`, `predict`, XGBoost, neural net, label target).
- Multi-tenant / SaaS publik.
- Live trading / broker API / MT5 bridge.
- PostgreSQL (fase ini: SQLite).
- SPA (React/Vue). UI = Django templates + HTMX.
- Menyimpan setiap bar M1 sebagai baris SQLite.

---

## 4. Stack yang dikunci

| Lapisan | Pilihan | Catatan |
|---------|---------|---------|
| Runtime | Python 3.12 / 3.13 / 3.14 | Django 6.1 resmi mendukung ketiganya |
| Web | Django 6.1 | Pin `Django>=6.1,<6.2` |
| DB | SQLite | `OPTIONS.timeout` >= 20; WAL jika perlu |
| Job | `django.tasks` | `@task` + worker; bukan django-q2 |
| Email | `MAILERS` | Settings 6.1; jangan `EMAIL_BACKEND` baru |
| CSS | Tailwind CSS v4 CLI | Scan `templates/` |
| Interaksi | HTMX | Progress job, tab partial |
| Chart | Chart.js | Equity, drawdown, histogram MC |
| Alpine.js | Minimal | Toggle sidebar / dark mode saja |
| OS/shell | Windows 11, cmd.exe | `setup.bat`; tanpa PowerShell/Bash di dokumen perintah |

### Settings Django 6.1 yang wajib

```python
# config/settings/base.py (konsep)
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.marketdata",
    "apps.strategies",
    "apps.backtests",
    "apps.reports",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {"timeout": 30},
    }
}

TASKS = {
    "default": {
        "BACKEND": "django.tasks.backends.database.DatabaseBackend",
    }
}

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    }
}
```

Worker: `py manage.py run_worker` (atau perintah ekuivalen 6.1) di terminal terpisah dari `runserver`. Job backtest **tidak** boleh dijalankan sinkron di request HTTP kecuali mode debug dengan dataset sangat kecil.

---

## 5. Arsitektur

```text
CSV OHLCV
    -> apps.marketdata (upload, validasi, metadata SQLite)
    -> cache H1 Parquet/CSV di media/data/
    -> engine.indicators (pandas, tanpa Django)
    -> engine.strategies.* (@register_strategy)
    -> engine.backtester (next-bar, biaya, SL/TP)
    -> engine.metrics / walk_forward / robustness / monte_carlo
    -> django.tasks worker
    -> SQLite (run, trade, metric, gate, export)
    -> templates HTMX + Chart.js
    -> engine.mql5_export
```

### Batas layer (wajib)

```text
engine/          tidak boleh import django
apps/*/models    tidak boleh berisi rumus indikator / loop backtest
strategy plugin  tidak boleh load CSV, hitung fee, hitung Sharpe, fit()
backtester       tidak boleh mengenal nama strategy; hanya signal/sl_atr/tp_atr
templates        tidak boleh berisi logika trading
```

---

## 6. Struktur folder target

```text
Higgs/
  AGENTS.md
  .cursor/rules/*.mdc
  .cursor/skills/add-strategy/SKILL.md
  .agents/skills/                 # Taste-Skill + Ponytail
  .codegraph/
  .codebase-memory/
  docs/CONVERSION_PLAN.md         # file ini
  docs/DESIGN.md
  manage.py
  requirements.txt
  requirements-dev.txt
  setup.bat
  .gitignore
  config/
    __init__.py
    settings/base.py
    settings/local.py
    urls.py
    asgi.py
    wsgi.py
  apps/
    core/                         # auth shell, dashboard home
    marketdata/                   # Dataset
    strategies/                   # listing registry (baca engine)
    backtests/                    # BacktestRun + tasks
    reports/                      # export files, compare
  engine/
    __init__.py
    data.py
    indicators.py
    registry.py
    backtester.py
    metrics.py
    walk_forward.py
    robustness.py
    monte_carlo.py
    decision_gate.py
    mql5_export.py
    strategies/
      __init__.py                 # auto-discover *.py
      ema_rsi_volume.py
      breakout_atr.py
      trend_pullback_by_claude.py
      trend_breakout_by_gemini.py
      momentum_squeeze_by_kimi.py
  templates/
    base.html
    partials/
    core/
    marketdata/
    strategies/
    backtests/
    reports/
  static/src/input.css
  static/dist/app.css
  media/uploads/
  media/cache/
  tests/
    test_engine_parity.py
    test_lookahead.py
    test_plugin_isolation.py
    test_gate.py
  data/                           # symlink atau copy dataset sample
```

Root aplikasi Cursor untuk Higgs adalah folder `Higgs/`, bukan repo induk notebook.

---

## 7. Frontend: Taste-Skill + Ponytail

### 7.1 Taste-Skill (tampilan)

Install:

```text
npx skills add Leonxlnx/taste-skill
```

Skill default berorientasi landing page. Higgs adalah **product dashboard**. Setelah install:

1. Tulis [`docs/DESIGN.md`](DESIGN.md) sebagai token source of truth.
2. Patch puncak `SKILL.md` Taste: brief dashboard, `VISUAL_DENSITY` 8–9, `MOTION_INTENSITY` 2–3, `DESIGN_VARIANCE` 4–5.
3. Design system: Tailwind v4 + `dark:`. Jangan Fluent, Carbon, shadcn-React, Bootstrap.

Larangan visual (anti-slop):

- Ungu AI, mesh blob, three-equal-cards sebagai layout default.
- Fake dashboard dari `div` kosong (angka dummy yang berpura-pura live).
- Serif editorial untuk cockpit data.
- GSAP scroll-hijack. Motion = hover, focus, HTMX swap.

Empty state harus jujur: "Belum ada run" bukan grafik palsu.

### 7.2 Ponytail (cara membangun)

Install:

```text
npx skills add dietrichgebert/ponytail
```

- **Lengkap** = semua layar di seksi 9 ada.
- **Ponytail** = jangan SPA, jangan CSS framework kedua, jangan Chart.js + library chart lain, jangan service layer Django yang belum dipanggil, jangan fitur di luar notebook.
- Mode default `full`. Jangan memotong tab walk-forward / Monte Carlo / export "supaya simpel".

### 7.3 Verifikasi UI

Setiap halaman baru: desktop (>=1280) dan viewport sempit, light dan dark. Gunakan browser tools. Skeleton tanpa data memakai empty state, bukan lorem ipsum metrik.

---

## 8. Information architecture dan URL

Shell: `templates/base.html` — sidebar kiri, topbar (judul, dataset aktif, status job HTMX, toggle tema), main.

Login: Django auth, staff/superuser lokal. Semua halaman di bawah `login_required` kecuali `/accounts/login/`.

| URL | View | Fungsi |
|-----|------|--------|
| `/accounts/login/` | LoginView | Login |
| `/` | `core.views.overview` | KPI run terakhir, sparkline, antrian, dataset aktif |
| `/datasets/` | list+upload | CSV, hasil validasi, `volume_usable` |
| `/datasets/<id>/` | detail | ringkasan validasi M1/H1 |
| `/strategies/` | list | registry + docstring |
| `/strategies/<name>/` | detail | params default, logic_spec |
| `/runs/new/` | form | strategy satu / list / `*`, costs, IS/OOS, `MULTI_DEEP` |
| `/runs/` | list | filter status, strategy, gate |
| `/runs/<id>/` | detail | tab (lihat bawah) |
| `/runs/<id>/partials/<tab>/` | HTMX | isi tab |
| `/runs/<id>/status/` | HTMX | progress job |
| `/compare/` | compare | screening `*` |
| `/exports/` | list | file spec |
| `/exports/<id>/download/` | file | `.md` / `.txt` |
| `/settings/` | form | default fee, spread, slippage, risk, equity |

### Tab Run detail (`/runs/<id>/`)

1. Overview metrics (scorecard + KPI notebook).
2. Equity + drawdown (Chart.js).
3. Trades (tabel paginasi).
4. In-sample / out-of-sample.
5. Walk-forward (jika `MULTI_DEEP`).
6. Robustness (EMA ±2).
7. Cost stress (×1/×2/×3).
8. Monte Carlo (shuffle, bootstrap, perturb, slippage_mc).
9. Decision gate.
10. Export MQL5 (download + preview teks).

Screening `ACTIVE_STRATEGY = "*"` di notebook = form New run dengan `*` lalu Compare.

---

## 9. Model SQLite

OHLCV tidak dinormalisasi ke tabel bar. `Dataset` menunjuk path file.

### `apps.marketdata.models.Dataset`

- `symbol` CharField (default `XAUUSD`)
- `timeframe` CharField (default `1H`)
- `source_name` CharField
- `raw_path` FilePath / FileField (CSV M1)
- `cache_path` CharField (H1 parquet/csv)
- `rows_m1` IntegerField
- `rows_h1` IntegerField
- `start_ts` DateTimeField
- `end_ts` DateTimeField
- `validation` JSONField (output `validate_ohlcv`)
- `volume_usable` BooleanField
- `created_at`

### `apps.backtests.models.BacktestRun`

- `dataset` FK
- `strategy_name` CharField (atau `*` untuk batch parent)
- `parent` FK self null (batch screening)
- `params` JSONField
- `initial_equity` Float
- `fee`, `commission_per_lot`, `spread`, `slippage`, `risk_pct`, `contract_size`
- `in_sample_end` DateField
- `oos_start` DateField
- `multi_deep` BooleanField
- `status` queued / running / done / failed
- `error_message` TextField blank
- `task_id` CharField blank
- `created_at`, `started_at`, `finished_at`
- `created_by` FK User null

### `Trade`

- `run` FK
- `entry_time`, `exit_time`
- `direction` SmallInteger (+1/-1)
- `entry`, `exit`, `lots`, `pnl`, `return_pct`
- `reason` CharField (`SL` / `TP` / `EOD`)

### `EquityPoint`

- `run` FK
- `ts` DateTimeField
- `equity` Float
- Downsample jika > ~20k titik (mis. 1 poin per hari + titik trade).

### `MetricSet`

- `run` FK
- `split` CharField (`full` / `is` / `oos` / `wf_fold` / `stress`)
- `label` CharField blank
- JSON atau kolom: `final_equity`, `total_return`, `cagr`, `sharpe`, `sortino`, `calmar`, `max_drawdown`, `win_rate`, `profit_factor`, `expectancy`, `average_win`, `average_loss`, `trades`, `average_trade`, `longest_losing_streak`, `recovery_factor`, `years`

### `WalkForwardFold`

- `run` FK
- `dev_start`, `dev_end`, `val_start`, `val_end`
- `best_ema_fast` Integer null
- metrik val: sharpe, return, dd, trades
- `positive_sharpe` Boolean

### `RobustnessRow`

- `run` FK
- `kind` (`ema_perturb` / `cost_stress`)
- `label` (`18/48`, `fee_x2`, ...)
- metrik OOS: return, sharpe, dd, trades

### `MonteCarloSummary`

- `run` FK
- `mode` (`shuffle` / `bootstrap` / `perturb` / `slippage_mc`)
- `n_sims` Integer
- `median_final`, `p5_final`, `p25_final`, `p50_final`, `p75_final`, `p95_final`
- `median_max_dd`, `p95_worst_dd`
- `prob_loss`, `prob_dd_gt_30`

### `DecisionGate`

- `run` FK
- boolean: `in_sample`, `out_of_sample`, `walk_forward`, `parameter_stability`, `cost_stress`, `monte_carlo`
- `status` (`FAIL` / `FRAGILE` / `ACCEPTABLE` / `ROBUST`)
- `implement_mql5` Boolean

### `ExportFile`

- `run` FK
- `kind` (`md` / `txt`)
- `path` FileField
- `filename` CharField

Index: `(run, split)` pada MetricSet; `run` pada Trade; `status` pada BacktestRun.

Jangan simpan 10.000 kurva MC penuh. Cukup summary + opsional histogram bins JSON.

---

## 10. Kontrak engine (port notebook)

Kolom OHLCV setelah load: `Datetime`, `Open`, `High`, `Low`, `Close`, `Volume` (kapital seperti notebook).

### 10.1 Data — `engine/data.py`

Port:

- `load_raw(path)`
- `validate_ohlcv(df, name, freq=None) -> dict`
- `resample_h1(df)`

Validasi: duplikat timestamp, OHLC invalid, volume zero %, `volume_dead` vs `VOLUME_DEAD_THRESHOLD` (0.80), gap > 2%.

Default notebook: volume M1 hampir seluruhnya 0 → `VOLUME_USABLE=False` → filter volume strategy diabaikan.

Cache H1 setelah resample; jangan resample M1 di setiap request.

### 10.2 Indikator — `engine/indicators.py`

Port: `rsi`, `true_range`, `atr`, `adx`, `add_indicators(df, ema_periods=None)`.

Default EMA periods: `[10, 15, 18, 19, 20, 21, 22, 25, 30, 48, 49, 50, 51, 52, 200]`.

Output wajib: `ema_*`, `rsi_14`, `atr_14`, `ATR`, `adx_14`, `volume_ma_20`, `range`.

Indikator **tidak** boleh menulis `signal`.

### 10.3 Registry — `engine/registry.py`

Port: `STRATEGY_REGISTRY`, `STRATEGY_SPECS`, `register_strategy`, `list_strategies`, `get_strategy`, `resolve_strategy_queue`.

Auto-import semua `engine/strategies/*.py`.

`ACTIVE_STRATEGY` di form: string, list, atau `*` / `all`.

### 10.4 Plugin — lima fungsi, nama file = nama fungsi

Kontrak output: `signal` ∈ {1, -1, 0}, `sl_atr`, `tp_atr`. Docstring = `logic_spec`.

Params global notebook yang harus jadi default Settings + form:

```text
INITIAL_EQUITY = 10000
FEE = 0.0
COMMISSION_PER_LOT = 7.0
SPREAD = 0.25
SLIPPAGE = 0.0001
RISK_PCT = 0.01
CONTRACT_SIZE = 100
MAX_POSITIONS = 1
IN_SAMPLE_END = 2023-12-31
OOS_START = 2024-01-01
N_MC_SIMS = 10000
MC_SEED = 42
```

Params strategy (dict): `ema_fast` 20, `ema_slow` 50, `ema_trend` 200, `lookback` 24, `rsi_period` 14, `rsi_threshold` 50, `rsi_th` 50, `rsi_long` 52, `rsi_short` 48, `adx_th` 20, `adx_min` 20, `adx_rise` 3, `volume_ma` 20, `atr_period` 14, `atr_sl` 2.0, `atr_tp` 4.0, plus `atr_sl_*` / `atr_tp_*` per plugin, `allow_short` True, `use_volume_filter` True, `pull_bars` 3, `slope_bars` 5.

Plugin:

1. `ema_rsi_volume` — long only; volume filter tergantung `VOLUME_USABLE`.
2. `breakout_atr` — long only; High rolling lookback shift 1.
3. `trend_pullback_by_claude` — long only; EMA200 regime + ADX + pullback.
4. `trend_breakout_by_gemini` — long/short Donchian + EMA200 + ADX + RSI.
5. `momentum_squeeze_by_kimi` — squeeze Donchian/ATR + ADX rising + RSI.

Isolation test: plugin module tidak import `engine.backtester` / `engine.metrics`.

### 10.5 Backtester — `engine/backtester.py`

Port `run_backtest` + dataclass `BacktestResult`.

Aturan eksekusi (jangan diubah tanpa tes regresi):

- Loop mulai `i = 1`.
- Sinyal bar `i-1`, entry `Open[i]` (next-bar).
- Long entry: `open * (1+slippage) + spread/2`.
- Short entry: `open * (1-slippage) - spread/2`.
- `sl_dist = sl_atr[i-1] * ATR[i-1]`; lot = `equity * risk_pct / (contract_size * sl_dist)`.
- Intrabar: jika SL dan TP kena, **SL dulu**.
- Exit: slippage + half spread berlawanan.
- PnL: `direction * (exit-entry) * lots * contract_size` minus `fee * lots * contract_size * (entry+exit)` minus `commission_per_lot * lots`.
- Posisi terbuka di akhir: close terakhir, reason `EOD`.
- Satu posisi (`MAX_POSITIONS = 1`).

### 10.6 Metrics — `engine/metrics.py`

Port `calculate_metrics`. Sharpe/Sortino dari equity harian, 252. Kolom sama dengan notebook (`print_metrics` keys).

### 10.7 Walk-forward

Port `walk_forward_windows(start, end, train_years=3, test_years=1, step_years=1)`.

Per fold: grid `ema_fast` in `{15, 20, 25}` di jendela dev; evaluasi val. `WF_PASS` mengikuti notebook (median val return dan % Sharpe positif). Jangan mengarang threshold baru.

### 10.8 Robustness

- EMA pair ±2: 18/48, 19/49, 20/50, 21/51, 22/52 pada OOS.
- Cost: fee dan slippage ×1, ×2, ×3.

`PARAM_STABLE` / `COST_PASS` harus sama logikanya dengan notebook (bukan "semua harus profit" jika notebook memakai kriteria lain). Baca cell robustness saat implementasi Fase 9.

### 10.9 Monte Carlo — `engine/monte_carlo.py`

Empat mode pada **PnL trade**, bukan acak harga:

| Mode | Isi |
|------|-----|
| shuffle | permutasi urutan PnL (jumlah PnL tetap) |
| bootstrap | sample with replacement |
| perturb | PnL * (1 + N(0, 0.10)) |
| slippage_mc | biaya extra uniform 0.0001–0.0012 * notional |

Default 10_000 sim, seed 42. `MC_PASS` port dari notebook.

### 10.10 Decision gate — `engine/decision_gate.py`

```text
IS_PASS  = sharpe_is > 1.0 and trades_is >= 30
OOS_PASS = sharpe_oos > 0.8 and return_oos > 0 and trades_oos >= 10

Jika bukan OOS_PASS atau return_oos <= 0  -> FAIL
Elif 6/6 gate pass                         -> ROBUST
Elif n_pass >= 4 and OOS_PASS              -> ACCEPTABLE
Else                                       -> FRAGILE
```

Implement MQL5 = YES hanya untuk `ROBUST` dan `ACCEPTABLE`.

### 10.11 Export — `engine/mql5_export.py`

Port `build_mql5_spec` + `export_mql5_spec`. 12 bagian template pipeline. Nama file:

```text
{SYMBOL}_{TF}_{strategy}_{YYYYMMDD}.md|txt
```

Jika status bukan ACCEPTABLE/ROBUST: prefix `REJECTED_`.

---

## 11. Target regresi notebook (Fase 5)

Full sample, biaya default notebook (bukan jaminan bit-exact; toleransi relatif ~1e-3 pada final_equity, 1e-3 pada sharpe):

| Strategy | final_equity (approx) | total_return | sharpe | trades |
|----------|------------------------|--------------|--------|--------|
| breakout_atr | 27001.67 | 170.02% | 0.375 | 1961 |
| ema_rsi_volume | 89513.90 | 795.14% | 0.567 | 3016 |
| momentum_squeeze_by_kimi | 10617.68 | 6.18% | 0.073 | 1109 |
| trend_breakout_by_gemini | 22986.09 | 129.86% | 0.314 | 2166 |
| trend_pullback_by_claude | 15358.39 | 53.58% | 0.212 | 1317 |

Jika angka menyimpang jauh: bug look-ahead atau biaya, bukan "optimasi".

---

## 12. Job background

```text
POST /runs/new/
  -> transaction.atomic: create BacktestRun(status=queued)
  -> transaction.on_commit(enqueue_run.delay(run_id))
  -> redirect ke /runs/<id>/

@task
def enqueue_run(run_id):
    load dataset cache
    indicators
    for name in queue:
      backtest full + IS/OOS
      if multi_deep: WF, robustness, MC, gate, export
    persist
    status=done
```

Progress: field `status` + HTMX poll `/runs/<id>/status/` setiap 2 detik saat running.

Jangan jalankan 10k MC di gunicorn request.

---

## 13. Fase implementasi

Setiap fase: tujuan, file, kontrak, checklist, Definition of Done. Kerjakan berurutan. Jangan loncat ke UI dalam sebelum engine fase itu selesai (kecuali Fase 1 shell kosong).

### Fase 0 — AI-friendly + graph (dokumen ini + rules)

**Tujuan:** Cursor dan MCP paham Higgs sebelum kode Django.

**File:**

- `docs/CONVERSION_PLAN.md` (ini)
- `docs/DESIGN.md`
- `.cursor/rules/*.mdc`
- `AGENTS.md`
- `.cursor/skills/add-strategy/SKILL.md`
- `.agents/skills/` (Taste-Skill, Ponytail)
- `.gitignore`
- `.codegraph/` (lokal)
- index Codebase Memory project `Higgs`

**Checklist:**

- [ ] Rules alwaysApply: identity, architecture, ai-graph, ui-taste
- [ ] Rules glob: django, engine, strategy-plugins, templates-tailwind, models-sqlite, tests
- [ ] Taste-Skill terpasang dan di-patch density dashboard
- [ ] Ponytail terpasang
- [ ] `codegraph init` sukses di `Higgs/`
- [ ] Codebase Memory `index_repository` name `Higgs`

**DoD:** Agent baru yang membuka Higgs mendapat rules; graph bisa di-query meski file masih sedikit.

### Fase 1 — Bootstrap Django 6.1 + shell UI

**Tujuan:** `manage.py runserver` menampilkan shell Taste-Skill, empty state jujur.

**File:** `config/`, apps kosong, `templates/base.html`, `static/src/input.css`, `setup.bat`, `requirements.txt`.

**Perintah (cmd.exe, dari folder Higgs):**

```text
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install "Django>=6.1,<6.2"
django-admin startproject config .
python manage.py startapp core apps\core
```

Sesuaikan `INSTALLED_APPS` path. Tailwind v4 CLI: `npx @tailwindcss/cli` scan templates.

**Checklist:**

- [ ] Python 3.12+
- [ ] `py manage.py check` bersih
- [ ] Login + overview kosong
- [ ] Dark/light
- [ ] Sidebar link ke semua rute (boleh 404 sampai fase terkait)
- [ ] Reindex Codegraph + Codebase Memory

**DoD:** User staff login melihat cockpit kosong yang tidak memalsukan KPI.

### Fase 2 — Data layer

**Tujuan:** Upload CSV, validasi, cache H1, `Dataset` di SQLite.

**File:** `engine/data.py`, `apps/marketdata/`, templates datasets.

**Kontrak:** output validasi setara notebook (`duplicate_ts`, `ohlc_invalid`, `volume_zero_pct`, `volume_dead`).

**DoD:** Dataset XAUUSD M1 terdaftar; H1 ~100k bar; `volume_usable` False untuk file saat ini.

### Fase 2b — Bootstrap dataset jika CSV merged tidak ada

**Status:** implemented (`prepare_dataset.bat` / `prepare_dataset.py`). Tidak memblokir Fase 3+. Wajib sebelum clone GitHub bisa ingest / parity tanpa file lokal.

**Tujuan:** Jika `XAUUSD_2009_2026_M1.csv` tidak ada di root repo, unduh tick M1 tahunan dari HuggingFace, gabungkan, dan tulis file merged yang sama kontrak kolomnya dengan notebook.

**Sumber:** [huggingface.co/datasets/fokan/xauusd-2009-2026](https://huggingface.co/datasets/fokan/xauusd-2009-2026)

**Alur (port notebook Colab, harus Windows/cmd.exe):**

1. Jika `XAUUSD_2009_2026_M1.csv` sudah ada di root `AlgoTradeBacktest/`, skip.
2. `dataset/` — unduh `DAT_MT_XAUUSD_M1_{2009..2025}.csv` plus `DAT_MT_XAUUSD_M1_202601.csv` dari `resolve/main/` (skip file yang sudah ada).
3. Baca tanpa header, kolom: `Date`, `Time`, `Open`, `High`, `Low`, `Close`, `Volume`.
4. `Datetime = Date + Time`; drop `Date`/`Time`; urutan kolom akhir: `Datetime`, `Open`, `High`, `Low`, `Close`, `Volume`.
5. Export `XAUUSD_2009_2026_M1.csv` di root repo (`index=False`).
6. Hapus file mentah di `dataset/` setelah merge sukses.

**File target:**

- `prepare_dataset.bat` di root repo (cmd.exe)
- Script Python di root (bukan `engine/` — ini persiapan file, bukan rumus trading)
- `dataset/` di `.gitignore`

**Larangan port Colab:**

- Jangan `wget`, `os.system`, magic `!ls` / `display()`
- Unduh dengan `urllib.request` (stdlib) atau `pandas`; perintah dokumentasi = cmd.exe
- Jangan commit CSV merged atau file tahunan (sudah > 100MB)

**Checklist:**

- [ ] Skip jika merged CSV sudah ada
- [ ] Resume unduhan per-file jika sebagian `dataset/` sudah terisi
- [ ] Kontrak kolom identik notebook (`Datetime` + OHLCV kapital)
- [ ] File mentah dihapus setelah export
- [ ] README: satu perintah bootstrap untuk clone tanpa CSV
- [ ] Opsional: panggil dari empty state `/datasets/` ("siapkan dataset default") tanpa menjalankan unduhan di request HTTP sinkron — job worker jika di UI

**DoD:** Clone repo tanpa `XAUUSD_2009_2026_M1.csv`, jalankan `prepare_dataset.bat`, file merged muncul; `ingest_dataset` Fase 2 tetap jalan tanpa ubah kontrak.

### Fase 3 — Indikator

**Tujuan:** `add_indicators` tanpa signal.

**Tes:** NaN warmup EMA200/RSI/ATR/ADX masuk akal; tidak ada kolom `signal`.

**DoD:** Cache indikator opsional (parquet) agar run tidak hitung ulang setiap kali.

### Fase 4 — Strategy plugin

**Tujuan:** Lima plugin + registry auto-discover.

**Tes:** `list_strategies()` mengembalikan 5 nama; isolation import.

**DoD:** Halaman `/strategies/` membaca docstring dari registry, bukan hardcode HTML.

### Fase 5 — Backtester + metrics

**Tujuan:** Parity full-sample vs seksi 11.

**File:** `engine/backtester.py`, `engine/metrics.py`, `tests/test_engine_parity.py`.

**DoD:** Tes regresi hijau dengan toleransi seksi 11.

### Fase 6 — Persistensi + task

**Tujuan:** `BacktestRun` queued → worker → Trade/MetricSet.

**File:** models, migrations, `apps/backtests/tasks.py`.

**DoD:** Satu run `ema_rsi_volume` full (atau subset tanggal debug) persist; status done; trade count > 0.

### Fase 7 — UI screening IS/OOS

**Tujuan:** Form New run, list, detail (tab 1–4), Compare, HTMX status.

**DoD:** `*` menjalankan 5 strategy; Compare menampilkan tabel IS/OOS seperti notebook.

### Fase 8 — Walk-forward

**Tujuan:** Tab WF; `WalkForwardFold` tersimpan jika `multi_deep`.

**DoD:** Jumlah window sebanding notebook untuk rentang data penuh; `WF_PASS` persist ke gate.

### Fase 9 — Robustness + cost stress

**Tujuan:** Tab 6–7; `RobustnessRow`.

**DoD:** Lima baris EMA perturb + tiga baris cost; flag stability/cost sesuai notebook.

### Fase 10 — Monte Carlo

**Tujuan:** Tab 8; 4 mode; Chart.js histogram dari bins, bukan 10k garis.

**DoD:** `n_sims` default 10000; seed 42; `MC_PASS` ke gate.

### Fase 11 — Gate + export MQL5

**Tujuan:** Tab 9–10; `ExportFile`; prefix `REJECTED_`.

**DoD:** Isi 12 bagian lengkap; developer MQL5 tidak perlu buka notebook.

### Fase 12 — Hardening

**Tujuan:** Siap development berulang.

**File:** README, tes look-ahead, tes isolasi, `.gitignore` lengkap.

**Checklist:**

- [ ] `py manage.py check --deploy` (local: sesuaikan ALLOWED_HOSTS)
- [ ] Tidak ada `DeprecationWarning` EMAIL_BACKEND vs MAILERS
- [ ] README: venv, setup.bat, runserver, run_worker, Tailwind watch
- [ ] Reindex graph terakhir
- [ ] Pre-flight Taste: density, dark mode, empty state

**DoD:** README cukup untuk clone Higgs dan menjalankan screening.

---

## 14. `requirements.txt` (target)

```text
Django>=6.1,<6.2
pandas
numpy
pyarrow
```

Dev:

```text
pytest
pytest-django
```

Jangan scikit-learn, xgboost, tensorflow.

---

## 15. Perintah Windows (cmd.exe)

Dari `e:\Project\AlgoTradeBacktest\Higgs`:

```text
setup.bat
.venv\Scripts\activate.bat
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Terminal 2:

```text
.venv\Scripts\activate.bat
python manage.py process_tasks
```

(Sesuaikan nama perintah worker resmi Django 6.1 saat implementasi.)

Tailwind watch:

```text
npx @tailwindcss/cli -i static\src\input.css -o static\dist\app.css --watch
```

---

## 16. Codegraph dan Codebase Memory

MCP global Cursor sudah mengarah ke `codegraph` dan `codebase-memory-mcp`.

Setelah Fase 0:

- Index Codegraph: `Higgs/.codegraph/`
- Query: `projectPath` = `e:\Project\AlgoTradeBacktest\Higgs`
- Codebase Memory project name: `Higgs`
- Reindex di akhir Fase 1, 5, 7, 11, 12
- Jangan `codegraph upgrade` otomatis (versi MCP user mungkin tertinggal)

Alur agent:

1. `codegraph_explore` / `search_graph` dulu.
2. Grep/Read hanya jika file baru belum terindex.

---

## 17. Prinsip yang tidak dinegosiasikan

1. Tidak ada ML.
2. Tidak look-ahead: sinyal candle close, entry next open.
3. Isolasi indikator / plugin / backtester / metrics.
4. Job berat di worker.
5. Taste-Skill mengatur pixel; Ponytail mengatur jumlah kode; keduanya tidak menghapus layar seksi 8.
6. Rules dan graph di-update jika struktur folder berubah.
7. Perintah dokumentasi = cmd.exe.

---

## 18. Urutan kerja setelah dokumen ini

| Sekarang (Fase 0) | Nanti |
|-------------------|--------|
| Rules, AGENTS.md, skill add-strategy | `startproject` |
| Taste-Skill + Ponytail + DESIGN.md | Port engine |
| Codegraph init + Memory index | Dashboard isi data |
| `.gitignore` | Tes parity |

Fase 1 dimulai hanya setelah DoD Fase 0 terpenuhi.
