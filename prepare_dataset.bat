@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 prepare_dataset.py %*
) else (
  python prepare_dataset.py %*
)
endlocal
