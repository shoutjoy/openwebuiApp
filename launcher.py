# -*- coding: utf-8 -*-
"""
Open WebUI Chat Launcher
- Open WebUI를 설치하거나 실행
- 별도의 CMD 창에서 `open-webui serve` 실행 상태를 표시
- localhost:8080 준비 후 브라우저 자동 열기
- Ollama에 설치된 모델 확인 및 모델 설치 명령 실행
"""

from __future__ import annotations

import json
import os
import re
import shlex
import signal
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlencode

import ollama_manager

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ImportError:
    class _MissingTkModule:
        class Tk:
            pass

        class Toplevel:
            pass

        class Event:
            pass

        END = "end"

        def __getattr__(self, name):
            raise RuntimeError("tkinter is not available in this Python environment.")

    tk = _MissingTkModule()
    messagebox = _MissingTkModule()
    ttk = _MissingTkModule()

try:
    import winreg
except ImportError:
    winreg = None

APP_NAME = "Joonghee Park PhD 's OpenWebUI Local AI"
APP_VERSION = "3.1.2"

APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "OpenWebUIChatLauncher"
CONFIG_FILE = APP_DIR / "settings.json"

CREATE_NEW_CONSOLE = 0x00000010 if os.name == "nt" else 0

DEFAULT_CONFIG = {
    "command": "open-webui serve",
    "venv_command": r"cd /d C:\OpenWebUI && call venv\Scripts\activate.bat && open-webui serve --port 8080",
    "python_path": "",
    "open_webui_path": "",
    "host": "127.0.0.1",
    "port": 8080,
    "auto_open_browser": True,
    "auto_start_server": False,
    "startup_timeout_seconds": 180,
    "selected_model": "",
}

OLLAMA_MODELS_URL = "https://ollama.com/library"
HUGGING_FACE_MODELS_URL = "https://huggingface.co/models"
MDPRO_URL = "https://mdproviewer.vercel.app/"
DEFAULT_MODEL_TO_PULL = "gemma4:e2b"
LEGACY_DIRECT_VENV_COMMAND = r'"C:\OpenWebUI\venv\Scripts\open-webui.exe" serve'
CONTEXT_MENU_KEY_NAME = "OpenWebUILocalAILauncher"
CONTEXT_MENU_LABEL = "Joonghee Park PhD's OpenWebUI Local AI 실행"
CONTEXT_MENU_REGISTRY_KEYS = [
    rf"Software\Classes\DesktopBackground\Shell\{CONTEXT_MENU_KEY_NAME}",
    rf"Software\Classes\Directory\Background\shell\{CONTEXT_MENU_KEY_NAME}",
    rf"Software\Classes\Directory\shell\{CONTEXT_MENU_KEY_NAME}",
]

POPULAR_OLLAMA_MODELS = [
    "gemma4:e2b",
    "llama3.1:8b",
    "llama3.2:3b",
    "qwen2.5:7b",
    "gemma2:9b",
    "mistral:7b",
    "deepseek-r1:7b",
]


def ensure_app_dir() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    ensure_app_dir()
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        config = {**DEFAULT_CONFIG, **loaded}
        if str(config.get("command", "")).strip() == str(config.get("venv_command", "")).strip():
            config["command"] = DEFAULT_CONFIG["command"]
        if str(config.get("command", "")).strip() == LEGACY_DIRECT_VENV_COMMAND:
            config["command"] = DEFAULT_CONFIG["command"]
        if str(config.get("venv_command", "")).strip() == LEGACY_DIRECT_VENV_COMMAND:
            config["venv_command"] = DEFAULT_CONFIG["venv_command"]
        return config
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    ensure_app_dir()
    CONFIG_FILE.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def port_is_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def port_can_bind(host: str, port: int) -> bool:
    bind_host = "0.0.0.0" if host in {"", "0.0.0.0", "127.0.0.1", "localhost"} else host
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((bind_host, int(port)))
        return True
    except OSError:
        return False


def start_cmd_window(command: str, title: str) -> subprocess.Popen:
    if sys.platform == "darwin":
        ensure_app_dir()
        log_path = APP_DIR / ("server.log" if "Server" in title else "operations.log")
        env = os.environ.copy()
        env["PATH"] = ("/opt/homebrew/bin:/usr/local/bin:"
                       "/Library/Frameworks/Python.framework/Versions/3.11/bin:"
                       "/Library/Frameworks/Python.framework/Versions/3.12/bin:" + env.get("PATH", ""))
        with log_path.open("a", encoding="utf-8") as log:
            return subprocess.Popen(["/bin/sh", "-c", command], stdout=log,
                                    stderr=subprocess.STDOUT, cwd=str(Path.home()),
                                    env=env, start_new_session=True)
    cmd_line = f'title {title} && echo [{APP_NAME}] {title} && {command}'
    return subprocess.Popen(
        ["cmd.exe", "/v:on", "/k", cmd_line],
        creationflags=CREATE_NEW_CONSOLE,
        cwd=str(Path.home()),
    )


def find_python_command() -> str | None:
    if shutil.which("py"):
        return "py"
    if shutil.which("python"):
        return "python"

    exe_name = Path(sys.executable).name.lower()
    if exe_name.startswith("python"):
        return f'"{sys.executable}"'

    return None


def build_open_webui_install_command() -> str:
    return (
        r"cd /d C:\ && "
        r"if not exist OpenWebUI mkdir OpenWebUI && "
        r"cd /d C:\OpenWebUI && "
        r'set "PY_CMD=" && '
        r'(py -3.11 --version >nul 2>nul && set "PY_CMD=py -3.11") & '
        r'if not defined PY_CMD (py -3.12 --version >nul 2>nul && set "PY_CMD=py -3.12") & '
        r"if not defined PY_CMD (echo [ERROR] Python 3.11 or 3.12 is required. & "
        r"echo Install Python 3.11 64-bit with Python Launcher enabled. & "
        r"py --list & exit /b 1) & "
        r"echo Using !PY_CMD! && "
        r"!PY_CMD! -m venv venv && "
        r"call venv\Scripts\activate.bat && "
        r"python --version && "
        r"python -m pip install --upgrade pip setuptools wheel && "
        r"python -m pip install open-webui && "
        r"python -m pip show open-webui && "
        r"echo. && "
        r"echo [Complete] C:\OpenWebUI\venv Open WebUI setup finished."
    )


def mac_install_command() -> str:
    return (
        'set -e; mkdir -p "$HOME/OpenWebUI"; cd "$HOME/OpenWebUI"; '
        'if command -v python3.11 >/dev/null 2>&1; then PY=python3.11; '
        'elif command -v python3.12 >/dev/null 2>&1; then PY=python3.12; '
        'else echo "Python 3.11 or 3.12 is required"; exit 1; fi; '
        '"$PY" -m venv venv; venv/bin/python -m pip install --upgrade pip setuptools wheel; '
        'venv/bin/python -m pip install open-webui; venv/bin/python -m pip show open-webui'
    )


def mac_serve_command() -> str:
    return 'cd "$HOME/OpenWebUI" && exec ./venv/bin/open-webui serve --port 8080'


def build_python_pip_upgrade_command() -> str:
    return "python.exe -m pip install --upgrade pip"


def build_python311_openwebui_setup_command() -> str:
    return build_open_webui_install_command()


def build_python311_openwebui_serve_command() -> str:
    if sys.platform == "darwin":
        return mac_serve_command()
    return r"cd /d C:\OpenWebUI && call venv\Scripts\activate.bat && open-webui serve --port 8080"


