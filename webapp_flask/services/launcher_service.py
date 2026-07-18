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

from .integrations import DEFAULT_INTEGRATIONS


class LauncherWebService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._server_process: subprocess.Popen | None = None
        self._is_starting = False
        self._last_event = ""

    def get_config(self) -> dict[str, Any]:
        return launcher.load_config()

    def update_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            config = launcher.load_config()
            updated = {
                "command": str(payload.get("command", config["command"])).strip(),
                "venv_command": str(payload.get("venv_command", config["venv_command"])).strip(),
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

            launcher.save_config(updated)
            self._last_event = "설정을 저장했습니다."
            return {"ok": True, "config": updated, "message": self._last_event}

    def get_status(self) -> dict[str, Any]:
        config = launcher.load_config()
        found = launcher.find_open_webui_command()
        venv_ready = launcher.openwebui_venv_is_installed()
        check_host = self._check_host(config["host"])
        port = int(config["port"])
        running = launcher.port_is_open(check_host, port)
        server_url = self._server_url(config)
        context_menu = launcher.context_menu_is_registered()
        ollama_command = launcher.find_ollama_command()

        return {
            "ok": True,
            "app_name": launcher.APP_NAME,
            "app_version": launcher.APP_VERSION,
            "server_url": server_url,
            "host": config["host"],
            "port": port,
            "running": running,
            "starting": self._is_starting,
            "status_text": self._status_text(running),
            "local_openwebui_command": found,
            "local_ready": bool(found),
            "venv_ready": venv_ready,
            "ollama_command": ollama_command,
            "ollama_ready": bool(ollama_command),
            "context_menu_registered": context_menu,
            "selected_model": config.get("selected_model") or launcher.DEFAULT_MODEL_TO_PULL,
            "auto_start_server": bool(config.get("auto_start_server")),
            "auto_open_browser": bool(config.get("auto_open_browser")),
            "last_event": self._last_event,
            "managed_process_pid": self._server_process.pid if self._server_process else None,
        }

    def start_server(self, mode: str = "auto") -> dict[str, Any]:
        with self._lock:
            config = launcher.load_config()
            check_host = self._check_host(config["host"])
            port = int(config["port"])

            if launcher.port_is_open(check_host, port):
                self._last_event = "Open WebUI 서버가 이미 실행 중입니다."
                return {"ok": True, "already_running": True, "message": self._last_event, "url": self._server_url(config)}
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
        config = launcher.load_config()
        url = self._server_url(config)
        webbrowser.open(url)
        self._last_event = f"브라우저에서 {url} 을 열었습니다."
        return {"ok": True, "url": url, "message": self._last_event}

    def install_openwebui(self) -> dict[str, Any]:
        command = launcher.build_open_webui_install_command()
        config = launcher.load_config()
        config["venv_command"] = launcher.build_python311_openwebui_serve_command()
        launcher.save_config(config)
        try:
            process = launcher.start_cmd_window(command, "Install Open WebUI")
        except Exception as exc:
            self._last_event = f"설치 CMD 창을 시작하지 못했습니다: {exc}"
            return {"ok": False, "message": self._last_event}
        self._last_event = "Open WebUI 가상환경 설치 명령을 CMD 창에서 실행했습니다."
        return {"ok": True, "pid": process.pid, "command": command, "message": self._last_event}

    def upgrade_python_pip(self) -> dict[str, Any]:
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
        return {"ok": True, "command": launcher.build_open_webui_install_command()}

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
        return {"ok": True, "model": model_name, "command": f"{launcher.quote_cmd_arg(ollama_command)} pull {model_name}"}

    def get_context_menu_status(self) -> dict[str, Any]:
        registered = launcher.context_menu_is_registered()
        return {"ok": True, "registered": registered}

    def register_context_menu(self) -> dict[str, Any]:
        try:
            launcher.set_context_menu_registry()
        except Exception as exc:
            self._last_event = f"오른쪽 클릭 메뉴 등록에 실패했습니다: {exc}"
            return {"ok": False, "message": self._last_event}
        self._last_event = "Windows 오른쪽 클릭 메뉴에 앱 실행 항목을 등록했습니다."
        return {"ok": True, "registered": True, "message": self._last_event}

    def unregister_context_menu(self) -> dict[str, Any]:
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

    def open_integration(self, integration_id: str) -> dict[str, Any]:
        integrations = self.list_integrations()["integrations"]
        found = next((item for item in integrations if item["id"] == integration_id), None)
        if not found:
            return {"ok": False, "message": "알 수 없는 연동 항목입니다."}
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

    def auto_start_if_enabled(self) -> None:
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
            return str(config.get("venv_command") or launcher.build_python311_openwebui_serve_command()).strip(), "Open WebUI venv Server", "가상환경"

        if mode == "local":
            if not found:
                return None, "Open WebUI Server", "Local환경"
            return f"{launcher.quote_cmd_arg(found)} serve", "Open WebUI Server", "Local환경"

        command = str(config.get("command") or "").strip()
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
        if running:
            return "Open WebUI가 실행 중입니다."
        if self._is_starting:
            return "Open WebUI를 시작하고 있습니다. CMD 창을 확인하십시오."
        return "Open WebUI가 현재 실행 중이 아닙니다."

    def _server_url(self, config: dict[str, Any]) -> str:
        host = str(config["host"])
        browser_host = "localhost" if host in {"127.0.0.1", "0.0.0.0"} else host
        return f"http://{browser_host}:{int(config['port'])}/"

    def _check_host(self, host: str) -> str:
        return "127.0.0.1" if host == "0.0.0.0" else host
