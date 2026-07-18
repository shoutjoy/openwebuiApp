# Joonghee Park PhD 's OpenWebUI Local AI v3.1.2

이 프로그램은 Windows에서 Open WebUI를 로컬로 실행하는 Tkinter 런처이다. 기존 BAT 실행 흐름을 앱 안으로 옮기고, 처음 사용자용 Open WebUI 설치 명령과 Ollama 모델 확인/설치 기능을 함께 제공한다.

## 핵심 동작

`Open WebUI 채팅 시작` 버튼을 누르면 다음 순서로 동작한다.

1. `localhost:8080`에서 기존 서버가 실행 중인지 확인한다.
2. 이미 실행 중이면 브라우저의 채팅 화면만 연다.
3. 실행 중이 아니면 별도의 CMD 창을 연다.
4. CMD 창에서 `open-webui serve`를 실행한다.
5. 서버 로그를 CMD 창에 그대로 표시한다.
6. 8080 포트가 준비되면 브라우저를 자동으로 연다.

## 실행 탭 버튼

- `Local환경실행`: PC에 직접 설치된 `open-webui` 실행 파일을 자동으로 찾은 경우 활성화된다.
- `가상환경 실행`: `C:\OpenWebUI\venv\Scripts\open-webui.exe`가 확인된 경우 활성화된다. 실행 시 `C:\OpenWebUI`로 이동하고 `venv\Scripts\activate.bat`로 가상환경을 활성화한 뒤 `open-webui serve`를 실행한다.
- `Local AI Chat`: `http://localhost:8080/` 채팅 화면을 연다.
- `자동실행`: 체크하면 다음에 앱을 켤 때 Open WebUI 서버를 자동으로 실행한다. 전용 가상환경이 있으면 가상환경 실행을 우선 사용하고, 없으면 Local환경실행을 사용한다.
- `MDlive`: https://mdlivepro.vercel.app/ 를 연다.
- `MDpro`: https://mdproviewer.vercel.app/ 를 연다.
- `서버 중지`: 이 런처가 시작한 Open WebUI 서버를 중지한다.
- `설정`: 실행 명령, 호스트, 포트, 자동 브라우저 열기 옵션을 변경한다.
- `오른쪽 클릭 메뉴 등록`: 현재 사용자 계정의 Windows 바탕화면/폴더 오른쪽 클릭 메뉴에 이 앱 실행 항목을 등록한다.
- `오른쪽 클릭 메뉴 해제`: 등록된 오른쪽 클릭 메뉴 항목을 제거한다.

## 설치 및 모델 기능

`설치 및 모델` 탭에서 다음 기능을 사용할 수 있다.

### 가상환경 & 파이썬

- `Open WebUI 가상환경 설치 실행`: `C:\OpenWebUI` 폴더를 만들고 Python 3.11 우선, 없으면 Python 3.12로 `venv` 가상환경을 만든 뒤, 그 안에서 `python -m pip install open-webui`를 실행한다. 실행 명령은 `cd /d C:\OpenWebUI && call venv\Scripts\activate.bat && open-webui serve`로 저장된다.
- `python pip upgrade`: 새 CMD 창에서 `python.exe -m pip install --upgrade pip`를 실행한다.
- `설치 명령 복사`: CMD나 PowerShell에 붙여 넣을 수 있는 설치 명령을 복사한다.
- `가상환경 설치 확인`: `C:\OpenWebUI\venv`와 `python.exe`, `activate.bat`, `open-webui.exe` 존재 여부를 확인한다.
- `가상환경에서 실행`: `C:\OpenWebUI`로 이동하고 `venv\Scripts\activate.bat`를 실행한 다음 `open-webui serve`로 서버를 실행한다.

### AI 모델 설치

- 앱 시작 시 `ollama list`를 자동 실행해 PC에 이미 다운로드된 Ollama 모델을 보여준다.
- `모델 목록 새로고침`: 설치된 모델 목록을 다시 조회한다.
- `CMD에서 모델 설치`: 입력한 모델명으로 `ollama pull <모델명>`을 실행한다.
- `모델 설치 명령 복사`: CMD나 PowerShell에서 직접 실행할 수 있는 `ollama pull <모델명>` 명령을 복사한다.
- `Ollama 모델 페이지 열기`: https://ollama.com/library 를 연다.
- `Hugging Face 모델 페이지 열기`: https://huggingface.co/models 를 연다.

예시 모델 설치 명령:

    ollama pull llama3.1:8b
    ollama pull qwen2.5:7b
    ollama pull gemma2:9b

## Python, 가상환경, pip 설치 절차

Open WebUI는 Python 버전 제약이 있다. 일반적으로 Python 3.11 또는 3.12 환경에서 설치해야 하며, Python 3.10 이하 또는 Python 3.13 이상에 연결된 `pip`로 설치하면 `Requires-Python >=3.11,<3.13` 오류가 날 수 있다.

현재 PC의 Python 상태는 CMD에서 다음 명령으로 확인한다.

    python --version
    pip --version
    py --list

권장 설치 방식은 기존 Python을 삭제하지 않고 Open WebUI 전용 가상환경을 따로 만드는 것이다. 런처의 `Open WebUI 가상환경 설치 실행` 버튼은 아래 흐름을 CMD 창에서 실행한다.

    cd /d C:\
    if not exist OpenWebUI mkdir OpenWebUI
    cd /d C:\OpenWebUI
    py -3.11 --version
    py -3.12 --version
    py -3.11 -m venv venv
    또는 py -3.12 -m venv venv
    call venv\Scripts\activate.bat
    python --version
    python -m pip install --upgrade pip setuptools wheel
    python -m pip install open-webui
    python -m pip show open-webui

