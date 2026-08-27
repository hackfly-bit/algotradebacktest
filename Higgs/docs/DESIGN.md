# Higgs Design Tokens

Source of truth untuk UI. Taste-Skill wajib membaca file ini sebelum menulis template. Dashboard product, bukan landing page.

## Brief

- Produk: cockpit backtest XAUUSD (research, bukan marketing).
- Stack UI: Django templates, Tailwind CSS v4, HTMX, Chart.js, Alpine.js minimal.
- Tema: light + dark (`class="dark"` di `<html>`), off-white / off-black, **satu** aksen.
- `VISUAL_DENSITY`: 8–9 (tabel rapat, KPI kecil, sedikit whitespace).
- `MOTION_INTENSITY`: 2–3 (hover, focus, HTMX swap). Tanpa GSAP scroll-hijack.
- `DESIGN_VARIANCE`: 4–5 (layout dashboard konsisten, bukan eksperimen hero).

## Color

- Canvas light: `#F4F1EA`
- Canvas dark: `#121410`
- Surface light: `#FFFcf7`
- Surface dark: `#1C1E1A`
- Border: `black/10` / `white/10`
- Text: near-black / near-white, bukan `#000` / `#fff` murni
- Accent (satu): teal `#0F7A6C` (dark: `#3D9A8C`)
- Semantic: profit `#1B7F4E`, loss `#B42318`, warn `#B45309`
- **Dilarang:** ungu AI, mesh gradient, rainbow chart

## Type

- Sans only: `"IBM Plex Sans", "Source Sans 3", ui-sans-serif, system-ui`
- Mono untuk angka tabel: `"IBM Plex Mono", ui-monospace`
- Jangan serif editorial

## Shape and density

- Radius: `6px` (satu sistem). Jangan campur pill + sharp.
- Sidebar: ~240px desktop; drawer di viewport sempit
- KPI: 4–6 chip per row, angka mono, label 11–12px
- Tabel: compact (`text-sm`, row padding kecil), sticky header

## Components

- Shell: sidebar + topbar (judul, dataset aktif, job status HTMX, theme toggle)
- Empty state: teks jujur, tanpa grafik dummy
- Charts: Chart.js, grid tipis, tanpa glow
- Forms: label di atas input, error Django standar di-style token

## Anti-slop

- Bukan tiga kartu fitur sama lebar sebagai layout halaman
- Bukan fake terminal / fake task list
- Bukan angka placeholder yang berpura-pura live
- Data dari SQLite/engine atau empty state
