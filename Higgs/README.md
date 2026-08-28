# Higgs — Backtest Cockpit XAUUSD

Aplikasi web lokal untuk backtest rules-based XAUUSD, di-port dari [`XAUUSD_Momentum_Pipeline.ipynb`](../XAUUSD_Momentum_Pipeline.ipynb). Bukan sistem ML — hanya aturan teknikal, next-bar execution, dan pipeline validasi seperti notebook.

Stack: **Django 6.1** · **SQLite** · **Tailwind v4** · **HTMX** · **Chart.js**

---

## Persyaratan

| Komponen | Versi |
|----------|--------|
| Python | 3.12+ |
| Node.js | Untuk Tailwind CLI |
| OS | Windows 11 (perintah di bawah memakai **cmd.exe**) |
| Ruang disk | ~500 MB+ untuk dataset XAUUSD M1 cache H1 |

---

## Instalasi cepat

Dari folder `Higgs/`:

```text
setup.bat
.venv\Scripts\activate.bat
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Buka browser: **http://127.0.0.1:8000/** → login dengan superuser yang baru dibuat.

Tailwind (wajib sekali, atau watch saat edit CSS):

```text
npx @tailwindcss/cli -i static\src\input.css -o static\dist\app.css
npx @tailwindcss/cli -i static\src\input.css -o static\dist\app.css --watch
```

---

## Persiapan dataset

Dataset default **tidak di-commit** (file ~300 MB). Pilih salah satu:

### Opsi A — Bootstrap dari HuggingFace (clone tanpa CSV)

Dari **root repo** `AlgoTradeBacktest/`:

```text
prepare_dataset.bat
```

Menghasilkan `XAUUSD_2009_2026_M1.csv` di root repo.

### Opsi B — Sudah punya CSV merged

Pastikan file ada di root repo dengan kolom: `Datetime`, `Open`, `High`, `Low`, `Close`, `Volume`.

### Ingest ke Higgs

Dari folder `Higgs/` (venv aktif):

```text
python manage.py ingest_dataset ..\XAUUSD_2009_2026_M1.csv
```

Output contoh: `rows_h1≈100k`, `volume_usable=False` (normal untuk tick data ini).

Alternatif: upload CSV kecil lewat UI **Dataset** (`/datasets/`) — file besar (>200 MB) gunakan command di atas.

---

## Panduan penggunaan

### 1. Login

| URL | Keterangan |
|-----|------------|
| `/accounts/login/` | Login staff/superuser |
| `/` | Dashboard ringkasan setelah login |

Buat akun pertama kali:

```text
python manage.py createsuperuser
```

---

### 2. Dataset (`/datasets/`)

1. Buka **Dataset** di sidebar.
2. Jika kosong → ingest CSV seperti di atas, atau upload CSV M1 sample.
3. Klik baris dataset → detail validasi M1/H1, `volume_usable`, rentang tanggal.

Dataset aktif terbaru ditampilkan di topbar.

---

### 3. Strategi (`/strategies/`)

Lima plugin rules-based (sama dengan notebook):

| Nama | Gaya |
|------|------|
| `ema_rsi_volume` | Long, EMA + RSI + volume |
| `breakout_atr` | Long, breakout Donchian + ATR |
| `trend_pullback_by_claude` | Long, pullback EMA200 |
| `trend_breakout_by_gemini` | Long/short, Donchian + ADX |
| `momentum_squeeze_by_kimi` | Squeeze + ADX rising |

Klik nama strategi → parameter default + docstring (`logic_spec`).

#### Strategy Builder (`/strategies/builder/`)

Buat strategi **tanpa coding Python**:

1. **Builder** → pilih template (breakout, EMA/RSI, gemini, claude, kimi)
2. Edit lewat **Visual rule editor** (tambah kondisi, preset blocks, panel parameter) — tab JSON opsional
3. **Cek schema** live + preview logic_spec
4. Set status **active** → muncul di form Run baru dan screening `*`
5. **Preview OHLC** + marker long/short + **Quick test** mini backtest
6. **Export/Import JSON**, duplikat, **versi baru** (fork), filter milik saya/semua

Custom slug: `custom_<nama>` (contoh `custom_my_breakout`).

---

### 4. Screening cepat — semua strategi (`*`)

Alur setara `ACTIVE_STRATEGY = "*"` di notebook (IS/OOS saja, tanpa deep pipeline):

1. **Run baru** → `/runs/new/`
2. Pilih **Dataset**
3. Strategi: **Semua strategi (\*)**
4. Biarkan default IS/OOS:
   - In-sample end: `2023-12-31`
   - OOS start: `2024-01-01`
5. **Jangan** centang MULTI_DEEP (lebih cepat).
6. Submit → redirect ke halaman screening parent.
7. Tunggu status **done** (HTMX polling di topbar).
8. Buka **Bandingkan** → `/compare/` untuk tabel IS vs OOS semua strategi.

---

### 5. Run satu strategi + analisis mendalam (MULTI_DEEP)

Untuk walk-forward, robustness, Monte Carlo, gate, dan export MQL5:

1. **Run baru** → pilih **satu strategi** (mis. `ema_rsi_volume`)
2. Centang **MULTI_DEEP**
3. Submit → buka run detail `#<id>`

