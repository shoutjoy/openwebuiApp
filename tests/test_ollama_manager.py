import json
import io
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, mock_open
from urllib.error import HTTPError

import ollama_manager as manager


class OllamaManagerTests(unittest.TestCase):
    def test_api_model_list_load_and_error(self):
        opener = MagicMock()
        with patch.object(manager.urllib.request, "build_opener", return_value=opener):
            opener.open.return_value.__enter__ = Mock(return_value=io.BytesIO(b'{"models":[{"name":"gemma4:e2b"}]}'))
            opener.open.return_value.__exit__ = Mock(return_value=False)
            self.assertEqual(manager.api_request("/api/tags")["models"][0]["name"], "gemma4:e2b")
            request = {"model": "gemma4:e2b", "prompt": "", "stream": False, "keep_alive": "5m"}
            opener.open.return_value.__enter__.return_value = io.BytesIO(b'{"done":true}')
            self.assertTrue(manager.api_request("/api/generate", request)["done"])
            self.assertEqual(json.loads(opener.open.call_args.args[0].data), request)
            opener.open.side_effect = HTTPError("url", 404, "missing", {}, io.BytesIO(b'{"error":"model not found"}'))
            with self.assertRaisesRegex(RuntimeError, "model not found"):
                manager.api_request("/api/generate", {"model": "missing"})

    def test_conflict_does_not_start_or_stop_external_process(self):
        with patch.object(manager, "port_in_use", return_value=True), patch.object(manager.subprocess, "Popen") as popen:
            server = manager.OllamaManager(Path("."))
            with self.assertRaisesRegex(RuntimeError, "11434"):
                server.start("ollama", manager.DEFAULT_ORIGINS)
            with self.assertRaisesRegex(RuntimeError, "런처"):
                server.stop()
            popen.assert_not_called()

    def test_start_passes_origins_and_stop_targets_owned_process(self):
        proc = Mock()
        proc.poll.return_value = None
        with patch.object(Path, "mkdir"), patch.object(Path, "open", mock_open()), patch.object(manager, "port_in_use", return_value=False), patch.object(manager.subprocess, "Popen", return_value=proc) as popen:
            server = manager.OllamaManager(Path("."))
            server.start("ollama", "https://example.org")
            self.assertEqual(popen.call_args.args[0], ["ollama", "serve"])
            self.assertEqual(popen.call_args.kwargs["env"]["OLLAMA_ORIGINS"], "https://example.org")
            self.assertEqual(popen.call_args.kwargs["env"]["OLLAMA_HOST"], "127.0.0.1:11434")
            server.stop()
            proc.terminate.assert_called_once()
            self.assertIsNone(server.process)

    def test_commands_quote_origin(self):
        self.assertIn("'https://site.test'", manager.serve_command("https://site.test", True))
        self.assertIn("'https://site.test;other'", manager.serve_command("https://site.test;other", False))

    def test_server_probe_distinguishes_stopped_running_and_unverified(self):
        with patch.object(manager, "port_in_use", return_value=False), patch.object(manager, "api_request") as api:
            self.assertEqual(manager.probe_server(), "stopped")
            api.assert_not_called()
        with patch.object(manager, "port_in_use", return_value=True), patch.object(manager, "api_request", return_value={"version": "0.12"}):
            self.assertEqual(manager.probe_server(), "running")
        with patch.object(manager, "port_in_use", return_value=True), patch.object(manager, "api_request", side_effect=OSError("unavailable")):
            self.assertEqual(manager.probe_server(), "unknown")
        with patch.object(manager, "port_in_use", return_value=True), patch.object(manager, "api_request", return_value={}):
            self.assertEqual(manager.probe_server(), "unknown")

    def test_windows_listener_parsing_excludes_other_ports_and_connections(self):
        output = ('  TCP    127.0.0.1:11434  0.0.0.0:0  LISTENING  123\n'
                  '  TCP    [::]:11434  [::]:0  LISTENING  124\n'
                  '  TCP    127.0.0.1:11434  127.0.0.1:51234  ESTABLISHED  125\n'
                  '  TCP    127.0.0.1:8080  0.0.0.0:0  LISTENING  126\n')
        with patch.object(manager.os, "name", "nt"), patch.object(manager.subprocess, "check_output", return_value=output):
            self.assertEqual(manager.listening_pids(), {123, 124})

    def test_external_ollama_stop_verifies_ownership_and_release(self):
        with patch.object(manager.os, "name", "nt"), \
             patch.object(manager, "listening_pids", side_effect=[{123}, {123}, set(), set()]), \
             patch.object(manager, "process_name", return_value="ollama.exe"), \
             patch.object(manager.subprocess, "run") as run, patch.object(manager.time, "sleep"):
            manager.stop_external_ollama()
            self.assertEqual(run.call_args.args[0], ["taskkill", "/PID", "123", "/T", "/F"])

    def test_external_stop_never_kills_unknown_or_managed_listener(self):
        with patch.object(manager.os, "name", "nt"), patch.object(manager, "listening_pids", return_value={123, 124}), \
             patch.object(manager, "process_name", side_effect=lambda pid: "ollama.exe" if pid == 123 else "other.exe"), \
             patch.object(manager.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "확인되지"):
                manager.stop_external_ollama()
            with self.assertRaisesRegex(RuntimeError, "서버 정지"):
                manager.stop_external_ollama(managed_pid=123)
            run.assert_not_called()

    def test_external_stop_refuses_changed_owner(self):
        with patch.object(manager.os, "name", "nt"), \
             patch.object(manager, "listening_pids", side_effect=[{123}, {124}]), \
             patch.object(manager, "process_name", return_value="ollama.exe"), \
             patch.object(manager.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "변경"):
                manager.stop_external_ollama()
            run.assert_not_called()

    def test_mac_external_stop_and_automatic_restart_detection(self):
        with patch.object(manager.os, "name", "posix"), patch.object(manager.sys, "platform", "darwin"), \
             patch.object(manager, "listening_pids", side_effect=[{123}, {123}] + [{456}] * 30), \
             patch.object(manager, "process_name", return_value="ollama"), \
             patch.object(manager.os, "kill") as kill, patch.object(manager.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "다시 실행"):
                manager.stop_external_ollama()
            kill.assert_called_once_with(123, manager.signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
