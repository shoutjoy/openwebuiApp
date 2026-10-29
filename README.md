# Joonghee Park PhD 's OpenWebUI Local AI v3.1.2

이 프로그램은 Windows와 macOS에서 Open WebUI를 로컬로 실행하는 Tkinter 런처이다. Open WebUI 설치와 Ollama 모델 확인 및 설치 기능을 함께 제공한다.

## macOS 실행

소스 코드가 있는 폴더에서 Tkinter가 포함된 Python으로 `python3 launcher.py`를 실행하고, **Mac 설치 및 모델** 탭을 사용한다. Windows용 EXE와 BAT 파일은 Mac에서 실행되지 않는다. 설치에는 Python 3.11 또는 3.12가 미리 설치되어 있어야 한다. `python3.11`을 먼저 찾고 없으면 `python3.12`를 사용한다.

- `가상환경 설치 실행`: `~/OpenWebUI/venv`를 만들고 pip와 Open WebUI를 설치한다. 설치가 완료되거나 실패하면 알림이 표시된다.
- `pip 업그레이드`: 이 가상환경의 pip를 업데이트한다.
- `가상환경 설치 확인`과 `가상환경에서 실행`: 설치 상태를 확인하고 서버를 시작한다. 서버가 준비되면 설정에 따라 브라우저가 열린다.
- `AI 모델 설치`: 별도로 설치한 Ollama를 사용하여 모델을 내려받는다. 설치된 모델 목록은 `설치 및 모델` 탭에서 확인할 수 있다.
- 설치 및 모델 작업 로그는 `~/OpenWebUIChatLauncher/operations.log`, 서버 로그는 `~/OpenWebUIChatLauncher/server.log`에 기록된다. 서버는 실행 탭의 `서버 중지` 버튼으로 중지한다.

macOS의 Python 설치에 Tkinter가 없다면 Tkinter를 포함한 Python을 설치해야 한다. Open WebUI 설치에는 인터넷 연결이 필요하다.

## Ollama 탭

`ollama serve` 실행 중 오류가 발생하면 Windows CMD에서 다음 명령을 순서대로 실행한다.

```cmd
set "OLLAMA_HOST=127.0.0.1:11434"
set "OLLAMA_ORIGINS=http://localhost:8080,http://127.0.0.1:8080,http://localhost:8000,http://127.0.0.1:8000,https://mdproviewer.vercel.app,http://127.0.0.1:8765"
ollama serve
```

포트가 이미 사용 중이라는 오류가 발생하면 기존 Ollama 앱이나 서버를 종료한 뒤 같은 CMD 창에서 다시 실행한다.