실제 앱 내부 명령은 Python 3.11을 먼저 찾고, 없으면 Python 3.12를 사용한다. 둘 다 없으면 Python 3.11 64-bit 설치와 Python Launcher 설치가 필요하다는 메시지를 CMD 창에 표시한다.

설치가 끝나면 런처의 실행 명령은 다음 값으로 저장된다.

    cd /d C:\OpenWebUI && call venv\Scripts\activate.bat && open-webui serve

`python pip upgrade` 버튼은 전역 Python의 pip만 업그레이드한다.

    python.exe -m pip install --upgrade pip

Open WebUI 설치에는 전용 가상환경 버튼을 사용하는 것이 더 안전하다.

## 사용 방법

### EXE 다운로드

[OpenWebUI-Local-AI-Launcher-Tabbed-v6.exe 다운로드](https://github.com/shoutjoy/openwebuiApp/raw/refs/heads/main/dist/OpenWebUI-Local-AI-Launcher-Tabbed-v6.exe)

### Python으로 실행

`run_launcher.bat`를 더블클릭한다.

### Flask 웹앱으로 실행

브라우저 UI로 사용하려면 `webapp_flask` 폴더의 Flask 서버를 실행한다.

    cd /d C:\CusorApps\openWebUi_app\OpenWebUI_Chat_Launcher_v3\OpenWebUI_Chat_Launcher\webapp_flask
    python -m pip install -r requirements.txt
    python app.py

또는 `webapp_flask\run_flask_webapp.bat`를 더블클릭한다. 실행 후 브라우저에서 다음 주소를 연다.

    http://127.0.0.1:8000

Flask 웹앱은 기존 tkinter 런처의 주요 기능을 브라우저에서 사용할 수 있게 옮긴 버전이다.

- Open WebUI 실행 상태 확인, `Local환경실행`, `가상환경 실행`, 자동 실행, 서버 중지
- 실행 명령, 호스트, 포트, 자동 브라우저 열기, 자동 시작, 선택 모델 설정 저장
- `C:\OpenWebUI\venv` 설치 확인, Open WebUI 가상환경 설치 CMD 실행, `python pip upgrade`
- Ollama 모델 목록 조회, 선택 모델 저장, `ollama pull <모델명>` CMD 실행
- Windows 오른쪽 클릭 메뉴 등록/해제
- OpenWebUI, MDlive, MDpro 바로 열기
- OpenWebUI API 테스트 UI

OpenWebUI API 테스트의 기본 호출 주소는 현재 설정된 Open WebUI 주소에 `/api/chat`을 붙여 사용한다. 다른 API 주소나 토큰이 필요하면 Flask 실행 전에 환경변수를 지정한다.

    set OPENWEBUI_CHAT_API_URL=http://localhost:8080/api/chat
    set OPENWEBUI_API_TOKEN=your_token_here
    python app.py

추후 다른 에디터 앱과 연동하려면 `webapp_flask\services\integrations.py`의 `DEFAULT_INTEGRATIONS`에 항목을 추가한다. 자세한 내용은 `webapp_flask\README.md`를 참고한다.

### EXE 생성

Windows PC에서 `build_windows_exe.bat`를 더블클릭한다.

생성 결과:

    dist\OpenWebUI-Chat-Launcher.exe

### GitHub에서 자동으로 EXE 생성

이 프로젝트를 GitHub 저장소에 올린 뒤 Actions 메뉴에서 `Build Windows EXE`를 실행한다. 빌드가 완료되면 Artifacts에서 EXE 압축 파일을 다운로드할 수 있다.

## 설정

기본 실행 명령:

    open-webui serve

PATH에서 명령을 찾지 못하는 경우 설정 창의 `자동 찾기`를 누른다. 그래도 찾지 못하면 다음과 같이 전체 경로를 입력한다.

    "C:\Users\사용자\AppData\Local\Programs\Python\Python311\Scripts\open-webui.exe" serve

또는 Python 모듈 방식으로 실행한다.

    "C:\경로\python.exe" -m open_webui serve

자동실행 설정은 앱에서 체크하면 즉시 저장된다. 설정 파일은 다음 위치에 저장된다.

    %LOCALAPPDATA%\OpenWebUIChatLauncher\settings.json

오른쪽 클릭 메뉴 등록은 관리자 권한이 필요 없는 현재 사용자 레지스트리 경로를 사용한다.

    HKCU\Software\Classes\DesktopBackground\Shell\OpenWebUILocalAILauncher
    HKCU\Software\Classes\Directory\Background\shell\OpenWebUILocalAILauncher
    HKCU\Software\Classes\Directory\shell\OpenWebUILocalAILauncher

## 주의

- Open WebUI의 실제 채팅 모델 선택은 브라우저에서 열린 Open WebUI 화면 안에서 진행한다.
- 이 런처의 모델 선택/저장은 로컬 런처 설정용이며, 필요한 모델을 Ollama에 설치하는 편의 기능이다.
- `ollama list`와 `ollama pull`을 사용하려면 Ollama가 먼저 설치되어 있어야 한다.
- CMD 창을 닫으면 Open WebUI 서버도 종료된다.
- 실행기 창을 닫아도 CMD 서버 창은 계속 실행된다.
