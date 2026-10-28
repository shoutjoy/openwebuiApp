"""Local Ollama process and API helpers used by the desktop launcher."""
from __future__ import annotations

import json
import csv
import io
import os
import shlex
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_ORIGINS = "http://localhost:8080,http://127.0.0.1:8080,http://localhost:8000,http://127.0.0.1:8000"


def port_in_use() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=0.4):
            return True
    except OSError:
        return False


def api_request(path: str, payload: dict | None = None, timeout: float = 3) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(OLLAMA_URL + path, data=data, headers={"Content-Type": "application/json"})
    try:
        # Do not route local requests through an environment-configured proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read(4096).decode("utf-8", errors="replace")
        finally:
            exc.close()
        raise RuntimeError(f"Ollama HTTP {exc.code}: {detail}") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Ollama에서 예상하지 못한 응답을 받았습니다.")
    if result.get("error"):
        raise RuntimeError(str(result["error"]))
    return result


def probe_server() -> str:
    """Distinguish a responding Ollama API from a stopped or occupied port."""
    if not port_in_use():
        return "stopped"
    try:
        version = api_request("/api/version", timeout=1).get("version")
        return "running" if isinstance(version, str) and version else "unknown"
    except Exception:
        return "unknown"


def serve_command(origins: str, windows: bool) -> str:
    if windows:
        value = origins.replace("'", "''")
        return f"$env:OLLAMA_HOST = '127.0.0.1:11434'; $env:OLLAMA_ORIGINS = '{value}'; ollama serve"
    return f"OLLAMA_HOST=127.0.0.1:11434 OLLAMA_ORIGINS={shlex.quote(origins)} ollama serve"


def listening_pids() -> set[int]:
    """Find TCP listeners on port 11434, including wildcard and IPv6 bindings."""
    if os.name == "nt":
        output = subprocess.check_output(["netstat", "-ano", "-p", "tcp"], text=True,
                                         errors="replace", timeout=10, creationflags=0x08000000)
        pids = set()
        for line in output.splitlines():
            fields = line.split()
            if len(fields) >= 5 and fields[0].upper() == "TCP" and fields[1].rsplit(":", 1)[-1] == "11434" and fields[3].upper() == "LISTENING" and fields[4].isdigit():
                pids.add(int(fields[4]))
        return pids
    if sys.platform == "darwin":
        result = subprocess.run(["/usr/sbin/lsof", "-nP", "-iTCP:11434", "-sTCP:LISTEN", "-t"],
                                capture_output=True, text=True, errors="replace", timeout=10)
        if result.returncode not in (0, 1):
            raise RuntimeError(f"포트 사용 프로세스를 확인하지 못했습니다: {result.stderr.strip()}")
        if result.returncode == 1 and result.stderr.strip():
            raise RuntimeError(f"포트 사용 프로세스를 확인하지 못했습니다: {result.stderr.strip()}")
        return {int(line) for line in result.stdout.splitlines() if line.isdigit()}
    raise RuntimeError("기존 서버 종료는 Windows와 macOS에서 지원됩니다.")


def process_name(pid: int) -> str:
    if os.name == "nt":
        output = subprocess.check_output(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                                         text=True, errors="replace", timeout=10, creationflags=0x08000000)
        rows = list(csv.reader(io.StringIO(output)))
        if len(rows) != 1 or len(rows[0]) < 2 or rows[0][1].strip() != str(pid):
            raise RuntimeError(f"PID {pid}의 실행 파일을 확인하지 못했습니다.")
        return rows[0][0].strip().lower()
    output = subprocess.check_output(["/bin/ps", "-p", str(pid), "-o", "comm="],
                                     text=True, errors="replace", timeout=10).strip()
    return Path(output).name.lower()


def stop_external_ollama(managed_pid: int | None = None) -> None:
    """Stop only verified Ollama listeners; never terminate unrelated port owners."""
    pids = listening_pids()
    if not pids:
        raise RuntimeError("11434 포트에서 실행 중인 서버를 찾지 못했습니다.")
    allowed = {"ollama.exe", "ollama app.exe"} if os.name == "nt" else {"ollama"}
    if managed_pid in pids:
        raise RuntimeError("이 런처가 실행한 서버입니다. '서버 정지' 버튼을 사용하십시오.")
    names = {pid: process_name(pid) for pid in pids}
    unknown = {pid: name for pid, name in names.items() if name not in allowed}
    if unknown:
        detail = ", ".join(f"{name} (PID {pid})" for pid, name in unknown.items())
        raise RuntimeError(f"11434 포트 소유자가 Ollama로 확인되지 않아 종료하지 않았습니다: {detail}")
    # Recheck ownership and identity just before termination.
    if listening_pids() != pids or any(process_name(pid) != names[pid] for pid in pids):
        raise RuntimeError("포트 소유자가 변경되어 서버를 종료하지 않았습니다. 다시 시도하십시오.")
    for pid in sorted(pids):
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=10,
                           creationflags=0x08000000)
        else:
            os.kill(pid, signal.SIGTERM)
    # The desktop app can relaunch its server; don't report success until it stays down.
    for _ in range(30):
        time.sleep(0.1)
        if not listening_pids():
            time.sleep(0.5)
            if not listening_pids():
                return
    raise RuntimeError("서버가 종료되지 않았거나 Ollama 앱이 다시 실행했습니다. 트레이 또는 메뉴 막대에서 Ollama 앱을 종료하십시오.")


class OllamaManager:
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.process: subprocess.Popen | None = None
        self.origins: str | None = None

    def start(self, executable: str, origins: str) -> None:
        if not origins.strip() or any(c in origins for c in "\r\n\x00"):
            raise ValueError("허용할 Origin을 쉼표로 입력하십시오.")
        if port_in_use():
            raise RuntimeError("11434 포트가 이미 사용 중입니다. 기존 Ollama 앱을 종료한 뒤 다시 시작하십시오.")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["OLLAMA_ORIGINS"] = origins.strip()
        # A user-level OLLAMA_HOST must not silently move the managed service.
        env["OLLAMA_HOST"] = "127.0.0.1:11434"
        with (self.log_dir / "ollama-server.log").open("a", encoding="utf-8") as log:
            self.process = subprocess.Popen([executable, "serve"], env=env, stdout=log,
                                            stderr=subprocess.STDOUT,
                                            creationflags=0x08000000 if os.name == "nt" else 0,
                                            start_new_session=os.name != "nt")
        self.origins = origins.strip()

    def is_managed_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def stop(self) -> None:
        if not self.is_managed_running():
            raise RuntimeError("이 런처에서 시작한 Ollama 서버가 없습니다. 기존 Ollama 앱에서 종료하십시오.")
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.process = None
        self.origins = None
