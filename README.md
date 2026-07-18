# Joonghee Park PhD 's OpenWebUI Local AI v3.1

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

- `내부 설치 실행`: 설정에 저장된 일반 실행 명령을 사용한다. 기본값은 `open-webui serve`이며, PC에 직접 설치된 Open WebUI를 실행할 때 사용한다.
- `가상환경 실행`: `C:\OpenWebUI\venv\Scripts\open-webui.exe serve`를 사용한다. `Open WebUI 가상환경 설치 실행`으로 만든 전용 가상환경에서 실행할 때 사용한다.
- `Local AI Chat`: `http://localhost:8080/` 채팅 화면을 연다.
- `MDlive`: https://mdlivepro.vercel.app/ 를 연다.
- `MDpro`: https://mdproviewer.vercel.app/ 를 연다.
- `서버 중지`: 이 런처가 시작한 Open WebUI 서버를 중지한다.
- `설정`: 실행 명령, 호스트, 포트, 자동 브라우저 열기 옵션을 변경한다.

## 설치 및 모델 기능

`설치 및 모델` 탭에서 다음 기능을 사용할 수 있다.

### 가상환경 & 파이썬

- `Open WebUI 가상환경 설치 실행`: `C:\OpenWebUI` 폴더를 만들고 Python 3.11 우선, 없으면 Python 3.12로 `venv` 가상환경을 만든 뒤, 그 안에서 `python -m pip install open-webui`를 실행한다. 실행 명령은 `"C:\OpenWebUI\venv\Scripts\open-webui.exe" serve`로 저장된다.
- `python pip upgrade`: 새 CMD 창에서 `python.exe -m pip install --upgrade pip`를 실행한다.
- `설치 명령 복사`: CMD나 PowerShell에 붙여 넣을 수 있는 설치 명령을 복사한다.

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

    "C:\OpenWebUI\venv\Scripts\open-webui.exe" serve

`python pip upgrade` 버튼은 전역 Python의 pip만 업그레이드한다.

    python.exe -m pip install --upgrade pip

Open WebUI 설치에는 전용 가상환경 버튼을 사용하는 것이 더 안전하다.

## 사용 방법

### EXE 다운로드

[OpenWebUI-Local-AI-Launcher-Tabbed-v2.exe 다운로드](https://github.com/shoutjoy/openwebuiApp/raw/refs/heads/main/dist/OpenWebUI-Local-AI-Launcher-Tabbed-v2.exe)

### Python으로 실행

`run_launcher.bat`를 더블클릭한다.

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

## 주의

- Open WebUI의 실제 채팅 모델 선택은 브라우저에서 열린 Open WebUI 화면 안에서 진행한다.
- 이 런처의 모델 선택/저장은 로컬 런처 설정용이며, 필요한 모델을 Ollama에 설치하는 편의 기능이다.
- `ollama list`와 `ollama pull`을 사용하려면 Ollama가 먼저 설치되어 있어야 한다.
- CMD 창을 닫으면 Open WebUI 서버도 종료된다.
- 실행기 창을 닫아도 CMD 서버 창은 계속 실행된다.
