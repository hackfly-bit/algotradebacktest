# Higgs — panduan agent

Aplikasi backtest XAUUSD rules-based. Root kerja: folder **Higgs/** (bukan notebook di parent).

## Wajib baca dulu

1. [docs/CONVERSION_PLAN.md](docs/CONVERSION_PLAN.md)
2. [docs/DESIGN.md](docs/DESIGN.md)
3. Graph: Codegraph `projectPath` = folder Higgs ini; Codebase Memory project `Higgs`

## Stack

Django 6.1, Python 3.12+, SQLite, Tailwind v4, HTMX, Chart.js, Django Tasks. Perintah: **cmd.exe**.

## Larangan

- ML (`fit` / `predict` / sklearn / boosting)
- Look-ahead (sinyal bar i, entry open bar i)
- `import django` di `engine/`
- Job berat di request HTTP sinkron
- SPA / React / CSS framework kedua
- PowerShell atau Bash di dokumentasi perintah

## UI

Taste-Skill + `docs/DESIGN.md`. Density 8–9. Ponytail: jangan over-build; jangan potong halaman pipeline.

## Fase

Fase 5 (backtester + metrics) selesai. Paritas penuh vs notebook membutuhkan `XAUUSD_2009_2026_M1.csv` (lihat Fase 2b). Berikutnya Fase 6: persistensi `BacktestRun` + `django.tasks` worker.

**Backlog:** [Fase 2b](docs/CONVERSION_PLAN.md#fase-2b--bootstrap-dataset-jika-csv-merged-tidak-ada) — bootstrap HuggingFace agar tes parity bisa hijau tanpa CSV lokal manual.
