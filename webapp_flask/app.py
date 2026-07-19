# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

from services.launcher_service import LauncherWebService


ROOT_DIR = Path(__file__).resolve().parents[1]
DOWNLOAD_EXE_NAME = "OpenWebUI-Local-AI-Launcher-Tabbed-v6.exe"


def create_app(auto_start: bool = False) -> Flask:
    app = Flask(__name__)
    service = LauncherWebService()
    app.config["launcher_service"] = service

    if auto_start:
        service.auto_start_if_enabled()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get(f"/downloads/{DOWNLOAD_EXE_NAME}")
    def download_windows_launcher():
        dist_dir = ROOT_DIR / "dist"
        exe_path = dist_dir / DOWNLOAD_EXE_NAME
        if not exe_path.is_file():
            return jsonify({"ok": False, "message": "다운로드 파일을 찾지 못했습니다."}), 404
        return send_from_directory(dist_dir, DOWNLOAD_EXE_NAME, as_attachment=True)

    @app.get("/api/status")
    def status():
        return jsonify(service.get_status())

    @app.get("/api/config")
    def get_config():
        return jsonify(service.get_config())

    @app.post("/api/runtime/detect")
    def detect_runtime():
        return jsonify(service.detect_runtime())

    @app.post("/api/config")
    def update_config():
        payload = request.get_json(silent=True) or {}
        return jsonify(service.update_config(payload))

    @app.post("/api/server/start")
    def start_server():
        payload = request.get_json(silent=True) or {}
        mode = str(payload.get("mode") or "auto")
        return jsonify(service.start_server(mode))

    @app.post("/api/server/stop")
    def stop_server():
        return jsonify(service.stop_server())

    @app.post("/api/server/open")
    def open_server():
        return jsonify(service.open_server_url())

    @app.post("/api/install/openwebui")
    def install_openwebui():
        return jsonify(service.install_openwebui())

    @app.post("/api/install/pip-upgrade")
    def pip_upgrade():
        return jsonify(service.upgrade_python_pip())

    @app.get("/api/install/venv")
    def check_venv():
        return jsonify(service.check_openwebui_venv())

    @app.get("/api/install/command")
    def install_command():
        return jsonify(service.get_openwebui_install_command())

    @app.get("/api/models")
    def list_models():
        return jsonify(service.list_ollama_models())

    @app.post("/api/models/save")
    def save_model():
        payload = request.get_json(silent=True) or {}
        return jsonify(service.save_selected_model(str(payload.get("model") or "")))

    @app.post("/api/models/install")
    def install_model():
        payload = request.get_json(silent=True) or {}
        return jsonify(service.install_ollama_model(str(payload.get("model") or "")))

    @app.get("/api/models/command")
    def model_command():
        model_name = str(request.args.get("model") or "")
        return jsonify(service.get_model_install_command(model_name))

    @app.get("/api/context-menu")
    def context_menu_status():
        return jsonify(service.get_context_menu_status())

    @app.post("/api/context-menu/register")
    def register_context_menu():
        return jsonify(service.register_context_menu())

    @app.post("/api/context-menu/unregister")
    def unregister_context_menu():
        return jsonify(service.unregister_context_menu())

    @app.get("/api/integrations")
    def integrations():
        return jsonify(service.list_integrations())

    @app.get("/api/citation-guard/function")
    def citation_guard_function():
        return jsonify(service.get_citation_guard_function())

    @app.get("/api/academic-search/tool")
    def academic_search_tool():
        return jsonify(service.get_academic_search_tool())

    @app.post("/api/integrations/open")
    def open_integration():
        payload = request.get_json(silent=True) or {}
        return jsonify(service.open_integration(str(payload.get("id") or "")))

    @app.post("/api/openwebui/chat")
    def openwebui_chat():
        payload = request.get_json(silent=True) or {}
        return jsonify(service.ask_openwebui(str(payload.get("message") or "")))

    @app.post("/api/academic-rag/answer")
    def academic_rag_answer():
        payload = request.get_json(silent=True) or {}
        return jsonify(
            service.ask_academic_rag(
                str(payload.get("question") or ""),
                int(payload.get("max_results") or 8),
            )
        )

    @app.post("/api/academic-rag/search")
    def academic_rag_search():
        payload = request.get_json(silent=True) or {}
        return jsonify(
            service.search_academic_sources(
                str(payload.get("query") or ""),
                int(payload.get("max_results") or 10),
            )
        )

    @app.errorhandler(ValueError)
    def handle_value_error(exc: ValueError):
        return jsonify({"ok": False, "message": str(exc)}), 400

    @app.errorhandler(Exception)
    def handle_exception(exc: Exception):
        app.logger.exception("Unhandled web launcher error")
        return jsonify({"ok": False, "message": str(exc)}), 500

    return app


app = create_app()


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", os.environ.get("HOST", "127.0.0.1"))
    port = int(os.environ.get("FLASK_PORT", os.environ.get("PORT", "8000")))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes", "on"}
    app = create_app(auto_start=True)
    app.run(host=host, port=port, debug=debug, use_reloader=debug)
