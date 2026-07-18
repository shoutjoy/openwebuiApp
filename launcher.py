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
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

APP_NAME = "Joonghee Park PhD 's OpenWebUI Local AI"
APP_VERSION = "3.1.0"

APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "OpenWebUIChatLauncher"
CONFIG_FILE = APP_DIR / "settings.json"

CREATE_NEW_CONSOLE = 0x00000010 if os.name == "nt" else 0

DEFAULT_CONFIG = {
    "command": "open-webui serve",
    "venv_command": r'"C:\OpenWebUI\venv\Scripts\open-webui.exe" serve',
    "host": "127.0.0.1",
    "port": 8080,
    "auto_open_browser": True,
    "startup_timeout_seconds": 180,
    "selected_model": "",
}

OLLAMA_MODELS_URL = "https://ollama.com/library"
HUGGING_FACE_MODELS_URL = "https://huggingface.co/models"
MDLIVE_URL = "https://mdlivepro.vercel.app/"
MDPRO_URL = "https://mdproviewer.vercel.app/"
DEFAULT_MODEL_TO_PULL = "llama3.1:8b"

POPULAR_OLLAMA_MODELS = [
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


def start_cmd_window(command: str, title: str) -> subprocess.Popen:
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


def build_python_pip_upgrade_command() -> str:
    return "python.exe -m pip install --upgrade pip"


def build_python311_openwebui_setup_command() -> str:
    return build_open_webui_install_command()


def build_python311_openwebui_serve_command() -> str:
    return r'"C:\OpenWebUI\venv\Scripts\open-webui.exe" serve'


def openwebui_venv_paths() -> dict[str, Path]:
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
    special_chars = set(" &()[]{}^=;!'+,`")
    if any(char.isspace() or char in special_chars for char in value):
        return f'"{value}"'
    return value


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

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("860x720")
        self.resizable(False, False)

        self.status_var = tk.StringVar(value="Open WebUI 상태를 확인하고 있습니다.")
        self.url_var = tk.StringVar()
        selected_model = str(self.config_data.get("selected_model") or DEFAULT_MODEL_TO_PULL)
        self.model_var = tk.StringVar(value=selected_model)
        self.model_status_var = tk.StringVar(value="Ollama에 설치된 모델을 자동으로 찾고 있습니다.")
        self.install_command_var = tk.StringVar(value="Open WebUI 전용 가상환경 설치 명령")
        self.model_command_var = tk.StringVar()
        self.model_var.trace_add("write", lambda *_: self.update_model_command())

        self._build_ui()
        self.update_model_command()
        self.after(300, self.refresh_status)
        self.after(700, lambda: self.refresh_ollama_models(show_errors=False))
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
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
        notebook.add(run_tab, text="실행")
        notebook.add(setup_tab, text="설치 및 모델")

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

        editor_box = ttk.LabelFrame(run_tab, text="AI editor connect", padding=12)
        editor_box.pack(fill="x", pady=(14, 0))
        editor_box.columnconfigure(0, weight=1)
        editor_box.columnconfigure(1, weight=1)

        ttk.Button(
            editor_box,
            text="MDlive",
            command=self.open_mdlive,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4), ipady=4)
        ttk.Button(
            editor_box,
            text="MDpro",
            command=self.open_mdpro,
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0), ipady=4)

        info = ttk.LabelFrame(run_tab, text="동작 방식", padding=12)
        info.pack(fill="x", pady=(18, 0))
        ttk.Label(
            info,
            text=(
                "① Local환경실행은 PC에 직접 설치된 open-webui 명령을 실행합니다.\n"
                "② 가상환경 실행은 C:\\OpenWebUI\\venv 안의 open-webui.exe를 실행합니다.\n"
                "③ Local AI Chat 버튼은 http://localhost:8080/ 채팅 화면을 엽니다."
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

    def copy_to_clipboard(self, text: str, success_message: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()
        messagebox.showinfo(APP_NAME, success_message)

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
                "설치가 끝나면 실행 명령은 C:\\OpenWebUI\\venv\\Scripts\\open-webui.exe serve 를 사용합니다.",
            )
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"설치 CMD 창을 시작하지 못했습니다.\n\n{exc}")

    def upgrade_python_pip(self) -> None:
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
            self.after(0, lambda: self._ollama_models_failed(str(exc), show_errors))
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

    def open_mdlive(self) -> None:
        webbrowser.open(MDLIVE_URL)

    def open_mdpro(self) -> None:
        webbrowser.open(MDPRO_URL)

    def server_url(self) -> str:
        host = self.config_data["host"]
        browser_host = "localhost" if host in {"127.0.0.1", "0.0.0.0"} else host
        return f"http://{browser_host}:{self.config_data['port']}/"

    def refresh_installation_detection(self) -> None:
        found = find_open_webui_command()
        self.internal_open_webui_command = found
        if found:
            self.config_data["command"] = f'{quote_cmd_arg(found)} serve'

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
            self.status_var.set("Open WebUI를 시작하고 있습니다. CMD 창을 확인하십시오.")
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

    def start_internal_chat(self) -> None:
        self.refresh_installation_detection()
        if not self.internal_open_webui_command:
            messagebox.showwarning(
                APP_NAME,
                "PC에 직접 설치된 open-webui 실행 파일을 찾지 못했습니다.\n"
                "`Open WebUI 가상환경 설치 실행` 후 `가상환경 실행`을 사용하거나, 설정에서 직접 실행 명령을 지정하십시오.",
            )
            return
        command = f"{quote_cmd_arg(self.internal_open_webui_command)} serve"
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
            messagebox.showerror(APP_NAME, f"CMD 창을 시작하지 못했습니다.\n\n{exc}")
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
            "Open WebUI 서버 프로세스가 종료되었습니다.\n"
            "열려 있는 CMD 창의 오류 메시지를 확인하고 설정의 실행 명령을 점검하십시오.",
        )

    def _server_timeout(self) -> None:
        self.is_starting = False
        self.progress.stop()
        self.configure_server_buttons("normal")
        self.refresh_status()
        messagebox.showwarning(
            APP_NAME,
            "설정된 대기시간 안에 localhost 포트가 열리지 않았습니다.\n"
            "CMD 창의 진행 상태를 확인하십시오.",
        )

    def open_browser(self) -> None:
        webbrowser.open(self.server_url())

    def stop_server(self) -> None:
        if self.server_process and self.server_process.poll() is None:
            try:
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
        # 서버는 유지한다. CMD 창에서 로그를 계속 확인할 수 있다.
        self.destroy()


if __name__ == "__main__":
    if os.name != "nt":
        raise SystemExit("이 실행기는 Windows용입니다.")
    LauncherApp().mainloop()
