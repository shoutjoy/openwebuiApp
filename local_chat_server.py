"""Serve the bundled test chat and proxy only its local Ollama API calls."""
from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8768
ORIGIN = f"http://{HOST}:{PORT}"
OLLAMA_BASE = "http://127.0.0.1:11434"
MAX_BODY = 32 * 1024 * 1024


def chat_asset_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "local_chat" / "ollama-say.html"


class ChatHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        pass

    def _valid_host(self) -> bool:
        return self.headers.get("Host", "").lower() == f"{HOST}:{PORT}"

    def _reply(self, code: int, data: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if getattr(self, "close_connection", False):
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def _error(self, code: int, message: str) -> None:
        self.close_connection = True
        self._reply(code, json.dumps({"error": message}, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        if not self._valid_host():
            return self._error(403, "Invalid host")
        if self.path in ("/", "/ollama-say.html"):
            try:
                page = chat_asset_path().read_bytes()
            except OSError:
                return self._error(500, "채팅 HTML 파일을 읽을 수 없습니다.")
            return self._reply(200, page, "text/html; charset=utf-8")
        if self.path == "/ollama/api/tags":
            return self._proxy("/api/tags", None)
        self._error(404, "Not found")

    def do_POST(self) -> None:
        if not self._valid_host() or self.headers.get("Origin") != ORIGIN:
            return self._error(403, "Invalid origin")
        if self.path != "/ollama/api/chat":
            return self._error(404, "Not found")
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            return self._error(415, "JSON 요청이 필요합니다.")
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 < length <= MAX_BODY:
                raise ValueError
        except ValueError:
            return self._error(413, "요청 크기를 확인하십시오.")
        self._proxy("/api/chat", self.rfile.read(length))

    def _proxy(self, path: str, body: bytes | None) -> None:
        request = urllib.request.Request(OLLAMA_BASE + path, data=body, headers={"Content-Type": "application/json"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            response = opener.open(request, timeout=300)
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read(65536)
                self._reply(exc.code, detail, "application/json; charset=utf-8")
            finally:
                exc.close()
            return
        except (OSError, urllib.error.URLError) as exc:
            return self._error(502, f"Ollama 서버 연결 실패: {exc}")
        with response:
            self.send_response(response.status)
            self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            try:
                while True:
                    chunk = response.read1(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass


class LocalChatServer:
    def __init__(self) -> None:
        self.server: ThreadingHTTPServer | None = None

    def start(self) -> str:
        if self.server is None:
            if not chat_asset_path().is_file():
                raise FileNotFoundError("로컬 테스트 채팅 HTML 파일을 찾지 못했습니다.")
            self.server = ThreadingHTTPServer((HOST, PORT), ChatHandler)
            self.server.daemon_threads = True
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return ORIGIN + "/"

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