- Windows와 macOS 공식 데스크톱 앱 다운로드 링크 및 설치 확인을 제공한다. 설치 후 기존 Ollama 데스크톱 앱이 서버를 자동으로 실행한 경우, CORS 설정을 적용하려면 해당 앱을 먼저 종료한다.
- `서버 실행`은 입력한 `OLLAMA_ORIGINS`를 적용해 로컬 `127.0.0.1:11434`에서 Ollama를 시작한다. 허용할 웹 사이트의 Origin을 쉼표로 추가할 수 있으며, 변경 사항은 재시작할 때 적용된다. Windows PowerShell과 macOS 터미널 명령도 화면에 표시된다.
- 서버 표시등은 Ollama API가 응답하면 초록색, 서버가 정지하면 빨간색, 작업 중이거나 포트의 응답을 확인할 수 없으면 노란색으로 표시된다.
- 서버 중지와 재시작은 이 런처가 시작한 Ollama 프로세스에 적용된다. `기존 Ollama 서버 종료`는 11434 포트를 사용하는 외부 프로세스가 Ollama인지 확인한 후 종료한다. 다른 프로그램이 포트를 사용하면 종료하지 않는다. 데스크톱 앱이 서버를 자동으로 다시 실행하면 해당 앱을 직접 종료해야 한다. 런처를 닫으면 런처가 시작한 Ollama 서버도 종료된다. 외부 서버의 CORS 설정은 확인하거나 변경하지 않는다.
- 기본 모델은 `gemma4:e2b`다. 온라인 검색 결과에서 모델과 버전을 선택하고 `다운로드 / 설치`를 누르면 `ollama pull` 명령과 다운로드 진행 상황이 앱 내부 설치 터미널에 표시된다. `설치된 모델` 탭에서는 이미 내려받은 모델을 선택해 로딩할 수 있다. 로딩한 모델은 유휴 상태에서 5분 동안 유지되며, Open WebUI에서도 사용할 모델을 선택해야 한다. 온라인 목록과 버전 정보는 Ollama 웹사이트의 검색 결과 첫 페이지에서 가져온다.
- 서버 로그는 `OpenWebUIChatLauncher/ollama-server.log`, 모델 다운로드 로그는 `OpenWebUIChatLauncher/ollama-pull.log`에 저장된다. 이 폴더는 Windows에서 `%LOCALAPPDATA%`, macOS에서 사용자 홈 폴더 아래에 있다.

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
- `open-webui`: 설정한 Open WebUI 채팅 화면을 연다.
- `로컬 테스트 Chat`: 복사한 Ollama Say 채팅 화면을 브라우저에서 열고 로컬 Ollama 서버에 연결한다. 런처가 열려 있는 동안 `http://127.0.0.1:8768/`에서 사용하며, 기본 화면 구성에 사용하는 외부 CDN 라이브러리는 인터넷이 필요하다.
- `자동실행`: 체크하면 다음에 앱을 켤 때 Open WebUI 서버를 자동으로 실행한다. 전용 가상환경이 있으면 가상환경 실행을 우선 사용하고, 없으면 Local환경실행을 사용한다.
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

Git과 Tkinter가 포함된 Python을 설치한 뒤, 터미널에서 저장소를 복제하고 해당 폴더로 이동하여 실행한다.

```bash
git clone https://github.com/shoutjoy/openwebuiApp.git
cd openwebuiApp
python launcher.py
```

macOS에서 `python` 명령을 사용할 수 없다면 `python3 launcher.py`로 실행한다. Windows에서는 `run_launcher.bat`를 더블클릭해도 된다.

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

### Render 배포

Render에서는 Windows PC 제어 기능을 사용할 수 없으므로, 배포 모드는 학술 검색 Tool 코드 제공과 외부 학술 DB 검색 기능 중심으로 동작한다.

루트에 Render용 파일을 둔다.

    app.py
    requirements.txt
    render.yaml
    webapp_flask/
    openwebui_tools/
    openwebui_functions/

Render Dashboard에서 수동으로 만들 때는 다음 값을 사용한다.

    Language: Python 3
    Build Command: pip install -r requirements.txt
    Start Command: gunicorn app:app

`render.yaml`을 사용하는 Blueprint 배포도 가능하다. 이때 `OPENWEBUI_LAUNCHER_DEPLOY_MODE=1`이 자동 설정되어 로컬 Open WebUI 실행, CMD 실행, Windows 오른쪽 클릭 메뉴 등록 같은 기능은 안내 메시지만 반환한다.
- Windows 오른쪽 클릭 메뉴 등록/해제
- OpenWebUI와 MDpro 바로 열기
- OpenWebUI API 테스트 UI
- 학술 인용 가드 Function 코드 확인/복사

OpenWebUI API 테스트의 기본 호출 주소는 현재 설정된 Open WebUI 주소에 `/api/chat`을 붙여 사용한다. 다른 API 주소나 토큰이 필요하면 Flask 실행 전에 환경변수를 지정한다.

    set OPENWEBUI_CHAT_API_URL=http://localhost:8080/api/chat
    set OPENWEBUI_API_TOKEN=your_token_here
    python app.py

## Open WebUI 채팅용 학술 검색 Tool

`openwebui_tools\academic_verified_search_tool.py`는 Open WebUI의 Workspace Tool로 가져가서 사용할 수 있는 학술 검색 도구이다. 이 방식은 Open WebUI 채팅 입력창의 `+` 메뉴에서 켤 수 있어 별도 Flask 패널보다 실제 채팅 흐름에 더 잘 맞는다.

