@echo off
chcp 65001 >nul
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3.11 launcher.py
    if %errorlevel%==0 exit /b 0
    py launcher.py
    exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
    python launcher.py
    exit /b %errorlevel%
)

echo Python을 찾지 못했습니다.
pause
