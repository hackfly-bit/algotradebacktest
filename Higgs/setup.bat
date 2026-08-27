@echo off
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  py -3.12 -m venv .venv 2>nul
  if errorlevel 1 py -3 -m venv .venv
) else (
  python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if exist package.json (
  call npm install
  call npx @tailwindcss/cli -i static\src\input.css -o static\dist\app.css
)

echo.
echo Higgs Fase 1. Berikutnya di cmd.exe:
echo   python manage.py migrate
echo   python manage.py createsuperuser
echo   python manage.py runserver
echo Terminal lain untuk CSS:
echo   npx @tailwindcss/cli -i static\src\input.css -o static\dist\app.css --watch
