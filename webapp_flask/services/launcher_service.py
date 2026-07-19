# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

import requests

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import launcher  # noqa: E402

from .academic_rag_service import AcademicRagService
from .integrations import DEFAULT_INTEGRATIONS


class LauncherWebService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._server_process: subprocess.Popen | None = None
        self._is_starting = False
        self._last_event = ""
        self._academic_rag = AcademicRagService()
        self._deploy_mode = self._is_deploy_mode()

    def get_config(self) -> dict[str, Any]:
        if self._deploy_mode:
            return launcher.load_config()
        return launcher.update_config_with_detected_runtime(launcher.load_config(), save=True)

    def detect_runtime(self) -> dict[str, Any]:
        if self._deploy_mode:
            config = launcher.load_config()
            self._last_event = "Render 배포 환경에서는 로컬 Python/Open WebUI 실행 파일을 탐색하지 않습니다."
            return {"ok": True, "detected": {}, "config": config, "message": self._last_event}
        config = launcher.update_config_with_detected_runtime(launcher.load_config(), save=True)
        detected = {
            "python_path": config.get("python_path", ""),
            "open_webui_path": config.get("open_webui_path", ""),
            "command": config.get("command", ""),
            "venv_command": config.get("venv_command", ""),
        }
        self._last_event = "Python/Open WebUI 실행 경로를 자동 탐색해 설정에 기록했습니다."
        return {"ok": True, "detected": detected, "config": config, "message": self._last_event}

    def update_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            config = launcher.load_config()
            updated = {
                "command": str(payload.get("command", config["command"])).strip(),
                "venv_command": str(payload.get("venv_command", config["venv_command"])).strip(),
                "python_path": str(payload.get("python_path", config.get("python_path", ""))).strip(),
                "open_webui_path": str(payload.get("open_webui_path", config.get("open_webui_path", ""))).strip(),
                "host": str(payload.get("host", config["host"])).strip() or "127.0.0.1",
                "port": int(payload.get("port", config["port"])),
                "auto_open_browser": bool(payload.get("auto_open_browser", config["auto_open_browser"])),
                "auto_start_server": bool(payload.get("auto_start_server", config["auto_start_server"])),
                "startup_timeout_seconds": int(
                    payload.get("startup_timeout_seconds", config["startup_timeout_seconds"])
                ),
                "selected_model": str(payload.get("selected_model", config.get("selected_model", ""))).strip(),
            }
            if not 1 <= updated["port"] <= 65535:
                raise ValueError("port must be between 1 and 65535")
            if updated["startup_timeout_seconds"] < 5:
                raise ValueError("startup_timeout_seconds must be 5 or more")

            updated["command"] = launcher.command_with_openwebui_port(updated["command"], updated["port"])
            updated["venv_command"] = launcher.command_with_openwebui_port(updated["venv_command"], updated["port"])
            launcher.save_config(updated)
            self._last_event = "설정을 저장했습니다."
            return {"ok": True, "config": updated, "message": self._last_event}

    def get_status(self) -> dict[str, Any]:
        config = launcher.load_config() if self._deploy_mode else launcher.update_config_with_detected_runtime(launcher.load_config(), save=True)
        found = config.get("open_webui_path") or launcher.find_open_webui_command()
        venv_ready = launcher.openwebui_venv_is_installed()
        check_host = self._check_host(config["host"])
        port = int(config["port"])
        running = False if self._deploy_mode else launcher.port_is_open(check_host, port)
        server_url = self._server_url(config)
        context_menu = launcher.context_menu_is_registered()
        ollama_command = "" if self._deploy_mode else launcher.find_ollama_command()

        return {
            "ok": True,
            "app_name": launcher.APP_NAME,
            "app_version": launcher.APP_VERSION,
            "deploy_mode": self._deploy_mode,
            "server_url": server_url,
            "host": config["host"],
            "port": port,
            "running": running,
            "starting": self._is_starting,
            "status_text": self._status_text(running),
            "local_openwebui_command": found,
            "python_path": config.get("python_path", ""),
            "open_webui_path": config.get("open_webui_path", ""),
            "local_ready": False if self._deploy_mode else bool(found),
            "venv_ready": False if self._deploy_mode else venv_ready,
            "ollama_command": ollama_command,
            "ollama_ready": bool(ollama_command),
            "context_menu_registered": False if self._deploy_mode else context_menu,
            "selected_model": config.get("selected_model") or launcher.DEFAULT_MODEL_TO_PULL,
            "auto_start_server": bool(config.get("auto_start_server")),
            "auto_open_browser": bool(config.get("auto_open_browser")),
            "last_event": self._last_event,
            "managed_process_pid": self._server_process.pid if self._server_process else None,
        }

    def start_server(self, mode: str = "auto") -> dict[str, Any]:
        if self._deploy_mode:
            return self._deployment_unavailable("Render 배포 환경에서는 서버 안에서 사용자의 PC에 있는 Open WebUI를 실행할 수 없습니다.")
        with self._lock:
            config = launcher.load_config()
            check_host = self._check_host(config["host"])
            port = int(config["port"])

            if launcher.port_is_open(check_host, port):
                self._last_event = "Open WebUI 서버가 이미 실행 중입니다."
                return {"ok": True, "already_running": True, "message": self._last_event, "url": self._server_url(config)}
            if not launcher.port_can_bind(config["host"], port):
                self._last_event = (
                    f"포트 {port}를 다른 프로그램이 사용 중이어서 Open WebUI를 시작하지 않았습니다. "
                    "기존 Open WebUI/CMD/브라우저 탭을 닫거나 설정에서 다른 포트를 사용하십시오."
                )
                return {"ok": False, "port_busy": True, "message": self._last_event, "url": self._server_url(config)}
            if self._is_starting:
                return {"ok": True, "starting": True, "message": "Open WebUI 서버를 이미 시작하고 있습니다."}

            command, title, resolved_mode = self._resolve_start_command(mode, config)
            if not command:
                return {
                    "ok": False,
                    "message": "실행 가능한 Open WebUI 설치를 찾지 못했습니다. 가상환경 설치 또는 설정의 실행 명령을 확인하십시오.",
                }

            self._is_starting = True
            self._last_event = f"{resolved_mode} 실행 명령을 시작했습니다."
            try:
                self._server_process = launcher.start_cmd_window(command, title)
            except Exception as exc:
                self._is_starting = False
                self._last_event = f"CMD 창을 시작하지 못했습니다: {exc}"
                return {"ok": False, "message": self._last_event}

            threading.Thread(
                target=self._wait_for_server,
                args=(config, self._server_process),
                daemon=True,
            ).start()
            return {
                "ok": True,
                "starting": True,
                "mode": resolved_mode,
                "pid": self._server_process.pid,
                "message": self._last_event,
                "url": self._server_url(config),
            }

    def stop_server(self) -> dict[str, Any]:
        if self._deploy_mode:
            return self._deployment_unavailable("Render 배포 환경에서는 로컬 Open WebUI 프로세스를 중지할 수 없습니다.")
        with self._lock:
            if self._server_process and self._server_process.poll() is None:
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(self._server_process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=0x08000000 if os.name == "nt" else 0,
                    )
                    self._server_process = None
                    self._is_starting = False
                    self._last_event = "이 웹앱에서 시작한 Open WebUI 서버를 중지했습니다."
                    return {"ok": True, "message": self._last_event}
                except Exception as exc:
                    self._last_event = f"서버 중지에 실패했습니다: {exc}"
                    return {"ok": False, "message": self._last_event}

            self._last_event = "이 웹앱에서 시작한 서버 프로세스가 없습니다."
            return {"ok": False, "message": self._last_event}

    def open_server_url(self) -> dict[str, Any]:
        if self._deploy_mode:
            return self._deployment_unavailable("Render 배포 환경에서는 서버가 사용자의 브라우저를 직접 열 수 없습니다.")
        config = launcher.load_config()
        url = self._server_url(config)
        webbrowser.open(url)
        self._last_event = f"브라우저에서 {url} 을 열었습니다."
        return {"ok": True, "url": url, "message": self._last_event}

    def install_openwebui(self) -> dict[str, Any]:
        if self._deploy_mode:
            return self._deployment_unavailable("Render 배포 환경에서는 Windows 가상환경 설치 명령을 실행할 수 없습니다.")
        command = launcher.build_open_webui_install_command()
        command_info = self.get_openwebui_install_command()
        config = launcher.load_config()
        config["venv_command"] = launcher.build_python311_openwebui_serve_command()
        launcher.save_config(config)
        try:
            process = launcher.start_cmd_window(command, "Install Open WebUI")
        except Exception as exc:
            self._last_event = f"설치 CMD 창을 시작하지 못했습니다: {exc}"
            return {"ok": False, "message": self._last_event}
        self._last_event = "Open WebUI 가상환경 설치 명령을 CMD 창에서 실행했습니다."
        return {
            "ok": True,
            "pid": process.pid,
            "command": command,
            "cmd_script": command_info["cmd_script"],
            "steps": command_info["steps"],
            "message": self._last_event,
        }

    def upgrade_python_pip(self) -> dict[str, Any]:
        if self._deploy_mode:
            return self._deployment_unavailable("Render 배포 환경에서는 사용자의 PC Python pip를 업그레이드할 수 없습니다.")
        command = launcher.build_python_pip_upgrade_command()
        try:
            process = launcher.start_cmd_window(command, "python pip upgrade")
        except Exception as exc:
            self._last_event = f"pip upgrade CMD 창을 시작하지 못했습니다: {exc}"
            return {"ok": False, "message": self._last_event}
        self._last_event = "python pip upgrade 명령을 CMD 창에서 실행했습니다."
        return {"ok": True, "pid": process.pid, "command": command, "message": self._last_event}

    def check_openwebui_venv(self) -> dict[str, Any]:
        paths = launcher.openwebui_venv_paths()
        checks = []
        missing = []
        for key, label in (
            ("root", "설치 폴더"),
            ("venv", "가상환경"),
            ("python", "Python 실행 파일"),
            ("activate", "활성화 스크립트"),
            ("open_webui", "Open WebUI 실행 파일"),
        ):
            exists = launcher.path_exists(paths[key])
            checks.append({"key": key, "label": label, "path": str(paths[key]), "exists": exists})
            if not exists:
                missing.append(label)

        ready = not missing
        if ready:
            config = launcher.load_config()
            config["venv_command"] = launcher.build_python311_openwebui_serve_command()
            launcher.save_config(config)
        return {"ok": True, "ready": ready, "checks": checks, "missing": missing}

    def get_openwebui_install_command(self) -> dict[str, Any]:
        steps = [
            {
                "title": "폴더 생성",
                "description": "가상환경을 설치할 C:\\OpenWebUI 폴더를 만듭니다.",
                "code": "\r\n".join(
                    [
                        "cd /d C:\\",
                        "if not exist OpenWebUI mkdir OpenWebUI",
                    ]
                ),
            },
            {
                "title": "Python 버전 확인",
                "description": "Open WebUI 설치에 맞는 Python 3.11을 먼저 찾고, 없으면 Python 3.12를 찾습니다.",
                "code": "\r\n".join(
                    [
                        "cd /d C:\\OpenWebUI",
                        'set "PY_CMD="',
                        'py -3.11 --version >nul 2>nul && set "PY_CMD=py -3.11"',
                        'if not defined PY_CMD (py -3.12 --version >nul 2>nul && set "PY_CMD=py -3.12")',
                        "if not defined PY_CMD echo [ERROR] Python 3.11 or 3.12 is required.",
                        "if not defined PY_CMD echo Install Python 3.11 64-bit with Python Launcher enabled.",
                        "if not defined PY_CMD py --list",
                    ]
                ),
            },
            {
                "title": "가상환경 생성",
                "description": "찾은 Python으로 C:\\OpenWebUI\\venv 가상환경을 만듭니다. 같은 CMD 창에서 이전 단계 다음에 실행합니다.",
                "code": "if defined PY_CMD %PY_CMD% -m venv venv",
            },
            {
                "title": "가상환경 활성화 및 pip 준비",
                "description": "가상환경을 활성화하고 pip, setuptools, wheel을 최신 상태로 준비합니다.",
                "code": "\r\n".join(
                    [
                        "if defined PY_CMD call venv\\Scripts\\activate.bat",
                        "if defined PY_CMD python --version",
                        "if defined PY_CMD python -m pip install --upgrade pip setuptools wheel",
                    ]
                ),
            },
            {
                "title": "Open WebUI 설치 확인",
                "description": "가상환경 안에 Open WebUI를 설치하고 설치 정보를 확인합니다.",
                "code": "\r\n".join(
                    [
                        "if defined PY_CMD python -m pip install open-webui",
                        "if defined PY_CMD python -m pip show open-webui",
                        "if defined PY_CMD echo.",
                        "if defined PY_CMD echo [Complete] C:\\OpenWebUI\\venv Open WebUI setup finished.",
                    ]
                ),
            },
        ]
        cmd_script = "\r\n".join(step["code"] for step in steps)
        return {
            "ok": True,
            "command": launcher.build_open_webui_install_command(),
            "cmd_script": cmd_script,
            "steps": steps,
        }

    def list_ollama_models(self) -> dict[str, Any]:
        ollama_command = launcher.find_ollama_command()
        if not ollama_command:
            return {
                "ok": False,
                "models": [],
                "popular_models": launcher.POPULAR_OLLAMA_MODELS,
                "message": "ollama 실행 파일을 찾지 못했습니다. Ollama 설치 후 다시 시도하십시오.",
            }
        try:
            output = launcher.run_ollama_list(ollama_command)
            models = launcher.parse_ollama_models(output)
        except Exception as exc:
            return {"ok": False, "models": [], "popular_models": launcher.POPULAR_OLLAMA_MODELS, "message": str(exc)}

        return {
            "ok": True,
            "models": models,
            "popular_models": launcher.POPULAR_OLLAMA_MODELS,
            "selected_model": launcher.load_config().get("selected_model") or launcher.DEFAULT_MODEL_TO_PULL,
            "command": ollama_command,
            "message": f"설치된 Ollama 모델 {len(models)}개를 찾았습니다." if models else "설치된 Ollama 모델이 없습니다.",
        }

    def save_selected_model(self, model_name: str) -> dict[str, Any]:
        model_name = model_name.strip()
        if not launcher.model_name_is_safe(model_name):
            return {"ok": False, "message": "모델명에는 영문, 숫자, ., _, -, /, : 문자만 사용할 수 있습니다."}
        config = launcher.load_config()
        config["selected_model"] = model_name
        launcher.save_config(config)
        self._last_event = f"선택 모델을 저장했습니다: {model_name}"
        return {"ok": True, "model": model_name, "message": self._last_event}

    def install_ollama_model(self, model_name: str) -> dict[str, Any]:
        if self._deploy_mode:
            return self._deployment_unavailable("Render 배포 환경에서는 사용자의 PC Ollama 모델을 설치할 수 없습니다.")
        command_payload = self.get_model_install_command(model_name)
        if not command_payload["ok"]:
            return command_payload
        try:
            process = launcher.start_cmd_window(command_payload["command"], "Install Ollama Model")
        except Exception as exc:
            self._last_event = f"모델 설치 CMD 창을 시작하지 못했습니다: {exc}"
            return {"ok": False, "message": self._last_event}
        self._last_event = f"Ollama 모델 설치 명령을 실행했습니다: {command_payload['model']}"
        return {"ok": True, "pid": process.pid, "command": command_payload["command"], "message": self._last_event}

    def get_model_install_command(self, model_name: str) -> dict[str, Any]:
        model_name = model_name.strip() or launcher.DEFAULT_MODEL_TO_PULL
        if not launcher.model_name_is_safe(model_name):
            return {"ok": False, "message": "모델명에는 영문, 숫자, ., _, -, /, : 문자만 사용할 수 있습니다."}
        ollama_command = launcher.find_ollama_command() or "ollama"
        command = f"{launcher.quote_cmd_arg(ollama_command)} pull {model_name}"
        model_base = model_name.split(":", 1)[0]
        library_url = launcher.OLLAMA_MODELS_URL
        model_url = f"{library_url}/{model_base}"
        steps = [
            {
                "title": "Ollama 모델 페이지 확인",
                "description": "Ollama 모델 페이지에서 설치할 모델 이름과 태그를 확인합니다. 예: llama3.1:8b",
                "code": f"start {model_url}",
            },
            {
                "title": "모델명 선택",
                "description": "웹앱의 모델명 입력칸에 설치할 모델명을 입력하거나 왼쪽 목록에서 선택합니다.",
                "code": model_name,
            },
            {
                "title": "CMD 설치 명령 복사",
                "description": "선택 모델 CMD 명령 복사 버튼으로 아래 명령을 복사합니다.",
                "code": command,
            },
            {
                "title": "Windows CMD에서 실행",
                "description": "Windows CMD 창을 열고 복사한 명령을 붙여넣은 뒤 Enter를 눌러 모델을 하나씩 설치합니다.",
                "code": command,
            },
            {
                "title": "설치된 모델 확인",
                "description": "설치가 끝나면 Ollama 모델 목록을 확인하고, 웹앱의 새로고침 버튼으로 목록을 다시 불러옵니다.",
                "code": f"{launcher.quote_cmd_arg(ollama_command)} list",
            },
        ]
        return {
            "ok": True,
            "model": model_name,
            "command": command,
            "library_url": library_url,
            "model_url": model_url,
            "steps": steps,
        }

    def get_context_menu_status(self) -> dict[str, Any]:
        if self._deploy_mode:
            return {"ok": True, "registered": False, "deploy_mode": True}
        registered = launcher.context_menu_is_registered()
        return {"ok": True, "registered": registered}

    def register_context_menu(self) -> dict[str, Any]:
        if self._deploy_mode:
            return self._deployment_unavailable("Render 배포 환경에서는 Windows 오른쪽 클릭 메뉴를 등록할 수 없습니다.")
        try:
            launcher.set_context_menu_registry()
        except Exception as exc:
            self._last_event = f"오른쪽 클릭 메뉴 등록에 실패했습니다: {exc}"
            return {"ok": False, "message": self._last_event}
        self._last_event = "Windows 오른쪽 클릭 메뉴에 앱 실행 항목을 등록했습니다."
        return {"ok": True, "registered": True, "message": self._last_event}

    def unregister_context_menu(self) -> dict[str, Any]:
        if self._deploy_mode:
            return self._deployment_unavailable("Render 배포 환경에서는 Windows 오른쪽 클릭 메뉴를 해제할 수 없습니다.")
        try:
            launcher.remove_context_menu_registry()
        except Exception as exc:
            self._last_event = f"오른쪽 클릭 메뉴 해제에 실패했습니다: {exc}"
            return {"ok": False, "message": self._last_event}
        self._last_event = "Windows 오른쪽 클릭 메뉴 등록을 해제했습니다."
        return {"ok": True, "registered": False, "message": self._last_event}

    def list_integrations(self) -> dict[str, Any]:
        config = launcher.load_config()
        integrations = []
        for integration in DEFAULT_INTEGRATIONS:
            item = integration.to_dict()
            if item["id"] == "openwebui":
                item["url"] = self._server_url(config)
            integrations.append(item)
        return {"ok": True, "integrations": integrations}

    def get_citation_guard_function(self) -> dict[str, Any]:
        path = ROOT_DIR / "openwebui_functions" / "academic_citation_guard_filter.py"
        content = path.read_text(encoding="utf-8")
        return {
            "ok": True,
            "id": "academic_citation_guard",
            "name": "Academic Citation Guard",
            "path": str(path),
            "content": content,
            "steps": [
                {
                    "title": "Function 코드 복사",
                    "description": "아래 Function 코드를 복사합니다. 이 코드는 Semantic Scholar/arXiv/Crossref/OpenAlex에서 실제 논문 메타데이터 후보를 가져오고, 후보 밖 인용에는 경고를 붙입니다.",
                },
                {
                    "title": "Open WebUI Functions 화면 열기",
                    "description": "Open WebUI에서 Admin Panel 또는 Workspace의 Functions 화면으로 이동한 뒤 Create를 누릅니다.",
                },
                {
                    "title": "Filter Function 생성",
                    "description": "ID는 academic_citation_guard, 이름은 Academic Citation Guard로 입력하고 복사한 코드를 붙여넣은 뒤 Save합니다. class Filter가 있어 Filter Function으로 자동 인식됩니다.",
                },
                {
                    "title": "활성화 및 적용",
                    "description": "Active를 켜고, 모든 모델에 강제하려면 Global을 켭니다. 특정 모델에만 쓰려면 Workspace > Models > 해당 모델 > Filters에서 선택하고 Default Filters에도 추가합니다.",
                },
                {
                    "title": "사용 확인",
                    "description": "논문, 연구, 참고문헌, DOI가 포함된 질문을 보낸 뒤 답변의 인용이 [C1] 같은 검증 후보 ID를 사용하거나, 후보가 없을 때 검증 불가라고 말하는지 확인합니다.",
                },
            ],
        }

    def get_academic_search_tool(self) -> dict[str, Any]:
        path = ROOT_DIR / "openwebui_tools" / "academic_verified_search_tool.py"
        content = path.read_text(encoding="utf-8")
        return {
            "ok": True,
            "id": "academic_verified_search",
            "name": "Academic Verified Search",
            "path": str(path),
            "content": content,
            "steps": [
                {
                    "title": "Workspace Tool 코드 복사",
                    "description": "아래 Tool 코드를 복사합니다. 이 코드는 Open WebUI 채팅 하단 + 메뉴에서 켤 수 있는 학술 검색 도구입니다.",
                },
                {
                    "title": "Open WebUI Tools 화면 열기",
                    "description": "Open WebUI에서 Workspace > Tools로 이동한 뒤 Create를 누릅니다.",
                },
                {
                    "title": "Tool 생성",
                    "description": "ID는 academic_verified_search, 이름은 Academic Verified Search로 입력하고 복사한 코드를 붙여넣은 뒤 Save합니다.",
                },
                {
                    "title": "채팅 하단에서 사용",
                    "description": "채팅 입력창 왼쪽 + 버튼을 누르고 Tools 목록에서 Academic Verified Search를 켭니다. 그 뒤 논문/참고문헌 질문을 하면 모델이 이 Tool을 호출할 수 있습니다.",
                },
                {
                    "title": "항상 적용",
                    "description": "Workspace > Models > 해당 모델 편집 > Tools에서 Academic Verified Search를 체크하면 해당 모델에 기본 Tool로 붙습니다. Tool Calling은 Native가 권장됩니다.",
                },
            ],
        }

    def open_integration(self, integration_id: str) -> dict[str, Any]:
        integrations = self.list_integrations()["integrations"]
        found = next((item for item in integrations if item["id"] == integration_id), None)
        if not found:
            return {"ok": False, "message": "알 수 없는 연동 항목입니다."}
        if self._deploy_mode:
            self._last_event = f"{found['name']} URL을 반환했습니다."
            return {"ok": True, "integration": found, "url": found["url"], "message": self._last_event}
        webbrowser.open(found["url"])
        self._last_event = f"{found['name']} 을 열었습니다."
        return {"ok": True, "integration": found, "message": self._last_event}

    def ask_openwebui(self, message: str) -> dict[str, Any]:
        message = message.strip()
        if not message:
            return {"ok": False, "message": "메시지를 입력하십시오."}

        config = launcher.load_config()
        api_url = os.environ.get("OPENWEBUI_CHAT_API_URL") or f"{self._server_url(config).rstrip('/')}/api/chat"
        headers = {"Content-Type": "application/json"}
        token = os.environ.get("OPENWEBUI_API_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        payload = {"message": message, "stream": False}
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            return {
                "ok": False,
                "message": f"OpenWebUI API 호출에 실패했습니다: {exc}",
                "api_url": api_url,
            }

        reply = data.get("response") or data.get("reply") or data.get("message") or data
        return {"ok": True, "reply": reply, "api_url": api_url}

    def ask_academic_rag(self, question: str, max_results: int = 8) -> dict[str, Any]:
        if self._deploy_mode:
            max_results = max(1, min(int(max_results or 8), 12))
            try:
                works = self._academic_rag.search(question, max_results=max_results)
                answer = self._academic_rag._build_deterministic_summary(question, works)
                answer = self._academic_rag._append_verified_references(answer, works)
                return {
                    "ok": True,
                    "answer": answer,
                    "sources": [work.to_dict() for work in works],
                    "formatted_results": self._academic_rag.format_search_results(question, works),
                    "copy_prompt": self._academic_rag.build_literature_review_prompt(question, works),
                    "model": "deterministic-render-summary",
                    "deploy_mode": True,
                }
            except Exception as exc:
                return {"ok": False, "message": f"학술 RAG 처리에 실패했습니다: {exc}"}
        config = launcher.load_config()
        model = str(config.get("selected_model") or launcher.DEFAULT_MODEL_TO_PULL).strip()
        if not launcher.model_name_is_safe(model):
            model = launcher.DEFAULT_MODEL_TO_PULL
        max_results = max(1, min(int(max_results or 8), 12))
        try:
            result = self._academic_rag.answer(question, model=model, max_results=max_results)
        except requests.RequestException as exc:
            return {
                "ok": False,
                "message": f"Ollama 모델 호출에 실패했습니다. Ollama가 실행 중인지, 모델({model})이 설치되어 있는지 확인하십시오: {exc}",
            }
        except Exception as exc:
            return {"ok": False, "message": f"학술 RAG 처리에 실패했습니다: {exc}"}
        return result

    def search_academic_sources(self, query: str, max_results: int = 10) -> dict[str, Any]:
        max_results = max(1, min(int(max_results or 10), 20))
        try:
            return self._academic_rag.search_package(query, max_results=max_results)
        except Exception as exc:
            return {"ok": False, "message": f"학술 검색 결과 생성에 실패했습니다: {exc}"}

    def auto_start_if_enabled(self) -> None:
        if self._deploy_mode:
            return
        config = launcher.load_config()
        if config.get("auto_start_server"):
            self.start_server("auto")

    def _resolve_start_command(self, mode: str, config: dict[str, Any]) -> tuple[str | None, str, str]:
        mode = mode.lower().strip()
        found = launcher.find_open_webui_command()
        venv_ready = launcher.openwebui_venv_is_installed()

        if mode in {"auto", ""}:
            if venv_ready:
                mode = "venv"
            elif found:
                mode = "local"
            else:
                mode = "custom"

        if mode == "venv":
            if not venv_ready:
                return None, "Open WebUI venv Server", "가상환경"
            command = str(config.get("venv_command") or launcher.build_python311_openwebui_serve_command()).strip()
            return launcher.command_with_openwebui_port(command, int(config["port"])), "Open WebUI venv Server", "가상환경"

        if mode == "local":
            if not found:
                return None, "Open WebUI Server", "Local환경"
            command = f"{launcher.quote_cmd_arg(found)} serve"
            return launcher.command_with_openwebui_port(command, int(config["port"])), "Open WebUI Server", "Local환경"

        command = str(config.get("command") or "").strip()
        command = launcher.command_with_openwebui_port(command, int(config["port"]))
        return (command or None), "Open WebUI Server", "사용자 설정"

    def _wait_for_server(self, config: dict[str, Any], process: subprocess.Popen) -> None:
        check_host = self._check_host(config["host"])
        port = int(config["port"])
        timeout = int(config.get("startup_timeout_seconds") or 180)
        started_at = time.time()

        while time.time() - started_at < timeout:
            if launcher.port_is_open(check_host, port):
                with self._lock:
                    self._is_starting = False
                    self._last_event = "Open WebUI 서버가 준비되었습니다."
                if config.get("auto_open_browser", True):
                    webbrowser.open(self._server_url(config))
                return

            if process.poll() is not None:
                with self._lock:
                    self._is_starting = False
                    self._last_event = "Open WebUI 서버 프로세스가 종료되었습니다. CMD 창의 오류 메시지를 확인하십시오."
                return

            time.sleep(1)

        with self._lock:
            self._is_starting = False
            self._last_event = "설정된 대기시간 안에 Open WebUI 포트가 열리지 않았습니다."

    def _status_text(self, running: bool) -> str:
        if self._deploy_mode:
            return "비활성화"
        if running:
            return "활성화"
        if self._is_starting:
            return "활성화 중"
        return "비활성화"

    def _server_url(self, config: dict[str, Any]) -> str:
        host = str(config["host"])
        browser_host = "localhost" if host in {"127.0.0.1", "0.0.0.0"} else host
        return f"http://{browser_host}:{int(config['port'])}/"

    def _check_host(self, host: str) -> str:
        return "127.0.0.1" if host == "0.0.0.0" else host

    def _is_deploy_mode(self) -> bool:
        value = os.environ.get("OPENWEBUI_LAUNCHER_DEPLOY_MODE", "")
        if value.lower() in {"1", "true", "yes", "on"}:
            return True
        return os.environ.get("RENDER", "").lower() == "true"

    def _deployment_unavailable(self, message: str) -> dict[str, Any]:
        self._last_event = message
        return {"ok": False, "deploy_mode": True, "message": message}
