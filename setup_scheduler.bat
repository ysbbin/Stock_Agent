@echo off
chcp 65001 > nul
schtasks /delete /tn "StockResearchAgent" /f >nul 2>&1
schtasks /create ^
  /tn "StockResearchAgent" ^
  /tr ""C:\Users\PC\AppData\Local\Programs\Python\Python311\python.exe" "C:\Users\PC\Desktop\stock_agent\scheduler.py"" ^
  /sc DAILY ^
  /st 01:25 ^
  /ru "%USERNAME%" ^
  /rl HIGHEST ^
  /f
if %errorlevel% == 0 (
    echo SUCCESS
) else (
    echo FAIL
)
