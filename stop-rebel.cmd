@echo off
rem Double-click to stop Rebel Store Manager (it first asks the app for a backup).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo The Python environment was not found in %CD%\.venv - nothing to stop from here.
  pause
  exit /b 2
)
".venv\Scripts\python.exe" -m tools.run_app --stop
set CODE=%ERRORLEVEL%
if not "%CODE%"=="0" (
  echo.
  pause
) else (
  timeout /t 4 >nul
)
exit /b %CODE%
