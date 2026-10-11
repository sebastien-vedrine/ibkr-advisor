@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
echo ============================================================
echo   IBKR Advisor - build + one-file installer (Windows)
echo ============================================================

rem ---------- 1. Python (installed automatically if missing)
call :find_python
if not defined PY (
  echo Python not found - installing it with winget...
  winget install -e --id Python.Python.3.13 --scope user --silent --accept-package-agreements --accept-source-agreements
  if errorlevel 1 winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
  call :find_python
)
if not defined PY (
  echo Could not find or install Python. Install it from https://www.python.org/downloads/ and run build.bat again.
  goto :err
)
echo Using Python: !PY!

rem ---------- 2. Virtual env + dependencies
if not exist ".venv\Scripts\python.exe" (
  "!PY!" -m venv .venv || goto :err
)
set "VPY=.venv\Scripts\python.exe"
"%VPY%" -m pip install --upgrade pip >nul
"%VPY%" -m pip install --upgrade -r requirements.txt pyinstaller || goto :err

rem ---------- 3. Version (read by a script: no cmd quoting pitfalls)
for /f "usebackq delims=" %%v in (`"%VPY%" tools\get_version.py`) do set "APPVER=%%v"
if not defined APPVER goto :err
echo Building IBKR Advisor !APPVER!

rem ---------- 4. Executable
"%VPY%" -m PyInstaller --noconfirm --clean --windowed --name IBKR-Advisor --collect-all customtkinter --collect-all yfinance --collect-submodules ib_async main.py || goto :err

rem ---------- 5. Inno Setup (installed automatically if missing)
call :find_iscc
if not defined ISCC (
  echo Inno Setup not found - installing it with winget...
  winget install -e --id JRSoftware.InnoSetup --scope user --silent --accept-package-agreements --accept-source-agreements
  call :find_iscc
)
if not defined ISCC (
  echo Could not find or install Inno Setup. Install it from https://jrsoftware.org/isdl.php and run build.bat again.
  goto :err
)
"!ISCC!" /Qp /DAppVersion=!APPVER! ibkr-advisor.iss || goto :err

echo.
echo ============================================================
echo   Done: dist\Installer-IBKR-Advisor.exe
echo   This single file is all you need to install IBKR Advisor.
echo ============================================================
explorer dist
pause
exit /b 0

:find_python
set "PY="
for /f "delims=" %%q in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%q"
if not defined PY for /f "delims=" %%p in ('where python 2^>nul') do if not defined PY (
  echo %%p | find /i "WindowsApps" >nul || set "PY=%%p"
)
if not defined PY for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%d\python.exe" set "PY=%%d\python.exe"
exit /b 0

:find_iscc
set "ISCC="
for %%f in ("%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe") do (
  if not defined ISCC if exist "%%~f" set "ISCC=%%~f"
)
exit /b 0

:err
echo.
echo *** Build failed - see the messages above. ***
pause
exit /b 1
