@echo off
REM Builds a single-file IBKR-Advisor.exe (needs Python 3.10+ on PATH)
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --onefile --windowed --name IBKR-Advisor ^
  --collect-all customtkinter --collect-all yfinance --collect-submodules ib_async main.py
echo.
echo Done: dist\IBKR-Advisor.exe
pause
