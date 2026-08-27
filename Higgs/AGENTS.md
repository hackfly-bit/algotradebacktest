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

Fase 2 (data layer) selesai. Berikutnya Fase 3: indikator (`engine/indicators.py`), tanpa sinyal atau backtest.

**Backlog (tidak memblokir Fase 3):** [Fase 2b](docs/CONVERSION_PLAN.md#fase-2b--bootstrap-dataset-jika-csv-merged-tidak-ada) — jika `XAUUSD_2009_2026_M1.csv` tidak ada, unduh + merge dari HuggingFace `fokan/xauusd-2009-2026`.
