"""Read model and tag names from Ollama's public catalog."""
from __future__ import annotations

import re
import urllib.request
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urlencode, urlsplit

MODEL_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)?(?::[A-Za-z0-9][A-Za-z0-9._-]*)?\Z")


def _model_from_href(href: str) -> str | None:
    parts = urlsplit(href)
    if parts.scheme and (parts.scheme != "https" or parts.netloc.lower() not in {"ollama.com", "www.ollama.com"}):
        return None
    path = unquote(parts.path).strip("/")
    if path.startswith("library/"):
        path = path[len("library/"):]
    elif "/" not in path:
        return None
    if not MODEL_PATTERN.fullmatch(path):
        return None
    if path.split("/", 1)[0].lower() in {"search", "settings", "download", "blog", "docs"}:
        return None
    return path


class CatalogParser(HTMLParser):
    def __init__(self, tags_for: str | None = None):
        super().__init__(convert_charrefs=True)
        self.tags_for = tags_for
        self.models: list[str] = []
        self._li_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "li":
            self._li_depth += 1
        if tag != "a" or (self.tags_for is None and not self._li_depth):
            return
        name = _model_from_href(dict(attrs).get("href") or "")
        if not name:
            return
        if self.tags_for is None:
            if ":" in name:
                return
        elif not name.startswith(self.tags_for + ":"):
            return
        if name not in self.models:
            self.models.append(name)

    def handle_endtag(self, tag: str) -> None:
        if tag == "li" and self._li_depth:
            self._li_depth -= 1


def _fetch(path: str) -> str:
    request = urllib.request.Request("https://ollama.com" + path,
                                     headers={"User-Agent": "OpenWebUI-Local-Launcher/1.0", "Accept": "text/html"})
    with urllib.request.urlopen(request, timeout=15) as response:
        destination = urlsplit(response.geturl())
        if destination.scheme != "https" or destination.hostname not in {"ollama.com", "www.ollama.com"}:
            raise RuntimeError("Ollama 검색 페이지 주소가 예상과 다릅니다.")
        body = response.read(3 * 1024 * 1024 + 1)
    if len(body) > 3 * 1024 * 1024:
        raise RuntimeError("Ollama 검색 결과가 너무 큽니다.")
    return body.decode("utf-8", errors="replace")


def search_models(query: str) -> list[str]:
    parser = CatalogParser()
    parser.feed(_fetch("/search?" + urlencode({"q": query.strip()})))
    return parser.models


def model_tags(model: str) -> list[str]:
    if not MODEL_PATTERN.fullmatch(model) or ":" in model:
        raise ValueError("모델 이름이 올바르지 않습니다.")
    model_path = ("/library/" if "/" not in model else "/") + quote(model, safe="/")
    parser = CatalogParser(tags_for=model)
    parser.feed(_fetch(model_path + "/tags"))
    return parser.models
