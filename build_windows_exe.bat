@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if not %errorlevel%==0 (
    echo Python Launcher(py.exe)를 찾지 못했습니다.
    pause
    exit /b 1
)

echo [1/3] 빌드 환경 생성
py -3.11 -m venv .build-venv
if errorlevel 1 goto :error

echo [2/3] PyInstaller 설치
call .build-venv\Scripts\python.exe -m pip install --upgrade pip pyinstaller
if errorlevel 1 goto :error

echo [3/3] Windows EXE 생성
call .build-venv\Scripts\pyinstaller.exe ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --add-data "local_chat;local_chat" ^
  --name "OpenWebUI-Chat-Launcher" ^
  launcher.py
if errorlevel 1 goto :error

echo.
echo 빌드 완료:
echo %CD%\dist\OpenWebUI-Chat-Launcher.exe
pause
exit /b 0

:error
echo.
echo EXE 빌드에 실패했습니다.
pause
exit /b 1
