# OpenWebUI Flask Web App

이 폴더는 기존 `launcher.py` tkinter 앱 기능을 브라우저 UI로 사용할 수 있게 만든 Flask 웹앱입니다.

## 실행

```bat
cd /d C:\CusorApps\openWebUi_app\OpenWebUI_Chat_Launcher_v3\OpenWebUI_Chat_Launcher\webapp_flask
python -m pip install -r requirements.txt
python app.py
```

브라우저에서 `http://127.0.0.1:8000`을 엽니다.

## OpenWebUI API 테스트

기본 API 주소는 현재 설정의 OpenWebUI URL 뒤에 `/api/chat`을 붙여 사용합니다.
다른 주소나 토큰이 필요하면 환경변수로 지정합니다.

```bat
set OPENWEBUI_CHAT_API_URL=http://localhost:8080/api/chat
set OPENWEBUI_API_TOKEN=your_token_here
python app.py
```

## 에디터 앱 추가

`services/integrations.py`의 `DEFAULT_INTEGRATIONS`에 항목을 추가하면 UI의 `에디터 연동` 영역에 자동 표시됩니다.