def flask_webapp_batch_path() -> Path:
    if getattr(sys, "frozen", False):
        candidates = [
            Path(sys.executable).resolve().parent.parent / "webapp_flask" / "run_flask_webapp.bat",
            Path(sys.executable).resolve().parent / "webapp_flask" / "run_flask_webapp.bat",
        ]
    else:
        candidates = [Path(__file__).resolve().parent / "webapp_flask" / "run_flask_webapp.bat"]

    candidates.append(
        Path(r"C:\CusorApps\openWebUi_app\OpenWebUI_Chat_Launcher_v3\OpenWebUI_Chat_Launcher\webapp_flask\run_flask_webapp.bat")
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def command_with_openwebui_port(command: str, port: int) -> str:
    command = str(command or "").strip()
    if not command:
        return command
    if re.search(r"(^|\s)--port\s+\d+", command):
        return re.sub(r"(^|\s)--port\s+\d+", rf"\1--port {int(port)}", command, count=1)
    if re.search(r"(^|\s)--port=\d+", command):
        return re.sub(r"(^|\s)--port=\d+", rf"\1--port={int(port)}", command, count=1)
    lowered = command.lower()
    if " serve" in lowered and ("open-webui" in lowered or "open_webui" in lowered):
        return f"{command} --port {int(port)}"
    return command


def openwebui_venv_paths() -> dict[str, Path]:
    if sys.platform == "darwin":
        root = Path.home() / "OpenWebUI"
        venv = root / "venv"
        return {"root": root, "venv": venv, "python": venv / "bin/python",
                "activate": venv / "bin/activate", "open_webui": venv / "bin/open-webui"}
    root = Path("C:/OpenWebUI")
    venv = root / "venv"
    scripts = venv / "Scripts"
    return {
        "root": root,
        "venv": venv,
        "python": scripts / "python.exe",
        "activate": scripts / "activate.bat",
        "open_webui": scripts / "open-webui.exe",
    }


def path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def openwebui_venv_is_installed() -> bool:
    paths = openwebui_venv_paths()
    return all(
        path_exists(paths[key])
        for key in ("venv", "python", "activate", "open_webui")
    )


def find_ollama_command() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    if sys.platform == "darwin":
        return next((str(p) for p in (Path('/opt/homebrew/bin/ollama'), Path('/usr/local/bin/ollama')) if p.is_file()), None)

    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    candidates = [
        local_app_data / "Programs" / "Ollama" / "ollama.exe",
        local_app_data / "Ollama" / "ollama.exe",
        Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Ollama" / "ollama.exe",
        Path(os.environ.get("ProgramW6432", "")) / "Ollama" / "ollama.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Ollama" / "ollama.exe",
    ]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            if candidate.name.lower() == "ollama.exe":
                return str(candidate)
            continue
    return None


def parse_ollama_models(output: str) -> list[str]:
    models: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.upper().startswith("NAME "):
            continue
        name = stripped.split()[0]
        if name and name not in models:
            models.append(name)
    return models


def run_ollama_list(ollama_command: str) -> str:
    try:
        return subprocess.check_output(
            [ollama_command, "list"],
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.STDOUT,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
    except OSError:
        if os.name != "nt":
            raise
        cmd_line = f'"{ollama_command}" list'
        return subprocess.check_output(
            ["cmd.exe", "/c", cmd_line],
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.STDOUT,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )


def quote_cmd_arg(value: str) -> str:
    if os.name != "nt":
        return shlex.quote(value)
    special_chars = set(" &()[]{}^=;!'+,`")
    if any(char.isspace() or char in special_chars for char in value):
        return f'"{value}"'
    return value


def get_launcher_command() -> str:
    if getattr(sys, "frozen", False):
        return quote_cmd_arg(sys.executable)

    script_path = Path(__file__).resolve()
    return f"{quote_cmd_arg(sys.executable)} {quote_cmd_arg(str(script_path))}"


def get_launcher_icon_path() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return str(Path(__file__).resolve())


def registry_tree_exists(subkey: str) -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey):
            return True
    except OSError:
        return False


def context_menu_is_registered() -> bool:
    return any(registry_tree_exists(subkey) for subkey in CONTEXT_MENU_REGISTRY_KEYS)


def set_context_menu_registry() -> None:
    if winreg is None:
        raise RuntimeError("Windows registry is not available.")

    launcher_command = get_launcher_command()
    icon_path = get_launcher_icon_path()
    for subkey in CONTEXT_MENU_REGISTRY_KEYS:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, subkey) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, CONTEXT_MENU_LABEL)
            winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon_path)
            winreg.SetValueEx(key, "Position", 0, winreg.REG_SZ, "Top")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, subkey + r"\command") as command_key:
            winreg.SetValueEx(command_key, "", 0, winreg.REG_SZ, launcher_command)


def delete_registry_tree(root, subkey: str) -> None:
    if winreg is None:
        return
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            while True:
                try:
                    child_name = winreg.EnumKey(key, 0)
                except OSError:
                    break
                delete_registry_tree(root, subkey + "\\" + child_name)
        winreg.DeleteKey(root, subkey)
    except FileNotFoundError:
        return


def remove_context_menu_registry() -> None:
    if winreg is None:
        raise RuntimeError("Windows registry is not available.")
    for subkey in CONTEXT_MENU_REGISTRY_KEYS:
        delete_registry_tree(winreg.HKEY_CURRENT_USER, subkey)


def model_name_is_safe(model_name: str) -> bool:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/:")
    return bool(model_name) and all(char in allowed for char in model_name)


def find_open_webui_command() -> str | None:
    """PATH 및 일반적인 Python Scripts 위치에서 open-webui.exe를 찾는다."""
    found = shutil.which("open-webui")
    if found:
        return found

    candidates: list[Path] = []

    # 현재 Python 환경
    candidates.append(Path(sys.executable).parent / "Scripts" / "open-webui.exe")
    candidates.append(Path(sys.executable).parent / "open-webui.exe")

    # 사용자 Python 설치 위치
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    py_root = local_app_data / "Programs" / "Python"
    if py_root.exists():
        for folder in sorted(py_root.glob("Python*"), reverse=True):
            candidates.append(folder / "Scripts" / "open-webui.exe")

    # pip --user 설치 위치
    appdata = Path(os.environ.get("APPDATA", ""))
    python_user = appdata / "Python"
    if python_user.exists():
        for scripts in python_user.glob("Python*/Scripts"):
            candidates.append(scripts / "open-webui.exe")

    # 이전에 제작한 실행기의 가상환경
    candidates.extend([
        local_app_data / "OpenWebUILauncher" / "venv" / "Scripts" / "open-webui.exe",
        local_app_data / "OpenWebUIEasyLauncher" / "venv" / "Scripts" / "open-webui.exe",
    ])

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    return None


def find_python_executable(open_webui_command: str | None = None) -> str | None:
    """Open WebUI 실행 파일 또는 일반 설치 위치에서 python.exe를 찾는다."""
    if open_webui_command:
        open_webui_path = Path(open_webui_command)
        scripts_dir = open_webui_path.parent
        candidates = [
            scripts_dir.parent / "python.exe",
            scripts_dir.parent / "pythonw.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)

    exe_name = Path(sys.executable).name.lower()
    if exe_name.startswith("python") and Path(sys.executable).is_file():
        return str(Path(sys.executable))

    found = shutil.which("python")
    if found:
        return found

    candidates: list[Path] = []
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    py_root = local_app_data / "Programs" / "Python"
    if py_root.exists():
        for folder in sorted(py_root.glob("Python*"), reverse=True):
            candidates.append(folder / "python.exe")

    for root_env in ("PROGRAMFILES", "ProgramW6432", "PROGRAMFILES(X86)"):
        root = Path(os.environ.get(root_env, ""))
        if root.exists():
            candidates.extend(sorted((root / "Python").glob("Python*/python.exe"), reverse=True))

    if winreg is not None:
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, r"Software\Python\PythonCore") as root_key:
                    index = 0
                    while True:
                        try:
                            version = winreg.EnumKey(root_key, index)
                        except OSError:
                            break
                        index += 1
                        try:
                            with winreg.OpenKey(root_key, version + r"\InstallPath") as install_key:
                                install_path, _ = winreg.QueryValueEx(install_key, "")
                                candidates.append(Path(str(install_path)) / "python.exe")
                        except OSError:
                            continue
            except OSError:
                continue

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    return None


def detect_openwebui_runtime(port: int = 8080) -> dict[str, str]:
    open_webui_path = find_open_webui_command() or ""
    python_path = find_python_executable(open_webui_path) or ""
    command = ""
    if open_webui_path:
        command = command_with_openwebui_port(f"{quote_cmd_arg(open_webui_path)} serve", int(port))
    return {
        "python_path": python_path,
        "open_webui_path": open_webui_path,
        "command": command,
    }


def update_config_with_detected_runtime(config: dict, save: bool = False) -> dict:
    updated = dict(config)
    port = int(updated.get("port") or DEFAULT_CONFIG["port"])
    detected = detect_openwebui_runtime(port)
    if detected["python_path"]:
        updated["python_path"] = detected["python_path"]
    if detected["open_webui_path"]:
        updated["open_webui_path"] = detected["open_webui_path"]
        updated["command"] = detected["command"]
    if save:
        save_config(updated)
    return updated


