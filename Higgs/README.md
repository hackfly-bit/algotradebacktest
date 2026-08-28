# Higgs

Cockpit backtest rules-based XAUUSD — port dari `XAUUSD_Momentum_Pipeline.ipynb` ke Django 6.1 + SQLite + Tailwind v4 + HTMX + Chart.js.

## Persyaratan

- Python 3.12+
- Node.js (Tailwind CLI)

## Setup (Windows cmd.exe)

```text
cd Higgs
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
npx @tailwindcss/cli -i static\src\input.css -o static\dist\app.css
```

Dataset XAUUSD M1 (jika belum ada di root repo):

```text
cd ..
prepare_dataset.bat
cd Higgs
python manage.py ingest_dataset ..\XAUUSD_2009_2026_M1.csv
```

## Menjalankan

Terminal 1 — web:

```text
.venv\Scripts\activate.bat
python manage.py runserver
```

Job backtest memakai `django.tasks` dengan `ImmediateBackend` (sinkron di proses yang sama). Untuk dataset besar, pertimbangkan worker resmi Django 6.1 saat `DatabaseBackend` tersedia.

Tailwind watch:

```text
npx @tailwindcss/cli -i static\src\input.css -o static\dist\app.css --watch
```

Login: `/accounts/login/` — buat superuser via `createsuperuser`.

## Alur screening

1. Upload / ingest dataset di `/datasets/`
2. New run di `/runs/new/` — pilih strategi atau `*` (semua)
3. Aktifkan **MULTI_DEEP** untuk walk-forward, robustness, Monte Carlo, gate, export MQL5
4. Compare IS/OOS di `/compare/`
5. Export spec di tab run atau `/exports/`

## Tes

```text
.venv\Scripts\activate.bat
set PYTHONPATH=.
python -m pytest tests\ -q
```

## Struktur fase

| Fase | Fitur |
|------|--------|
| 2–6 | Data, indikator, plugin, backtester, persistensi |
| 7 | UI run / compare / HTMX |
| 8 | Walk-forward |
| 9 | Robustness + cost stress |
| 10 | Monte Carlo (4 mode) |
| 11 | Decision gate + export MQL5 |
| 12 | README, tes, hardening |

Rencana lengkap: `docs/CONVERSION_PLAN.md`.
