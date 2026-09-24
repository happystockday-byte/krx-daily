@echo off
chcp 65001 >nul
cd /d %~dp0
echo ============================================
echo   KRX Daily Card - Auto Setup
echo ============================================

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Install from python.org and check "Add Python to PATH".
  pause & exit /b
)

echo [1/4] Installing packages...
python -m pip install -r requirements.txt -q

echo [2/4] Enter your X API keys (Developer Console - Keys and tokens)
set /p K1=X_API_KEY: 
set /p K2=X_API_SECRET: 
set /p K3=X_ACCESS_TOKEN: 
set /p K4=X_ACCESS_SECRET: 
(
echo X_API_KEY=%K1%
echo X_API_SECRET=%K2%
echo X_ACCESS_TOKEN=%K3%
echo X_ACCESS_SECRET=%K4%
) > .env

echo [3/4] Test run (image only, no upload)...
python daily_market_card.py --dry-run
echo    -^> check the "output" folder for the card image.

echo [4/4] Registering daily task (Mon-Fri 17:00)...
schtasks /create /tn "KRX_Daily_X" /tr "\"%~dp0run_daily.bat\"" /sc weekly /d MON,TUE,WED,THU,FRI /st 17:00 /f

echo.
echo Done. It will post to X every trading day at 17:00.
echo To stop:  schtasks /delete /tn "KRX_Daily_X" /f
pause