class SettingsDialog(tk.Toplevel):
    def __init__(self, master: "LauncherApp", config: dict):
        super().__init__(master)
        self.title("실행 설정")
        self.geometry("720x430")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.result: dict | None = None

        self.command_var = tk.StringVar(value=str(config["command"]))
        self.host_var = tk.StringVar(value=str(config["host"]))
        self.port_var = tk.StringVar(value=str(config["port"]))
        self.browser_var = tk.BooleanVar(value=bool(config["auto_open_browser"]))
        self.timeout_var = tk.StringVar(value=str(config["startup_timeout_seconds"]))

        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="Open WebUI 실행 설정",
            font=("맑은 고딕", 16, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            outer,
            text=(
                "이미 설치와 연결 설정이 완료된 환경을 기준으로 한다. "
                "일반적으로 실행 명령은 open-webui serve 그대로 사용하면 된다."
            ),
            wraplength=670,
            justify="left",
        ).pack(anchor="w", pady=(4, 18))

        form = ttk.Frame(outer)
        form.pack(fill="x")

        ttk.Label(form, text="실행 명령", width=14).grid(row=0, column=0, sticky="w", pady=7)
        ttk.Entry(form, textvariable=self.command_var).grid(
            row=0, column=1, sticky="ew", pady=7
        )
        ttk.Button(form, text="자동 찾기", command=self.auto_find).grid(
            row=0, column=2, padx=(8, 0), pady=7
        )

        ttk.Label(form, text="호스트", width=14).grid(row=1, column=0, sticky="w", pady=7)
        ttk.Entry(form, textvariable=self.host_var).grid(
            row=1, column=1, sticky="ew", pady=7
        )

        ttk.Label(form, text="포트", width=14).grid(row=2, column=0, sticky="w", pady=7)
        ttk.Entry(form, textvariable=self.port_var).grid(
            row=2, column=1, sticky="ew", pady=7
        )

        ttk.Label(form, text="시작 대기시간", width=14).grid(row=3, column=0, sticky="w", pady=7)
        ttk.Entry(form, textvariable=self.timeout_var).grid(
            row=3, column=1, sticky="ew", pady=7
        )
        ttk.Label(form, text="초").grid(row=3, column=2, sticky="w", padx=(8, 0))

        ttk.Checkbutton(
            form,
            text="서버 준비 후 브라우저 자동 열기",
            variable=self.browser_var,
        ).grid(row=4, column=1, sticky="w", pady=(10, 0))

        form.columnconfigure(1, weight=1)

        help_box = ttk.LabelFrame(outer, text="설정 예시", padding=10)
        help_box.pack(fill="x", pady=(18, 0))
        ttk.Label(
            help_box,
            text=(
                "기본 pip 설치:  open-webui serve\n"
                "특정 경로 사용:  C:\\경로\\Scripts\\open-webui.exe serve\n"
                "모듈 실행 방식:  C:\\Python311\\python.exe -m open_webui serve"
            ),
            justify="left",
        ).pack(anchor="w")

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", side="bottom", pady=(18, 0))
        ttk.Button(buttons, text="취소", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="저장", command=self.save).pack(
            side="right", padx=(0, 8)
        )

    def auto_find(self) -> None:
        found = find_open_webui_command()
        if found:
            self.command_var.set(f'"{found}" serve')
            messagebox.showinfo(APP_NAME, f"Open WebUI 실행 파일을 찾았습니다.\n\n{found}")
        else:
            messagebox.showwarning(
                APP_NAME,
                "open-webui 실행 파일을 자동으로 찾지 못했습니다.\n"
                "기본 명령인 open-webui serve를 그대로 사용하거나 경로를 직접 입력하십시오.",
            )

    def save(self) -> None:
        command = self.command_var.get().strip()
        host = self.host_var.get().strip()
        if not command:
            messagebox.showwarning(APP_NAME, "실행 명령을 입력하십시오.")
            return
        if not host:
            messagebox.showwarning(APP_NAME, "호스트를 입력하십시오.")
            return
        try:
            port = int(self.port_var.get().strip())
            timeout = int(self.timeout_var.get().strip())
            if not (1 <= port <= 65535):
                raise ValueError
            if timeout < 10:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                APP_NAME,
                "포트는 1~65535, 시작 대기시간은 10초 이상의 숫자로 입력하십시오.",
            )
            return

        self.result = {
            "command": command,
            "host": host,
            "port": port,
            "auto_open_browser": self.browser_var.get(),
            "startup_timeout_seconds": timeout,
        }
        self.destroy()


class LauncherApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.config_data = load_config()
        self.server_process: subprocess.Popen | None = None
        self.is_starting = False
        self.available_models: list[str] = []
        self.internal_open_webui_command: str | None = None
        self.venv_open_webui_ready = False
        self.auto_start_attempted = False
        self.ollama_manager = ollama_manager.OllamaManager(APP_DIR)
        self.ollama_pull_process: subprocess.Popen | None = None
        self.ollama_busy = False
        self.ollama_loading = False
        self.ollama_status_generation = 0

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("920x850")
        self.minsize(860, 780)
        self.resizable(True, True)

        self.status_var = tk.StringVar(value="Open WebUI 상태를 확인하고 있습니다.")
        self.url_var = tk.StringVar()
        self.auto_start_var = tk.BooleanVar(value=bool(self.config_data.get("auto_start_server")))
        self.auto_start_status_var = tk.StringVar(value="")
        self.context_menu_status_var = tk.StringVar(value="")
        selected_model = str(self.config_data.get("selected_model") or DEFAULT_MODEL_TO_PULL)
        self.model_var = tk.StringVar(value=selected_model)
        self.model_status_var = tk.StringVar(value="Ollama에 설치된 모델을 자동으로 찾고 있습니다.")
        self.install_command_var = tk.StringVar(value="Open WebUI 전용 가상환경 설치 명령")
        self.model_command_var = tk.StringVar()
        self.ollama_model_var = tk.StringVar(value=DEFAULT_MODEL_TO_PULL)
        self.ollama_search_var = tk.StringVar()
        self.ollama_origins_var = tk.StringVar(value=str(self.config_data.get("ollama_origins") or ollama_manager.DEFAULT_ORIGINS))
        self.ollama_server_status_var = tk.StringVar(value="Ollama 상태 확인 중")
        self.ollama_action_status_var = tk.StringVar(value="설치할 모델을 입력하거나 검색하십시오.")
        self.ollama_command_display_var = tk.StringVar()
        self.model_var.trace_add("write", lambda *_: self.update_model_command())

        self._build_ui()
        self.update_model_command()
        self.update_context_menu_status()
        self.after(300, self.refresh_status)
        self.after(700, lambda: self.refresh_ollama_models(show_errors=False))
        self.after(1200, self.run_auto_start_if_enabled)
        self.after(500, self.refresh_ollama_server_status)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TNotebook", background="#e7edf5", borderwidth=0, tabmargins=(4, 6, 4, 0))
        style.configure("TNotebook.Tab", background="#cbd5e1", foreground="#334155",
                        padding=(16, 8), font=("맑은 고딕", 10, "bold"), borderwidth=1)
        style.map("TNotebook.Tab", background=[("selected", "#1e4e8c"), ("active", "#aebfd3")],
                  foreground=[("selected", "#ffffff"), ("active", "#172b46")])
        style.configure("TButton", padding=(10, 6), background="#e1e9f3", foreground="#172f4d",
                        bordercolor="#a8b9cc", font=("맑은 고딕", 10))
        style.map("TButton", background=[("disabled", "#edf0f3"), ("pressed", "#b4c7dd"), ("active", "#cbdcf0")],
                  foreground=[("disabled", "#8b98a6")])
        for name, background, active in (("Start.TButton", "#166c45", "#0e5635"),
                                         ("Stop.TButton", "#a02d35", "#83222a"),
                                         ("Action.TButton", "#245b9a", "#19477b")):
            style.configure(name, background=background, foreground="#ffffff", bordercolor=background,
                            padding=(10, 7), font=("맑은 고딕", 10, "bold"))
            style.map(name, background=[("pressed", active), ("active", active)], foreground=[("disabled", "#bfc9d4")])
        style.configure("Primary.TButton", font=("맑은 고딕", 16, "bold"), padding=16)
        style.configure("Title.TLabel", font=("맑은 고딕", 20, "bold"))
        style.configure("Status.TLabel", font=("맑은 고딕", 12, "bold"))

        outer = ttk.Frame(self, padding=22)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "Open WebUI 서버를 로컬에서 실행하고, 서버 준비가 끝나면 "
                "브라우저에서 http://localhost:8080/ 채팅 화면을 엽니다."
            ),
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(5, 14))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)

        run_tab = ttk.Frame(notebook, padding=16)
        setup_tab = ttk.Frame(notebook, padding=16)
        mac_tab = ttk.Frame(notebook, padding=16)
        ollama_tab = ttk.Frame(notebook, padding=12)
        notebook.add(run_tab, text="실행")
        notebook.add(setup_tab, text="설치 및 모델")
        notebook.add(mac_tab, text="Mac 설치 및 모델")
        notebook.add(ollama_tab, text="Ollama")
        self.build_ollama_tab(ollama_tab)

        mac_setup = ttk.Notebook(mac_tab)
        mac_setup.pack(fill="both", expand=True)
        mac_python = ttk.Frame(mac_setup, padding=12)
        mac_models = ttk.Frame(mac_setup, padding=12)
        mac_setup.add(mac_python, text="가상환경 & 파이썬")
        mac_setup.add(mac_models, text="AI 모델 설치")
        ttk.Label(mac_python, text="macOS: ~/OpenWebUI/venv에 Python 3.11 또는 3.12로 Open WebUI를 설치합니다.", wraplength=700).pack(anchor="w")
        mac_text = tk.Text(mac_python, height=10, wrap="word")
        mac_text.pack(fill="both", expand=True, pady=8)
        mac_text.insert("1.0", mac_install_command())
        mac_text.configure(state="disabled")
        mac_buttons = ttk.Frame(mac_python)
        mac_buttons.pack(fill="x")
        for label, callback in (("가상환경 설치 실행", self.install_mac_openwebui),
                                ("pip 업그레이드", self.upgrade_mac_pip),
                                ("설치 명령 복사", self.copy_mac_install_command)):
            ttk.Button(mac_buttons, text=label, command=callback).pack(side="left", fill="x", expand=True, padx=3)
        mac_actions = ttk.Frame(mac_python)
        mac_actions.pack(fill="x", pady=8)
        ttk.Button(mac_actions, text="가상환경 설치 확인", command=self.check_mac_venv).pack(side="left", fill="x", expand=True, padx=3)
        ttk.Button(mac_actions, text="가상환경에서 실행", command=self.start_mac_venv).pack(side="left", fill="x", expand=True, padx=3)
        ttk.Label(mac_models, text="Ollama 설치 후 모델명을 입력하세요. 설치된 모델 목록은 설치 및 모델 탭에서 확인할 수 있습니다.", wraplength=700).pack(anchor="w")
        ttk.Label(mac_models, textvariable=self.model_status_var, wraplength=700).pack(anchor="w", pady=8)
        ttk.Entry(mac_models, textvariable=self.model_var).pack(fill="x", pady=8)
        for label, callback in (("모델 목록 새로고침", self.refresh_ollama_models),
                                ("모델 설치", self.install_mac_model),
                                ("모델 설치 명령 복사", self.copy_model_install_command),
                                ("모델 선택 저장", self.save_selected_model),
                                ("Ollama 모델 페이지 열기", self.open_ollama_models_page)):
            ttk.Button(mac_models, text=label, command=callback).pack(fill="x", pady=3)

        status_box = ttk.LabelFrame(run_tab, text="실행 상태", padding=16)
        status_box.pack(fill="x")

        ttk.Label(status_box, textvariable=self.status_var, style="Status.TLabel").pack(anchor="w")
        ttk.Label(status_box, textvariable=self.url_var).pack(anchor="w", pady=(7, 0))

        self.progress = ttk.Progressbar(run_tab, mode="indeterminate")
        self.progress.pack(fill="x", pady=(18, 8))

        action_area = ttk.Frame(run_tab)
        action_area.pack(fill="x", pady=(12, 0))
        action_area.columnconfigure(0, weight=1)
        action_area.columnconfigure(1, weight=1)
        action_area.columnconfigure(2, weight=1)

        self.internal_start_button = ttk.Button(
            action_area,
            text="Local환경실행",
            style="Primary.TButton",
            command=self.start_internal_chat,
        )
        self.internal_start_button.grid(row=0, column=0, sticky="ew", ipady=10, padx=(0, 6))

        self.venv_start_button = ttk.Button(
            action_area,
            text="가상환경 실행",
            style="Primary.TButton",
            command=self.start_venv_chat,
        )
        self.venv_start_button.grid(row=0, column=1, sticky="ew", ipady=10, padx=6)

        self.chat_button = ttk.Button(
            action_area,
            text="Local AI Chat",
            style="Primary.TButton",
            command=self.open_browser,
        )
        self.chat_button.grid(row=0, column=2, sticky="ew", ipady=10, padx=(6, 0))

        small_row = ttk.Frame(run_tab)
        small_row.pack(fill="x", pady=(12, 0))

        ttk.Button(small_row, text="서버 중지", command=self.stop_server).pack(
            side="left", expand=True, fill="x", padx=(0, 4)
        )
        ttk.Button(small_row, text="설정", command=self.open_settings).pack(
            side="left", expand=True, fill="x", padx=(4, 0)
        )

        option_row = ttk.Frame(run_tab)
        option_row.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(
            option_row,
            text="자동실행",
            variable=self.auto_start_var,
            command=self.save_auto_start_setting,
        ).pack(side="left")
        ttk.Label(
            option_row,
            text="앱을 다시 켤 때 Open WebUI 서버를 자동으로 실행합니다.",
        ).pack(side="left", padx=(8, 0))
        ttk.Label(option_row, textvariable=self.auto_start_status_var).pack(side="right")

        editor_box = ttk.LabelFrame(run_tab, text="AI editor connect", padding=12)
        editor_box.pack(fill="x", pady=(12, 0))
        editor_box.columnconfigure(0, weight=1)
        editor_box.columnconfigure(1, weight=1)

        ttk.Button(
            editor_box,
            text="MDpro",
            command=self.open_mdpro,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4), ipady=4)
        ttk.Button(
            editor_box,
            text="Flask 웹앱 실행",
            command=self.start_flask_webapp,
            state="normal" if os.name == "nt" else "disabled",
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0), ipady=4)

        context_box = ttk.LabelFrame(run_tab, text="Windows 오른쪽 클릭 메뉴", padding=12)
        if os.name == "nt":
            context_box.pack(fill="x", pady=(12, 0))
        context_box.columnconfigure(0, weight=1)
        context_box.columnconfigure(1, weight=1)
        ttk.Button(
            context_box,
            text="오른쪽 클릭 메뉴 등록",
            command=self.register_context_menu,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4), ipady=4)
        ttk.Button(
            context_box,
            text="오른쪽 클릭 메뉴 해제",
            command=self.unregister_context_menu,
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0), ipady=4)
        ttk.Label(context_box, textvariable=self.context_menu_status_var).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

        info = ttk.LabelFrame(run_tab, text="동작 방식", padding=12)
        info.pack(fill="x", pady=(14, 0))
        ttk.Label(
            info,
            text=(
                "① Local환경실행은 PC에 직접 설치된 open-webui 명령을 실행합니다.\n" +
                ("② 가상환경 실행은 ~/OpenWebUI/venv에서 서버를 실행합니다.\n" if sys.platform == "darwin" else "② 가상환경 실행은 C:\\OpenWebUI로 이동한 뒤 venv를 활성화하고 open-webui serve를 실행합니다.\n") +
                "③ 자동실행은 다음 앱 시작 때 가상환경을 우선 사용하고, 없으면 Local환경실행을 사용합니다.\n"
                "④ Local AI Chat 버튼은 http://localhost:8080/ 채팅 화면을 엽니다."
            ),
            justify="left",
        ).pack(anchor="w")

        setup_notebook = ttk.Notebook(setup_tab)
        setup_notebook.pack(fill="both", expand=True)

        python_tab = ttk.Frame(setup_notebook, padding=12)
        model_tab = ttk.Frame(setup_notebook, padding=12)
        setup_notebook.add(python_tab, text="가상환경 & 파이썬")
        setup_notebook.add(model_tab, text="AI 모델 설치")

        install_box = ttk.LabelFrame(python_tab, text="Open WebUI 전용 가상환경", padding=12)
        install_box.pack(fill="both", expand=True)
        ttk.Label(
            install_box,
            text="Python 3.11을 우선 사용하고, 없으면 Python 3.12로 C:\\OpenWebUI\\venv 가상환경을 만든 뒤 그 안에 Open WebUI를 설치합니다.",
            wraplength=720,
            justify="left",
        ).pack(anchor="w")

        self.install_command_text = tk.Text(
            install_box,
            height=11,
            wrap="none",
            font=("Consolas", 10),
        )
        self.install_command_text.pack(fill="both", expand=True, pady=(8, 8))
        self.install_command_text.insert("1.0", self.format_install_command_for_display())
        self.install_command_text.configure(state="disabled")

        install_row = ttk.Frame(install_box)
        install_row.pack(fill="x")
        ttk.Button(
            install_row,
            text="Open WebUI 가상환경 설치 실행",
            command=self.install_open_webui,
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Button(
            install_row,
            text="python pip upgrade",
            command=self.upgrade_python_pip,
        ).pack(side="left", expand=True, fill="x", padx=4)
        ttk.Button(
            install_row,
            text="설치 명령 복사",
            command=self.copy_open_webui_install_command,
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))

        venv_action_row = ttk.Frame(install_box)
        venv_action_row.pack(fill="x", pady=(8, 0))
        ttk.Button(
            venv_action_row,
            text="가상환경 설치 확인",
            command=self.check_openwebui_venv,
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Button(
            venv_action_row,
            text="가상환경에서 실행",
            command=self.start_venv_chat,
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))

        models_box = ttk.LabelFrame(model_tab, text="Ollama 모델", padding=12)
        models_box.pack(fill="both", expand=True)
        ttk.Label(models_box, textvariable=self.model_status_var).pack(anchor="w")

        body = ttk.Frame(models_box)
        body.pack(fill="both", expand=True, pady=(8, 0))

        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        ttk.Label(left, text="설치된 모델").pack(anchor="w")
        self.model_listbox = tk.Listbox(left, height=8, exportselection=False)
        self.model_listbox.pack(fill="both", expand=True, pady=(6, 0))
        self.model_listbox.bind("<<ListboxSelect>>", self.select_model_from_list)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        ttk.Label(right, text="설치하거나 선택할 모델").pack(anchor="w")
        self.model_combo = ttk.Combobox(
            right,
            textvariable=self.model_var,
            values=POPULAR_OLLAMA_MODELS,
            state="normal",
        )
        self.model_combo.pack(fill="x", pady=(6, 8))
        ttk.Entry(
            right,
            textvariable=self.model_command_var,
            state="readonly",
        ).pack(fill="x")

        model_row_1 = ttk.Frame(right)
        model_row_1.pack(fill="x", pady=(8, 0))
        ttk.Button(
            model_row_1,
            text="모델 목록 새로고침",
            command=self.refresh_ollama_models,
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Button(
            model_row_1,
            text="선택 모델 저장",
            command=self.save_selected_model,
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))

        model_row_2 = ttk.Frame(right)
        model_row_2.pack(fill="x", pady=(8, 0))
        ttk.Button(
            model_row_2,
            text="CMD에서 모델 설치",
            command=self.install_selected_model,
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Button(
            model_row_2,
            text="모델 설치 명령 복사",
            command=self.copy_model_install_command,
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))

        link_row = ttk.Frame(models_box)
        link_row.pack(fill="x", pady=(12, 0))
        ttk.Button(link_row, text="Ollama 모델 페이지 열기", command=self.open_ollama_models_page).pack(
            side="left", expand=True, fill="x", padx=(0, 4)
        )
        ttk.Button(link_row, text="Hugging Face 모델 페이지 열기", command=self.open_hugging_face_models_page).pack(
            side="left", expand=True, fill="x", padx=(4, 0)
        )

    def build_ollama_tab(self, parent: ttk.Frame) -> None:
        tabs = ttk.Notebook(parent)
        tabs.pack(fill="both", expand=True)
        server = ttk.Frame(tabs, padding=10)
        models = ttk.Frame(tabs, padding=10)
        tabs.add(server, text="설치 · 서버 · CORS")
        tabs.add(models, text="모델 검색 · 설치 · 로딩")

        install = ttk.LabelFrame(server, text="Ollama 데스크톱 앱 설치", padding=8)
        install.pack(fill="x")
        ttk.Label(install, text="운영체제에 맞는 공식 설치 프로그램을 다운로드해 설치하세요.").pack(anchor="w")
        links = ttk.Frame(install)
        links.pack(fill="x", pady=4)
        ttk.Button(links, text="Windows 다운로드", command=lambda: webbrowser.open("https://ollama.com/download/windows")).pack(side="left", expand=True, fill="x", padx=3)
        ttk.Button(links, text="macOS 다운로드", command=lambda: webbrowser.open("https://ollama.com/download/mac")).pack(side="left", expand=True, fill="x", padx=3)
        ttk.Button(links, text="설치 확인", command=self.check_ollama_install).pack(side="left", expand=True, fill="x", padx=3)

        control = ttk.LabelFrame(server, text="Ollama 서버", padding=8)
        control.pack(fill="x", pady=6)
        status_row = ttk.Frame(control)
        status_row.pack(fill="x")
        frame_color = ttk.Style(self).lookup("TFrame", "background") or "#f0f0f0"
        self.ollama_status_light = tk.Canvas(status_row, width=20, height=20, bg=frame_color,
                                             highlightthickness=0, bd=0)
        self.ollama_status_light.pack(side="left", padx=(0, 8))
        self.ollama_status_dot = self.ollama_status_light.create_oval(3, 3, 17, 17, fill="#d99719", outline="#9a690c")
        ttk.Label(status_row, textvariable=self.ollama_server_status_var, wraplength=690).pack(side="left", fill="x", expand=True)
        buttons = ttk.Frame(control)
        buttons.pack(fill="x", pady=5)
        for label, action, button_style in (("서버 실행", "start", "Start.TButton"), ("서버 정지", "stop", "Stop.TButton"), ("서버 재시작", "restart", "Action.TButton")):
            ttk.Button(buttons, text=label, style=button_style, command=lambda a=action: self.control_ollama(a)).pack(side="left", fill="x", expand=True, padx=3)
        ttk.Button(control, text="기존 Ollama 서버 종료", command=lambda: self.control_ollama("external_stop")).pack(fill="x", padx=3, pady=(0, 4))
        ttk.Label(control, text="기존 서버 종료는 11434 포트를 사용하는 Ollama만 종료합니다. 런처가 시작한 서버는 런처 종료 시 함께 종료됩니다.", wraplength=690).pack(anchor="w")

        cors = ttk.LabelFrame(server, text="CORS 허용 Origin", padding=8)
        cors.pack(fill="both", expand=True)
        ttk.Label(cors, text="쉼표로 추가한 Origin은 서버 실행 또는 재시작 시 자동 적용됩니다.", wraplength=690).pack(anchor="w")
        ttk.Entry(cors, textvariable=self.ollama_origins_var).pack(fill="x", pady=5)
        self.ollama_command_text = tk.Text(cors, height=5, wrap="word", bg="#182230", fg="#e4edf7",
                                           insertbackground="#ffffff", selectbackground="#3d6792",
                                           relief="flat", borderwidth=0, padx=10, pady=8,
                                           font=("Consolas" if os.name == "nt" else "Menlo", 10))
        self.ollama_command_text.pack(fill="both", expand=True, pady=(2, 2))
        ttk.Button(cors, text="현재 OS의 터미널 명령 복사", command=self.copy_ollama_serve_command).pack(anchor="w", pady=5)
        self.ollama_origins_var.trace_add("write", lambda *_: self.update_ollama_commands())
        self.update_ollama_commands()

        ttk.Label(models, text="모델명을 입력하거나 설치된 모델을 선택하세요. 기본 모델: gemma4:e2b", wraplength=690).pack(anchor="w")
        model_line = ttk.Frame(models)
        model_line.pack(fill="x", pady=6)
        ttk.Label(model_line, text="모델명").pack(side="left")
        ttk.Entry(model_line, textvariable=self.ollama_model_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(model_line, text="다운로드 / 설치", command=self.pull_ollama_model).pack(side="left")
        search_line = ttk.Frame(models)
        search_line.pack(fill="x", pady=4)
        ttk.Label(search_line, text="검색").pack(side="left")
        ttk.Entry(search_line, textvariable=self.ollama_search_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(search_line, text="Ollama 온라인 검색", command=self.search_ollama_online).pack(side="left")
        ttk.Label(models, text="설치된 모델 (검색어로 목록 필터)").pack(anchor="w")
        self.ollama_listbox = tk.Listbox(models, height=7, exportselection=False)
        self.ollama_listbox.pack(fill="both", expand=True, pady=4)
        self.ollama_listbox.bind("<<ListboxSelect>>", self.select_ollama_model)
        self.ollama_search_var.trace_add("write", lambda *_: self.filter_ollama_models())
        model_buttons = ttk.Frame(models)
        model_buttons.pack(fill="x")
        ttk.Button(model_buttons, text="설치 모델 새로고침", command=self.refresh_ollama_tab_models).pack(side="left", fill="x", expand=True, padx=3)
        ttk.Button(model_buttons, text="선택 모델 로딩", command=self.load_ollama_model).pack(side="left", fill="x", expand=True, padx=3)
        ttk.Label(models, textvariable=self.ollama_action_status_var, wraplength=690).pack(anchor="w", pady=6)

    def update_ollama_commands(self) -> None:
        origins = self.ollama_origins_var.get().strip()
        self.ollama_command_display_var.set("Windows PowerShell: " + ollama_manager.serve_command(origins, True) +
                                            "\nmacOS 터미널: " + ollama_manager.serve_command(origins, False))
        self.ollama_command_text.configure(state="normal")
        self.ollama_command_text.delete("1.0", tk.END)
        self.ollama_command_text.insert("1.0", self.ollama_command_display_var.get())
        self.ollama_command_text.configure(state="disabled")

    def copy_ollama_serve_command(self) -> None:
        command = ollama_manager.serve_command(self.ollama_origins_var.get().strip(), os.name == "nt")
        self.copy_to_clipboard(command, "Ollama 서버 명령을 복사했습니다.")

    def check_ollama_install(self) -> None:
        executable = find_ollama_command()
        if executable:
            messagebox.showinfo(APP_NAME, f"Ollama 실행 파일: {executable}")
        else:
            messagebox.showwarning(APP_NAME, "Ollama 실행 파일을 찾지 못했습니다. 다운로드 후 설치하고 다시 확인하세요.")

    def refresh_ollama_server_status(self) -> None:
        self.after(3000, self.refresh_ollama_server_status)
        if self.ollama_busy:
            return
        self.ollama_status_generation += 1
        generation = self.ollama_status_generation
        def work() -> None:
            result = ollama_manager.probe_server()
            self.after(0, lambda: self.apply_ollama_server_status(generation, result))
        threading.Thread(target=work, daemon=True).start()

    def set_ollama_status(self, state: str, message: str) -> None:
        colors = {"running": ("#22a65a", "#127c3e"), "stopped": ("#dc3545", "#a3212d"),
                  "unknown": ("#d99719", "#9a690c")}
        fill, outline = colors[state]
        self.ollama_status_light.itemconfigure(self.ollama_status_dot, fill=fill, outline=outline)
        self.ollama_server_status_var.set(message)

    def apply_ollama_server_status(self, generation: int, result: str) -> None:
        if generation != self.ollama_status_generation or self.ollama_busy:
            return
        managed = self.ollama_manager.is_managed_running()
        if result == "running":
            if managed:
                changed = self.ollama_manager.origins != self.ollama_origins_var.get().strip()
                message = "실행 중 — " + ("Origin 변경을 적용하려면 재시작하세요." if changed else "입력한 Origin 적용됨")
            else:
                message = "외부 Ollama 서버 실행 중 — Origin 설정은 확인할 수 없습니다."
            self.set_ollama_status("running", message)
        elif result == "stopped" and not managed:
            self.set_ollama_status("stopped", "정지 — Ollama 서버가 실행 중이 아닙니다.")
        else:
            self.set_ollama_status("unknown", "확인 필요 — 서버 포트가 응답하지 않거나 Ollama인지 확인할 수 없습니다.")

    def control_ollama(self, action: str) -> None:
        if self.ollama_busy:
            return
        executable = find_ollama_command()
        if action in ("start", "restart") and not executable:
            messagebox.showwarning(APP_NAME, "Ollama를 먼저 설치하십시오.")
            return
        origins = self.ollama_origins_var.get().strip()
        self.ollama_busy = True
        self.ollama_status_generation += 1
        self.set_ollama_status("unknown", "확인 중 — Ollama 서버 작업을 진행하고 있습니다.")
        def work() -> None:
            try:
                if action == "external_stop":
                    managed = self.ollama_manager.process
                    ollama_manager.stop_external_ollama(managed.pid if managed and self.ollama_manager.is_managed_running() else None)
                if action in ("stop", "restart"):
                    self.ollama_manager.stop()
                if action in ("start", "restart"):
                    # Allow the stopped listener to release its port before restart.
                    for _ in range(30):
                        if not ollama_manager.port_in_use():
                            break
                        time.sleep(0.1)
                    self.ollama_manager.start(executable, origins)
                    for _ in range(100):
                        if not self.ollama_manager.is_managed_running():
                            raise RuntimeError(f"Ollama 서버 시작 실패. 로그: {APP_DIR / 'ollama-server.log'}")
                        try:
                            ollama_manager.api_request("/api/version", timeout=1)
                            break
                        except Exception:
                            time.sleep(0.1)
                    else:
                        self.ollama_manager.stop()
                        raise RuntimeError(f"Ollama 서버 응답 대기 시간 초과. 로그: {APP_DIR / 'ollama-server.log'}")
                self.after(0, lambda: self.ollama_control_done(action, origins, None))
            except Exception as exc:
                self.after(0, lambda error=str(exc): self.ollama_control_done(action, origins, error))
        threading.Thread(target=work, daemon=True).start()

    def ollama_control_done(self, action: str, origins: str, error: str | None) -> None:
        self.ollama_busy = False
        if error:
            self.set_ollama_status("unknown", error)
            messagebox.showerror(APP_NAME, error)
            return
        if action in ("start", "restart"):
            self.config_data["ollama_origins"] = origins
            save_config(self.config_data)
            self.set_ollama_status("running", "실행 중 — 입력한 Origin 적용됨")
            self.refresh_ollama_tab_models()
        else:
            self.set_ollama_status("unknown", "확인 중 — 서버 종료 상태를 확인하고 있습니다.")

    def search_ollama_online(self) -> None:
        webbrowser.open("https://ollama.com/search?" + urlencode({"q": self.ollama_search_var.get().strip()}))

    def filter_ollama_models(self) -> None:
        query = self.ollama_search_var.get().strip().lower()
        self.ollama_listbox.delete(0, tk.END)
        for model in getattr(self, "ollama_tab_models", []):
            if query in model.lower():
                self.ollama_listbox.insert(tk.END, model)

    def select_ollama_model(self, _event: tk.Event) -> None:
        selected = self.ollama_listbox.curselection()
        if selected:
            self.ollama_model_var.set(self.ollama_listbox.get(selected[0]))

    def refresh_ollama_tab_models(self) -> None:
        self.ollama_action_status_var.set("설치된 모델을 확인 중입니다.")
        def work() -> None:
            try:
                result = ollama_manager.api_request("/api/tags")
                models = [m["name"] for m in result.get("models", []) if isinstance(m, dict) and isinstance(m.get("name"), str)]
                self.after(0, lambda: self.ollama_models_received(models))
            except Exception as exc:
                self.after(0, lambda error=str(exc): self.ollama_action_status_var.set(f"모델 목록 확인 실패: {error}"))
        threading.Thread(target=work, daemon=True).start()

    def ollama_models_received(self, models: list[str]) -> None:
        self.ollama_tab_models = models
        self.filter_ollama_models()
        self.ollama_action_status_var.set(f"설치된 모델 {len(models)}개")

    def pull_ollama_model(self) -> None:
        model = self.ollama_model_var.get().strip()
        executable = find_ollama_command()
        if not model_name_is_safe(model):
            messagebox.showwarning(APP_NAME, "올바른 Ollama 모델명을 입력하세요.")
            return
        if not executable:
            messagebox.showwarning(APP_NAME, "Ollama를 먼저 설치하십시오.")
            return
        if self.ollama_pull_process and self.ollama_pull_process.poll() is None:
            messagebox.showwarning(APP_NAME, "모델 다운로드가 이미 진행 중입니다.")
            return
        try:
            ensure_app_dir()
            with (APP_DIR / "ollama-pull.log").open("a", encoding="utf-8") as log:
                env = os.environ.copy()
                env["OLLAMA_HOST"] = "127.0.0.1:11434"
                self.ollama_pull_process = subprocess.Popen([executable, "pull", model], stdout=log, stderr=subprocess.STDOUT,
                                                            env=env, creationflags=0x08000000 if os.name == "nt" else 0)
        except OSError as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return
        self.ollama_action_status_var.set(f"{model} 다운로드 중 — 로그: {APP_DIR / 'ollama-pull.log'}")
        self.after(1000, lambda: self.poll_ollama_pull(model))

    def poll_ollama_pull(self, model: str) -> None:
        result = self.ollama_pull_process.poll()
        if result is None:
            self.after(1000, lambda: self.poll_ollama_pull(model))
        elif result == 0:
            self.ollama_action_status_var.set(f"{model} 다운로드 완료")
            self.refresh_ollama_tab_models()
        else:
            self.ollama_action_status_var.set(f"{model} 다운로드 실패 — 로그: {APP_DIR / 'ollama-pull.log'}")
            messagebox.showerror(APP_NAME, f"모델 설치 실패. Ollama 서버와 로그를 확인하세요.\n{APP_DIR / 'ollama-pull.log'}")

    def load_ollama_model(self) -> None:
        if self.ollama_loading:
            messagebox.showwarning(APP_NAME, "모델 로딩이 이미 진행 중입니다.")
            return
        model = self.ollama_model_var.get().strip()
        if not model_name_is_safe(model):
            messagebox.showwarning(APP_NAME, "올바른 Ollama 모델명을 입력하세요.")
            return
        self.ollama_loading = True
        self.ollama_action_status_var.set(f"{model} 로딩 중입니다. 시간이 걸릴 수 있습니다.")
        def work() -> None:
            try:
                ollama_manager.api_request("/api/generate", {"model": model, "prompt": "", "stream": False, "keep_alive": "5m"}, timeout=600)
                self.after(0, lambda: self.ollama_model_loaded(model))
            except Exception as exc:
                self.after(0, lambda error=str(exc): self.ollama_model_load_failed(error))
        threading.Thread(target=work, daemon=True).start()

    def ollama_model_loaded(self, model: str) -> None:
        self.ollama_loading = False
        self.config_data["selected_model"] = model
        save_config(self.config_data)
        self.model_var.set(model)
        self.ollama_action_status_var.set(f"{model} 로딩 완료 (유휴 시 5분 유지). Open WebUI에서도 모델을 선택하세요.")

    def ollama_model_load_failed(self, error: str) -> None:
        self.ollama_loading = False
        self.ollama_action_status_var.set(f"모델 로딩 실패: {error}")

    def copy_to_clipboard(self, text: str, success_message: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()
        messagebox.showinfo(APP_NAME, success_message)

    def require_mac(self) -> bool:
        if sys.platform == "darwin":
            return True
        messagebox.showwarning(APP_NAME, "이 기능은 macOS에서 실행하십시오.")
        return False

    def run_mac_operation(self, command: str, title: str) -> None:
        if not self.require_mac():
            return
        if getattr(self, "mac_operation", None) and self.mac_operation.poll() is None:
            messagebox.showwarning(APP_NAME, "이전 설치 작업이 진행 중입니다.")
            return
        try:
            self.mac_operation = start_cmd_window(command, title)
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"작업을 시작하지 못했습니다: {exc}")
            return
        self.status_var.set(f"{title} 진행 중. 로그: {APP_DIR / 'operations.log'}")
        messagebox.showinfo(APP_NAME, f"{title} 작업을 시작했습니다.\n진행 로그: {APP_DIR / 'operations.log'}")
        self.after(1000, lambda: self.poll_mac_operation(title))

    def poll_mac_operation(self, title: str) -> None:
        result = self.mac_operation.poll()
        if result is None:
            self.after(1000, lambda: self.poll_mac_operation(title))
            return
        self.refresh_status()
        if result == 0:
            messagebox.showinfo(APP_NAME, f"{title} 작업이 완료되었습니다.")
            if title == "Install Ollama Model":
                self.refresh_ollama_models(show_errors=False)
        else:
            messagebox.showerror(APP_NAME, f"{title} 작업이 실패했습니다 (종료 코드 {result}).\n로그: {APP_DIR / 'operations.log'}")

    def install_mac_openwebui(self) -> None:
        self.run_mac_operation(mac_install_command(), "Install Open WebUI")

    def upgrade_mac_pip(self) -> None:
        self.run_mac_operation('"$HOME/OpenWebUI/venv/bin/python" -m pip install --upgrade pip', "Upgrade pip")

    def copy_mac_install_command(self) -> None:
        self.copy_to_clipboard(mac_install_command(), "Mac 설치 명령을 복사했습니다.")

    def check_mac_venv(self) -> None:
        if self.require_mac():
            self.check_openwebui_venv()

    def start_mac_venv(self) -> None:
        if self.require_mac():
            self.start_venv_chat()

    def install_mac_model(self) -> None:
        if self.require_mac():
            self.install_selected_model()

    def format_install_command_for_display(self) -> str:
        return "\n".join(
            [
                "cd /d C:\\",
                "if not exist OpenWebUI mkdir OpenWebUI",
                "cd /d C:\\OpenWebUI",
                "py -3.11 우선 확인",
                "py -3.11이 없으면 py -3.12 확인",
                "py -3.11 또는 py -3.12 -m venv venv",
                "call venv\\Scripts\\activate.bat",
                "python --version",
                "python -m pip install --upgrade pip setuptools wheel",
                "python -m pip install open-webui",
                "python -m pip show open-webui",
            ]
        )

    def install_open_webui(self) -> None:
        if sys.platform == "darwin":
            messagebox.showwarning(APP_NAME, "Mac 설치 및 모델 탭을 사용하십시오.")
            return
        command = build_open_webui_install_command()
        self.install_command_var.set(r"C:\OpenWebUI\venv + Python 3.11/3.12 + python -m pip install open-webui")
        self.config_data["venv_command"] = build_python311_openwebui_serve_command()
        save_config(self.config_data)
        try:
            start_cmd_window(command, "Install Open WebUI")
            messagebox.showinfo(
                APP_NAME,
                "Open WebUI 전용 가상환경 설치 명령을 CMD 창에서 실행했습니다.\n\n"
                "Python 3.11을 먼저 사용하고, 없으면 Python 3.12를 시도합니다.\n"
                "설치가 끝나면 C:\\OpenWebUI로 이동해 venv를 활성화한 뒤 open-webui serve를 실행합니다.",
            )
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"설치 CMD 창을 시작하지 못했습니다.\n\n{exc}")

    def upgrade_python_pip(self) -> None:
        if sys.platform == "darwin":
            self.upgrade_mac_pip()
            return
        command = build_python_pip_upgrade_command()
        try:
            start_cmd_window(command, "python pip upgrade")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"pip upgrade CMD 창을 시작하지 못했습니다.\n\n{exc}")

    def copy_open_webui_install_command(self) -> None:
        command = build_open_webui_install_command()
        self.install_command_var.set(command)
        self.copy_to_clipboard(command, "Open WebUI 가상환경 설치 명령을 클립보드에 복사했습니다.")

    def check_openwebui_venv(self) -> None:
        paths = openwebui_venv_paths()
        checks = [
            ("설치 폴더", paths["root"]),
            ("가상환경", paths["venv"]),
            ("Python 실행 파일", paths["python"]),
            ("활성화 스크립트", paths["activate"]),
            ("Open WebUI 실행 파일", paths["open_webui"]),
        ]
        lines = []
        missing = []
        for label, path in checks:
            exists = path_exists(path)
            lines.append(f"{'OK' if exists else 'NO'}  {label}: {path}")
            if not exists:
                missing.append(label)

        if missing:
            title = "가상환경 설치가 아직 완료되지 않았습니다."
            guide = "\n\n누락 항목이 있으면 `Open WebUI 가상환경 설치 실행` 버튼을 먼저 실행하십시오."
            messagebox.showwarning(APP_NAME, title + "\n\n" + "\n".join(lines) + guide)
        else:
            self.config_data["venv_command"] = build_python311_openwebui_serve_command()
            save_config(self.config_data)
            messagebox.showinfo(
                APP_NAME,
                "가상환경 설치를 확인했습니다.\n\n"
                + "\n".join(lines)
                + "\n\n가상환경 실행 명령을 저장했습니다.",
            )

    def update_model_command(self) -> None:
        model_name = self.model_var.get().strip() or DEFAULT_MODEL_TO_PULL
        ollama_command = find_ollama_command() or "ollama"
        self.model_command_var.set(f"{quote_cmd_arg(ollama_command)} pull {model_name}")

    def refresh_ollama_models(self, show_errors: bool = True) -> None:
        self.model_status_var.set("Ollama 모델 목록을 불러오는 중입니다.")
        threading.Thread(target=lambda: self._load_ollama_models(show_errors), daemon=True).start()

    def _load_ollama_models(self, show_errors: bool) -> None:
        ollama_command = find_ollama_command()
        if not ollama_command:
            self.after(
                0,
                lambda: self._ollama_models_failed(
                    "ollama 실행 파일을 찾지 못했습니다. Ollama 설치 후 다시 시도하십시오.",
                    show_errors,
                ),
            )
            return

        try:
            output = run_ollama_list(ollama_command)
            models = parse_ollama_models(output)
        except Exception as exc:
            self.after(0, lambda error=str(exc): self._ollama_models_failed(error, show_errors))
            return

        self.after(0, lambda: self._ollama_models_loaded(models))

    def _ollama_models_loaded(self, models: list[str]) -> None:
        self.available_models = models
        self.model_listbox.delete(0, tk.END)
        for model_name in models:
            self.model_listbox.insert(tk.END, model_name)

        combo_values = models if models else POPULAR_OLLAMA_MODELS
        self.model_combo.configure(values=combo_values)

        saved_model = str(self.config_data.get("selected_model") or "").strip()
        if saved_model and saved_model in combo_values:
            self.model_var.set(saved_model)
        elif models:
            self.model_var.set(models[0])

        if models:
            self.model_status_var.set(f"설치된 Ollama 모델 {len(models)}개를 찾았습니다.")
        else:
            self.model_status_var.set("설치된 Ollama 모델이 없습니다. 오른쪽에서 모델명을 입력해 설치하십시오.")

    def _ollama_models_failed(self, message: str, show_errors: bool = True) -> None:
        self.model_status_var.set("Ollama 모델 목록을 불러오지 못했습니다.")
        if show_errors:
            messagebox.showwarning(APP_NAME, message)

    def select_model_from_list(self, _event: tk.Event) -> None:
        selection = self.model_listbox.curselection()
        if not selection:
            return
        self.model_var.set(self.model_listbox.get(selection[0]))

    def save_selected_model(self) -> None:
        model_name = self.model_var.get().strip()
        if not model_name:
            messagebox.showwarning(APP_NAME, "모델명을 입력하거나 설치된 모델을 선택하십시오.")
            return
        if not model_name_is_safe(model_name):
            messagebox.showwarning(APP_NAME, "모델명에는 영문, 숫자, ., _, -, /, : 문자만 사용할 수 있습니다.")
            return

        self.config_data["selected_model"] = model_name
        save_config(self.config_data)
        self.model_status_var.set(f"선택 모델을 저장했습니다: {model_name}")

    def install_selected_model(self) -> None:
        model_name = self.model_var.get().strip()
        if not model_name:
            messagebox.showwarning(APP_NAME, "설치할 Ollama 모델명을 입력하십시오.")
            return
        if not model_name_is_safe(model_name):
            messagebox.showwarning(APP_NAME, "모델명에는 영문, 숫자, ., _, -, /, : 문자만 사용할 수 있습니다.")
            return

        command = self.model_command_var.get().strip()
        if sys.platform == "darwin":
            self.run_mac_operation(command, "Install Ollama Model")
            return
        try:
            start_cmd_window(command, "Install Ollama Model")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"모델 설치 CMD 창을 시작하지 못했습니다.\n\n{exc}")

    def copy_model_install_command(self) -> None:
        model_name = self.model_var.get().strip()
        if not model_name or not model_name_is_safe(model_name):
            messagebox.showwarning(APP_NAME, "복사할 수 있는 올바른 모델명을 입력하십시오.")
            return
        self.copy_to_clipboard(
            self.model_command_var.get().strip(),
            "Ollama 모델 설치 명령을 클립보드에 복사했습니다.",
        )

    def open_ollama_models_page(self) -> None:
        webbrowser.open(OLLAMA_MODELS_URL)

    def open_hugging_face_models_page(self) -> None:
        webbrowser.open(HUGGING_FACE_MODELS_URL)

    def open_mdpro(self) -> None:
        webbrowser.open(MDPRO_URL)

    def start_flask_webapp(self) -> None:
        batch_path = flask_webapp_batch_path()
        if not batch_path.is_file():
            messagebox.showerror(
                APP_NAME,
                "Flask 웹앱 실행 파일을 찾지 못했습니다.\n\n"
                f"확인 경로:\n{batch_path}",
            )
            return
        command = f'call {quote_cmd_arg(str(batch_path))}'
        try:
            start_cmd_window(command, "OpenWebUI Flask Web App")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Flask 웹앱 CMD 창을 시작하지 못했습니다.\n\n{exc}")

    def save_auto_start_setting(self) -> None:
        enabled = bool(self.auto_start_var.get())
        self.config_data["auto_start_server"] = enabled
        save_config(self.config_data)
        if enabled:
            self.auto_start_status_var.set("자동실행 저장됨")
        else:
            self.auto_start_status_var.set("자동실행 해제됨")

    def update_context_menu_status(self) -> None:
        if context_menu_is_registered():
            self.context_menu_status_var.set("등록됨: 바탕화면 또는 폴더에서 마우스 오른쪽 버튼으로 실행할 수 있습니다.")
        else:
            self.context_menu_status_var.set("등록 안 됨")

    def register_context_menu(self) -> None:
        try:
            set_context_menu_registry()
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"오른쪽 클릭 메뉴 등록에 실패했습니다.\n\n{exc}")
            self.update_context_menu_status()
            return

        self.update_context_menu_status()
        messagebox.showinfo(
            APP_NAME,
            "Windows 오른쪽 클릭 메뉴에 앱 실행 항목을 등록했습니다.\n\n"
            "바탕화면 빈 공간 또는 폴더를 마우스 오른쪽 버튼으로 클릭해 실행할 수 있습니다.",
        )

    def unregister_context_menu(self) -> None:
        try:
            remove_context_menu_registry()
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"오른쪽 클릭 메뉴 해제에 실패했습니다.\n\n{exc}")
            self.update_context_menu_status()
            return

        self.update_context_menu_status()
        messagebox.showinfo(APP_NAME, "Windows 오른쪽 클릭 메뉴 등록을 해제했습니다.")

    def server_url(self) -> str:
        host = self.config_data["host"]
        browser_host = "localhost" if host in {"127.0.0.1", "0.0.0.0"} else host
        return f"http://{browser_host}:{self.config_data['port']}/"

    def refresh_installation_detection(self) -> None:
        self.config_data = update_config_with_detected_runtime(self.config_data, save=True)
        found = self.config_data.get("open_webui_path") or find_open_webui_command()
        if found and not path_exists(Path(found)):
            found = find_open_webui_command()
        self.internal_open_webui_command = found

        self.venv_open_webui_ready = openwebui_venv_is_installed()
        if self.venv_open_webui_ready:
            self.config_data["venv_command"] = build_python311_openwebui_serve_command()

    def refresh_status(self) -> None:
        self.refresh_installation_detection()
        host = self.config_data["host"]
        check_host = "127.0.0.1" if host == "0.0.0.0" else host
        port = int(self.config_data["port"])
        url = self.server_url()
        self.url_var.set(url)

        if port_is_open(check_host, port):
            self.status_var.set("Open WebUI가 실행 중입니다.")
            self.internal_start_button.configure(text="Local환경실행")
            self.venv_start_button.configure(text="가상환경 실행")
        elif self.is_starting:
            self.status_var.set("Open WebUI를 시작하고 있습니다. " + (f"로그: {APP_DIR / 'server.log'}" if sys.platform == "darwin" else "CMD 창을 확인하십시오."))
            self.internal_start_button.configure(text="서버 시작 중...")
            self.venv_start_button.configure(text="서버 시작 중...")
        else:
            self.status_var.set("Open WebUI가 현재 실행 중이 아닙니다.")
            self.internal_start_button.configure(text="Local환경실행")
            self.venv_start_button.configure(text="가상환경 실행")

        if self.is_starting:
            self.configure_server_buttons("disabled")
        else:
            self.internal_start_button.configure(
                state="normal" if self.internal_open_webui_command else "disabled"
            )
            self.venv_start_button.configure(
                state="normal" if self.venv_open_webui_ready else "disabled"
            )

    def run_auto_start_if_enabled(self) -> None:
        if self.auto_start_attempted:
            return
        self.auto_start_attempted = True

        if not self.config_data.get("auto_start_server"):
            return

        self.refresh_installation_detection()
        host = self.config_data["host"]
        check_host = "127.0.0.1" if host == "0.0.0.0" else host
        port = int(self.config_data["port"])
        if port_is_open(check_host, port):
            self.refresh_status()
            if self.config_data.get("auto_open_browser", True):
                self.open_browser()
            return

        if self.venv_open_webui_ready:
            self.start_venv_chat()
            return

        if self.internal_open_webui_command:
            self.start_internal_chat()
            return

        self.status_var.set("자동실행 켜짐: 실행 가능한 Open WebUI 설치를 찾지 못했습니다.")

    def start_internal_chat(self) -> None:
        self.refresh_installation_detection()
        if not self.internal_open_webui_command:
            messagebox.showwarning(
                APP_NAME,
                "PC에 직접 설치된 open-webui 실행 파일을 찾지 못했습니다.\n"
                "`Open WebUI 가상환경 설치 실행` 후 `가상환경 실행`을 사용하거나, 설정에서 직접 실행 명령을 지정하십시오.",
            )
            return
        command = command_with_openwebui_port(
            f"{quote_cmd_arg(self.internal_open_webui_command)} serve",
            int(self.config_data.get("port") or DEFAULT_CONFIG["port"]),
        )
        if not command:
            messagebox.showwarning(APP_NAME, "Local 환경 실행 명령을 찾지 못했습니다.")
            return
        self.start_chat_with_command(command, "Open WebUI Server")

    def start_venv_chat(self) -> None:
        self.refresh_installation_detection()
        if not self.venv_open_webui_ready:
            messagebox.showwarning(
                APP_NAME,
                "Open WebUI 전용 가상환경 설치를 찾지 못했습니다.\n"
                "`가상환경 설치 확인` 또는 `Open WebUI 가상환경 설치 실행`을 먼저 실행하십시오.",
            )
            return
        command = str(
            self.config_data.get("venv_command")
            or build_python311_openwebui_serve_command()
        ).strip()
        command = command_with_openwebui_port(
            command,
            int(self.config_data.get("port") or DEFAULT_CONFIG["port"]),
        )
        if not command:
            messagebox.showwarning(APP_NAME, "가상환경 실행 명령을 찾지 못했습니다.")
            return
        self.start_chat_with_command(command, "Open WebUI venv Server")

    def configure_server_buttons(self, state: str) -> None:
        self.internal_start_button.configure(state=state)
        self.venv_start_button.configure(state=state)

    def start_chat_with_command(self, command: str, title: str) -> None:
        host = self.config_data["host"]
        check_host = "127.0.0.1" if host == "0.0.0.0" else host
        port = int(self.config_data["port"])

        if port_is_open(check_host, port):
            self.refresh_status()
            self.status_var.set("Open WebUI 서버가 이미 실행 중입니다.")
            return
        if not port_can_bind(host, port):
            self.refresh_status()
            messagebox.showwarning(
                APP_NAME,
                f"포트 {port}를 다른 프로그램이 사용 중이어서 Open WebUI를 시작하지 않았습니다.\n\n"
                "이미 열린 Open WebUI/CMD/브라우저 탭을 닫거나, 설정에서 다른 포트를 사용하십시오.",
            )
            return

        if self.is_starting:
            return

        self.is_starting = True
        self.progress.start(10)
        self.configure_server_buttons("disabled")
        self.refresh_status()

        try:
            # /k를 사용하여 서버가 실패해도 CMD 창이 닫히지 않도록 한다.
            self.server_process = start_cmd_window(command, title)
        except Exception as exc:
            self.is_starting = False
            self.progress.stop()
            self.configure_server_buttons("normal")
            messagebox.showerror(APP_NAME, f"서버를 시작하지 못했습니다.\n\n{exc}")
            self.refresh_status()
            return

        threading.Thread(target=self._wait_for_server, daemon=True).start()

    def _wait_for_server(self) -> None:
        host = self.config_data["host"]
        check_host = "127.0.0.1" if host == "0.0.0.0" else host
        port = int(self.config_data["port"])
        timeout = int(self.config_data["startup_timeout_seconds"])
        started_at = time.time()

        while time.time() - started_at < timeout:
            if port_is_open(check_host, port):
                self.after(0, self._server_ready)
                return

            if self.server_process and self.server_process.poll() is not None:
                self.after(0, self._server_failed)
                return

            time.sleep(1)

        self.after(0, self._server_timeout)

    def _server_ready(self) -> None:
        self.is_starting = False
        self.progress.stop()
        self.configure_server_buttons("normal")
        self.refresh_status()

        if self.config_data.get("auto_open_browser", True):
            self.open_browser()

    def _server_failed(self) -> None:
        self.is_starting = False
        self.progress.stop()
        self.configure_server_buttons("normal")
        self.refresh_status()
        messagebox.showerror(
            APP_NAME,
            "Open WebUI 서버 프로세스가 종료되었습니다.\n" +
            (f"로그를 확인하십시오: {APP_DIR / 'server.log'}" if sys.platform == "darwin" else "열려 있는 CMD 창의 오류 메시지를 확인하고 설정의 실행 명령을 점검하십시오."),
        )

    def _server_timeout(self) -> None:
        self.is_starting = False
        self.progress.stop()
        self.configure_server_buttons("normal")
        self.refresh_status()
        messagebox.showwarning(
            APP_NAME,
            "설정된 대기시간 안에 localhost 포트가 열리지 않았습니다.\n" +
            (f"로그를 확인하십시오: {APP_DIR / 'server.log'}" if sys.platform == "darwin" else "CMD 창의 진행 상태를 확인하십시오."),
        )

    def open_browser(self) -> None:
        webbrowser.open(self.server_url())

    def stop_server(self) -> None:
        if self.server_process and self.server_process.poll() is None:
            try:
                if sys.platform == "darwin":
                    os.killpg(self.server_process.pid, signal.SIGTERM)
                else:
                    subprocess.run(
                        ["taskkill", "/PID", str(self.server_process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=0x08000000,
                    )
                self.server_process = None
                messagebox.showinfo(APP_NAME, "이 앱에서 시작한 Open WebUI 서버를 중지했습니다.")
            except Exception as exc:
                messagebox.showerror(APP_NAME, f"서버 중지에 실패했습니다.\n\n{exc}")
        else:
            messagebox.showinfo(
                APP_NAME,
                "이 앱에서 시작한 서버 프로세스가 없습니다.\n"
                "외부 CMD에서 시작한 서버는 해당 CMD 창에서 Ctrl+C로 중지하십시오.",
            )
        self.after(500, self.refresh_status)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self, self.config_data)
        self.wait_window(dialog)
        if dialog.result:
            self.config_data = {**self.config_data, **dialog.result}
            save_config(self.config_data)
            self.refresh_status()
            messagebox.showinfo(APP_NAME, "실행 설정을 저장했습니다.")

    def on_close(self) -> None:
        if self.ollama_busy:
            messagebox.showwarning(APP_NAME, "Ollama 서버 작업이 끝난 뒤 종료하십시오.")
            return
        if self.ollama_manager.is_managed_running():
            try:
                self.ollama_manager.stop()
            except Exception as exc:
                messagebox.showerror(APP_NAME, f"Ollama 서버를 종료하지 못했습니다: {exc}")
                return
        # 서버는 유지한다. CMD 창에서 로그를 계속 확인할 수 있다.
        self.destroy()


if __name__ == "__main__":
    if os.name != "nt" and sys.platform != "darwin":
        raise SystemExit("이 실행기는 Windows와 macOS를 지원합니다.")
    LauncherApp().mainloop()
