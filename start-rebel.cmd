@echo off
rem Double-click to start Rebel Store Manager. Extra options are passed on, e.g.: start-rebel.cmd --rebuild
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo The Python environment was not found in %CD%\.venv
  echo Open PowerShell in this folder and run these two commands, then double-click this file again:
  echo   python -m venv .venv
  echo   .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 2
)
".venv\Scripts\python.exe" -m tools.run_app %*
set CODE=%ERRORLEVEL%
if not "%CODE%"=="0" (
  echo.
  echo Something went wrong ^(see the message above^). Nothing was changed in your data.
  pause
) else (
  timeout /t 6 >nul
)
exit /b %CODE%
