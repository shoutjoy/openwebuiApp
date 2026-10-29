import io
import json
import unittest
from email.message import Message
from unittest.mock import MagicMock, patch

import local_chat_server as chat


def handler(path, *, origin=None, body=b"", content_type="application/json", host=None):
    request = chat.ChatHandler.__new__(chat.ChatHandler)
    request.path = path
    request.headers = Message()
    request.headers["Host"] = host or f"{chat.HOST}:{chat.PORT}"
    request.headers["Content-Type"] = content_type
    request.headers["Content-Length"] = str(len(body))
    if origin is not None:
        request.headers["Origin"] = origin
    request.rfile = io.BytesIO(body)
    request.wfile = io.BytesIO()
    request.send_response = MagicMock()
    request.send_header = MagicMock()
    request.end_headers = MagicMock()
    return request


class LocalChatTests(unittest.TestCase):
    def test_bundled_html_uses_local_proxy(self):
        text = chat.chat_asset_path().read_text(encoding="utf-8")
        self.assertIn("window.location.origin + '/ollama'", text)
        self.assertIn('src="https://unpkg.com/react@18/', text)
        self.assertNotIn("sourceMappingURL=data:application/json", text)

    def test_stream_and_tags_route_to_fixed_local_ollama(self):
        response = MagicMock()
        response.status = 200
        response.headers = {"Content-Type": "application/x-ndjson"}
        response.read1.side_effect = [b'{"message":"first"}\n', b'{"done":true}\n', b""]
        opener = MagicMock()
        opener.open.return_value = response
        data = b'{"model":"gemma4:e2b","stream":true}'
        request = handler("/ollama/api/chat", origin=chat.ORIGIN, body=data)
        with patch.object(chat.urllib.request, "build_opener", return_value=opener):
            request.do_POST()
        upstream = opener.open.call_args.args[0]
        self.assertEqual(upstream.full_url, chat.OLLAMA_BASE + "/api/chat")
        self.assertEqual(upstream.data, data)
        self.assertEqual(request.wfile.getvalue(), b'{"message":"first"}\n{"done":true}\n')
        self.assertTrue(request.close_connection)
        request = handler("/ollama/api/tags")
        with patch.object(request, "_proxy") as proxy:
            request.do_GET()
            proxy.assert_called_once_with("/api/tags", None)

    def test_rejects_other_origins_hosts_and_paths(self):
        for request in (handler("/ollama/api/chat", origin="https://example.com", body=b"{}"),
                        handler("/ollama/api/chat", origin=chat.ORIGIN, body=b"{}", host="evil.test"),
                        handler("/ollama/api/chat", origin=chat.ORIGIN, body=b"{}", content_type="text/plain"),
                        handler("/ollama/api/delete", origin=chat.ORIGIN, body=b"{}")):
            with patch.object(request, "_proxy") as proxy:
                request.do_POST()
                proxy.assert_not_called()
                self.assertIn(request.send_response.call_args.args[0], (403, 404, 415))

    def test_backend_failure_is_json(self):
        request = handler("/ollama/api/tags")
        with patch.object(chat.urllib.request, "build_opener") as build:
            build.return_value.open.side_effect = OSError("not running")
            request.do_GET()
        self.assertEqual(request.send_response.call_args.args[0], 502)
        self.assertIn("Ollama", json.loads(request.wfile.getvalue())["error"])


if __name__ == "__main__":
    unittest.main()