**Tab run detail** (10 tab jika MULTI_DEEP):

| # | Tab | Isi |
|---|-----|-----|
| 1 | Overview | KPI full sample |
| 2 | Equity | Kurva equity Chart.js |
| 3 | Trades | Tabel trade (paginasi) |
| 4 | IS/OOS | Metrik in-sample vs out-of-sample |
| 5 | Walk-forward | 13 fold (data penuh), WF_PASS |
| 6 | Robustness | Grid EMA fast IS + perturb OOS |
| 7 | Cost stress | Fee/spread ×1, ×2, ×3 |
| 8 | Monte Carlo | 4 mode, histogram bootstrap |
| 9 | Gate | 6 gate → FAIL / FRAGILE / ACCEPTABLE / ROBUST |
| 10 | Export | Preview + unduh `.md` / `.txt` |

**Catatan waktu:** MULTI_DEEP pada dataset penuh + MC 10.000 sim memakan beberapa menit (job sinkron di proses web).

---

### 6. Export MQL5

| Lokasi | Keterangan |
|--------|------------|
| Tab **Export** di run detail | Preview spec + link unduh |
| `/exports/` | Daftar semua file export |

Naming file:

- **ACCEPTABLE / ROBUST** → `XAUUSD_1H_<strategy>_YYYYMMDD.md`
- **FAIL / FRAGILE** → `REJECTED_XAUUSD_1H_<strategy>_YYYYMMDD.md`

File disimpan di `Higgs/media/exports/`.

---

### 7. Parameter biaya default (notebook)

| Parameter | Default |
|-----------|---------|
| Initial equity | 10.000 |
| Fee | 0.0 |
| Commission / lot | 7.0 USD |
| Spread | 0.25 |
| Slippage | 0.0001 |
| Risk % | 1% |
| Contract size | 100 |
| IS end | 2023-12-31 |
| OOS start | 2024-01-01 |

Override per run lewat form **Run baru**.

---

### 8. Decision gate (ringkasan)

| Gate | Kriteria lulus |
|------|----------------|
| In-sample | Sharpe > 1.0, trades ≥ 30 |
| Out-of-sample | Sharpe > 0.8, return > 0, trades ≥ 10 |
| Walk-forward | ≥50% fold Sharpe val > 0, median return val > 0 |
| Parameter stability | PARAM_STABLE ∧ PERTURB_STABLE |
| Cost stress | OOS profit pada biaya ×2 |
| Monte Carlo | Bootstrap P(loss) < 15%, median > equity awal |

| Status | Arti |
|--------|------|
| **ROBUST** | 6/6 gate lulus |
| **ACCEPTABLE** | ≥4/6 + OOS lulus → export MQL5 direkomendasikan |
| **FRAGILE** | OOS lulus tapi <4 gate |
| **FAIL** | OOS gagal |

---

## Peta URL

| URL | Fungsi |
|-----|--------|
| `/` | Dashboard |
| `/datasets/` | Daftar + upload dataset |
| `/datasets/<id>/` | Detail validasi |
| `/strategies/` | Registry strategi |
| `/strategies/<name>/` | Detail strategi |
| `/runs/new/` | Form run baru |
| `/runs/` | Daftar run |
| `/runs/<id>/` | Detail run + tab |
| `/compare/` | Perbandingan screening `*` |
| `/exports/` | Daftar export MQL5 |
| `/exports/<id>/download/` | Unduh file |
| `/settings/` | ⚠ Placeholder (belum implementasi) |

