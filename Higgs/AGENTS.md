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

Fase 8 (walk-forward tab + WalkForwardFold) selesai. Berikutnya Fase 9: robustness + cost stress.

Paritas: `prepare_dataset.bat` → ingest → screening `*` → `/compare/`.