동작 방식:

1. 사용자가 Open WebUI 채팅 하단 `+` 메뉴에서 `Academic Verified Search` Tool을 켠다.
2. 논문, 연구, 인용, 참고문헌, DOI 같은 질문을 하면 모델이 Tool을 호출할 수 있다.
3. Tool은 Crossref, OpenAlex, Semantic Scholar, PubMed, arXiv에서 실제 메타데이터를 검색한다.
4. Tool은 `[C1]`, `[C2]` 형식의 검색 결과, APA 참고문헌, JSON 원본을 반환한다.
5. 모델은 Tool 반환값 밖의 참고문헌을 만들면 안 된다.

Open WebUI에 적용하는 순서:

1. Flask 웹앱의 `Open WebUI 채팅용 학술 검색 Tool` 패널에서 `Tool 보기`를 누른 뒤 `Tool 코드 복사`를 누른다.
2. Open WebUI에서 `Workspace > Tools`로 이동한다.
3. Create를 누르고 ID는 `academic_verified_search`, 이름은 `Academic Verified Search`로 입력한다.
4. 복사한 코드를 붙여넣고 저장한다.
5. 채팅 입력창 왼쪽 `+` 버튼을 누르고 Tools 목록에서 `Academic Verified Search`를 켠다.
6. 매번 켜기 싫으면 `Workspace > Models > 해당 모델 편집 > Tools`에서 이 Tool을 체크한다.

주의:

- Tool Calling은 Open WebUI의 Native Mode가 권장된다.
- 작은 로컬 모델은 Tool 호출 자체를 놓칠 수 있다. 이 경우 질문에 `Academic Verified Search 도구를 사용해서`라고 명시한다.
- Google Scholar는 공식 공개 API가 없어 자동화에는 기본 포함하지 않았다.

## 학술 인용 가드 Filter

`openwebui_functions\academic_citation_guard_filter.py`는 Open WebUI의 Filter Function으로 가져가서 사용할 수 있는 학술 인용 방지 플러그인 코드이다.

동작 방식:

1. 사용자가 논문, 연구, 인용, 참고문헌, DOI 같은 학술 질문을 하면 Semantic Scholar, arXiv, Crossref, OpenAlex에서 실제 메타데이터 후보를 검색한다.
2. 후보를 `[C1]`, `[C2]` 형식의 검증 출처 목록으로 모델 입력에 주입한다.
3. 모델에게 후보 목록 밖의 저자, 연도, DOI, 학술지명, 참고문헌을 생성하지 말라고 지시한다.
4. 답변에 후보 밖 DOI나 참고문헌 형식이 있으면 답변 끝에 검증 경고를 붙인다.

Open WebUI에 적용하는 순서:

1. Flask 웹앱의 `학술 인용 가드` 패널에서 `Function 보기`를 누른 뒤 `Function 코드 복사`를 누른다.
2. Open WebUI에서 Admin Panel 또는 Workspace의 Functions 화면으로 이동한다.
3. Create를 누르고 ID는 `academic_citation_guard`, 이름은 `Academic Citation Guard`로 입력한다.
4. 복사한 코드를 붙여넣고 저장한다. 코드에 `class Filter`가 있어 Filter Function으로 자동 인식된다.
5. Active를 켠다. 모든 모델에 적용하려면 Global을 켜고, 특정 모델만 적용하려면 Workspace > Models > 해당 모델 > Filters에서 선택한 뒤 Default Filters에도 추가한다.

주의:

- Google Scholar는 공식 공개 API가 없어 자동화에는 Semantic Scholar/arXiv/Crossref/OpenAlex가 더 안정적이다.
- 한국어 주제어만으로는 외부 메타데이터 검색 결과가 부족할 수 있다. 필요한 경우 영어 논문명, 핵심 키워드, DOI 일부를 함께 입력한다.
- 이 기능은 가짜 인용을 줄이는 장치이며, 최종 논문 제출 전에는 DOI 원문, Semantic Scholar, arXiv, Crossref, PubMed, OpenAlex에서 직접 재확인해야 한다.

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