---

## Menjalankan tes

```text
.venv\Scripts\activate.bat
set PYTHONPATH=.
python -m pytest tests\ -q
```

Harus **71 passed** (parity notebook, rule interpreter, visual builder UI, walk-forward, gate, deep pipeline).

Parity penuh membutuhkan dataset bootstrap + ingest terlebih dahulu.

---

## Audit kelengkapan (vs CONVERSION_PLAN)

### ✅ Selesai

| Area | Status |
|------|--------|
| Data layer (upload, validasi, cache H1) | ✅ |
| Bootstrap dataset (`prepare_dataset.bat`) | ✅ |
| Indikator (RSI, ATR, ADX, EMA) | ✅ |
| 5 strategy plugin + registry | ✅ |
| Backtester next-bar + biaya | ✅ |
| Metrics + tes parity notebook | ✅ |
| Persistensi run/trade/metric | ✅ |
| UI dashboard + screening IS/OOS | ✅ |
| Walk-forward + WalkForwardFold | ✅ |
| Robustness + cost stress | ✅ |
| Monte Carlo 4 mode | ✅ |
| Decision gate + export MQL5 | ✅ |
| README + 53 tests | ✅ |

### ⚠ Belum / deviasi

| Item | Keterangan | Prioritas |
|------|------------|-----------|
| **Halaman Settings** (`/settings/`) | Masih placeholder; default fee/risk tidak disimpan global | Rendah |
| **Filter gate di `/runs/`** | Rencana: filter by gate status; saat ini hanya status + strategy | Rendah |
| **Kolom gate di `/compare/`** | Data gate ada di backend, belum ditampilkan di tabel compare | Rendah |
| **Chart drawdown terpisah** | Tab Equity hanya equity line; drawdown hanya angka KPI | Rendah |
| **Model `EquityPoint`** | Kurva equity disimpan di `MetricSet.extras` (JSON), bukan tabel terpisah | Deviasi OK |
| **Cache indikator Parquet** | Indikator dihitung ulang tiap run; cache opsional belum ada | Rendah |
| **Background worker** | `ImmediateBackend` (sinkron); `DatabaseBackend` belum ada di Django 6.1 | Menunggu Django |
| **Tab preview strategy** | Notebook punya preview pasca-MC; belum ada tab UI terpisah | Rendah |
| **PR merge ke `main`** | PR #2–#6 masih draft, belum di-merge | Operasional |

### ❌ Non-goals (sengaja tidak ada)

- Machine learning / prediksi harga
- Live trading / broker API
- PostgreSQL / multi-tenant
- SPA React/Vue

---

## Troubleshooting

| Masalah | Solusi |
|---------|--------|
| CSS polos / tidak styled | Jalankan Tailwind build (lihat Instalasi) |
| `ingest_dataset` lambat | Normal untuk ~5,8 juta bar M1; tunggu 2–5 menit |
| Run gagal `IndexError` / slice kosong | Pastikan tanggal IS/OOS ada di rentang dataset |
| Walk-forward 0 fold | Data perlu ≥4 tahun (train 3y + test 1y) |
| MULTI_DEEP sangat lambat | Expected; MC 10k sim. Untuk dev, gunakan dataset sample kecil |
| Export kosong | Hanya dihasilkan saat MULTI_DEEP selesai tanpa error |
| `volume_usable=False` | Normal; filter volume strategy otomatis diabaikan |

---

## Dokumen terkait

- [`docs/CONVERSION_PLAN.md`](docs/CONVERSION_PLAN.md) — rencana fase & kontrak engine
- [`docs/DESIGN.md`](docs/DESIGN.md) — token UI
- [`AGENTS.md`](AGENTS.md) — panduan agent Cursor

---

## Alur kerja disarankan (first run)

```text
1. setup.bat && migrate && createsuperuser
2. prepare_dataset.bat          (root repo, jika belum punya CSV)
3. ingest_dataset ..\XAUUSD_2009_2026_M1.csv
4. runserver
5. Login → Run baru → * → Compare
6. Run baru → ema_rsi_volume + MULTI_DEEP → tab Gate + Export
```
