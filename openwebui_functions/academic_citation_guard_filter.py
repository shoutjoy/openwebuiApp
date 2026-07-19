"""
title: Academic Citation Guard
author: Joonghee Park PhD
version: 1.0.0
description: Prevents fabricated academic citations by injecting verified Semantic Scholar/arXiv/Crossref/OpenAlex metadata and warning on unverified references.
required_open_webui_version: 0.9.0
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Optional

from pydantic import BaseModel, Field


ACADEMIC_HINT_RE = re.compile(
    r"(논문|학술|연구|인용|참고문헌|출처|저자|연도|doi|pubmed|scholar|"
    r"paper|article|study|studies|research|citation|reference|references|bibliography|journal)",
    re.IGNORECASE,
)
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
SOURCE_ID_RE = re.compile(r"\[(C\d+)\]")
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


class Filter:
    class Valves(BaseModel):
        ENABLE_RETRIEVAL: bool = Field(
            default=True,
            description="Search Semantic Scholar/arXiv/Crossref/OpenAlex for academic metadata on citation-like prompts.",
        )
        ALWAYS_RETRIEVE: bool = Field(
            default=False,
            description="Run retrieval for every prompt. Leave off to avoid slowing normal chat.",
        )
        MAX_RESULTS: int = Field(
            default=5,
            ge=1,
            le=10,
            description="Maximum verified citation candidates to inject.",
        )
        TIMEOUT_SECONDS: float = Field(
            default=5.0,
            ge=1.0,
            le=20.0,
            description="HTTP timeout per metadata source.",
        )
        CONTACT_EMAIL: str = Field(
            default="",
            description="Optional contact email for Crossref polite API usage.",
        )
        SEMANTIC_SCHOLAR_API_KEY: str = Field(
            default="",
            description="Optional Semantic Scholar API key for higher rate limits.",
        )
        ENABLE_ARXIV: bool = Field(
            default=True,
            description="Also search arXiv for preprints. Turn off if arXiv rate limits slow requests.",
        )
        ARXIV_TIMEOUT_SECONDS: float = Field(
            default=3.0,
            ge=1.0,
            le=10.0,
            description="Separate arXiv timeout because the public API may rate limit.",
        )
        OUTPUT_POLICY: str = Field(
            default="warn_append",
            description="warn_append keeps the answer and adds a warning; replace_unverified replaces citation-heavy unverified answers.",
            json_schema_extra={"enum": ["warn_append", "replace_unverified"]},
        )
        SHOW_STATUS: bool = Field(
            default=True,
            description="Show retrieval status messages in the Open WebUI chat UI.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def inlet(
        self,
        body: dict,
        __event_emitter__=None,
        __user__: Optional[dict] = None,
        __model__: Optional[dict] = None,
    ) -> dict:
        messages = body.get("messages") or []
        user_text = self._last_user_text(messages)
        should_retrieve = bool(
            self.valves.ENABLE_RETRIEVAL
            and user_text
            and (self.valves.ALWAYS_RETRIEVE or ACADEMIC_HINT_RE.search(user_text))
        )

        works: list[dict[str, Any]] = []
        if should_retrieve:
            await self._emit(__event_emitter__, "검증된 학술 메타데이터를 검색합니다.", False)
            works = self._retrieve_works(user_text)
            await self._emit(
                __event_emitter__,
                f"검증 후보 {len(works)}개를 찾았습니다." if works else "검증 후보를 찾지 못했습니다.",
                True,
            )

        self._inject_guard_instruction(body, works)
        body.setdefault("metadata", {})["academic_citation_guard"] = {
            "source_ids": [work["id"] for work in works],
            "dois": [work["doi"] for work in works if work.get("doi")],
            "titles": [work["title"] for work in works if work.get("title")],
            "created_at": int(time.time()),
        }
        return body

    async def outlet(
        self,
        body: dict,
        __event_emitter__=None,
        __user__: Optional[dict] = None,
    ) -> dict:
        messages = body.get("messages") or []
        content = self._last_assistant_text(messages)
        if not content:
            return body

        verification = self._extract_verification_context(body)
        warning = self._build_output_warning(content, verification)
        if not warning:
            return body

        if self.valves.OUTPUT_POLICY == "replace_unverified" and self._has_bibliography(content):
            content = (
                "이 답변에는 검증 후보에 없는 참고문헌 또는 출처 ID가 포함되어 표시를 중단했습니다.\n\n"
                + warning
            )
        else:
            content = content.rstrip() + "\n\n" + warning

        self._set_last_assistant_text(messages, content)
        await self._emit(__event_emitter__, "검증되지 않은 인용 가능성을 표시했습니다.", True)
        return body

    def _retrieve_works(self, query: str) -> list[dict[str, Any]]:
        max_results = int(self.valves.MAX_RESULTS)
        works: list[dict[str, Any]] = []
        for item in self._search_semantic_scholar(query, max_results):
            works.append(item)
        if self.valves.ENABLE_ARXIV:
            for item in self._search_arxiv(query, max_results):
                works.append(item)
        for item in self._search_crossref(query, max_results):
            works.append(item)
        for item in self._search_openalex(query, max_results):
            works.append(item)
        return self._dedupe_works(works)[:max_results]

    def _search_semantic_scholar(self, query: str, max_results: int) -> list[dict[str, Any]]:
        params = {
            "query": query[:500].replace("-", " "),
            "limit": str(max_results),
            "fields": "title,authors,year,venue,externalIds,url",
        }
        url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(params)
        headers = {}
        if self.valves.SEMANTIC_SCHOLAR_API_KEY.strip():
            headers["x-api-key"] = self.valves.SEMANTIC_SCHOLAR_API_KEY.strip()
        try:
            data = self._get_json(url, headers)
        except Exception:
            return []

        items = data.get("data") or [] if isinstance(data, dict) else []
        works = []
        for raw in items:
            title = raw.get("title") or ""
            if not title:
                continue
            external_ids = raw.get("externalIds") or {}
            doi = external_ids.get("DOI") or ""
            works.append(
                {
                    "id": "",
                    "source": "Semantic Scholar",
                    "title": title,
                    "authors": self._format_semantic_scholar_authors(raw.get("authors") or []),
                    "year": raw.get("year"),
                    "doi": self._clean_doi(doi),
                    "venue": raw.get("venue") or "",
                    "url": raw.get("url") or "",
                }
            )
        return works

    def _search_arxiv(self, query: str, max_results: int) -> list[dict[str, Any]]:
        quoted_query = '"' + query[:240].replace('"', " ").strip() + '"'
        params = {
            "search_query": f"all:{quoted_query}",
            "start": "0",
            "max_results": str(max_results),
        }
        url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "OpenWebUI-Academic-Citation-Guard/1.0"},
            )
            with urllib.request.urlopen(request, timeout=float(self.valves.ARXIV_TIMEOUT_SECONDS)) as response:
                text = response.read().decode("utf-8", errors="replace")
        except Exception:
            return []

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return []

        works = []
        for entry in root.findall("atom:entry", ns):
            title = self._clean_space(self._xml_text(entry.find("atom:title", ns)))
            if not title:
                continue
            authors = []
            for author in entry.findall("atom:author", ns)[:6]:
                name = self._clean_space(self._xml_text(author.find("atom:name", ns)))
                if name:
                    authors.append(name)
            published = self._xml_text(entry.find("atom:published", ns))
            doi = self._xml_text(entry.find("arxiv:doi", ns))
            journal_ref = self._xml_text(entry.find("arxiv:journal_ref", ns))
            arxiv_url = self._xml_text(entry.find("atom:id", ns))
            works.append(
                {
                    "id": "",
                    "source": "arXiv",
                    "title": title,
                    "authors": ", ".join(authors),
                    "year": int(published[:4]) if published[:4].isdigit() else None,
                    "doi": self._clean_doi(doi),
                    "venue": self._clean_space(journal_ref) or "arXiv",
                    "url": arxiv_url,
                }
            )
        return works

    def _search_crossref(self, query: str, max_results: int) -> list[dict[str, Any]]:
        params = {
            "query.bibliographic": query[:500],
            "rows": str(max_results),
            "select": "DOI,title,author,issued,container-title,URL,type",
        }
        if self.valves.CONTACT_EMAIL.strip():
            params["mailto"] = self.valves.CONTACT_EMAIL.strip()
        url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
        try:
            data = self._get_json(url)
        except Exception:
            return []

        items = ((data.get("message") or {}).get("items") or []) if isinstance(data, dict) else []
        works = []
        for raw in items:
            title = self._first(raw.get("title"))
            if not title:
                continue
            works.append(
                {
                    "id": "",
                    "source": "Crossref",
                    "title": title,
                    "authors": self._format_crossref_authors(raw.get("author") or []),
                    "year": self._crossref_year(raw.get("issued")),
                    "doi": self._clean_doi(raw.get("DOI")),
                    "venue": self._first(raw.get("container-title")),
                    "url": raw.get("URL") or "",
                }
            )
        return works

    def _search_openalex(self, query: str, max_results: int) -> list[dict[str, Any]]:
        params = {
            "search": query[:500],
            "per-page": str(max_results),
            "select": "id,doi,title,publication_year,authorships,primary_location,type",
        }
        if self.valves.CONTACT_EMAIL.strip():
            params["mailto"] = self.valves.CONTACT_EMAIL.strip()
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
        try:
            data = self._get_json(url)
        except Exception:
            return []

        items = data.get("results") or [] if isinstance(data, dict) else []
        works = []
        for raw in items:
            title = raw.get("title") or ""
            if not title:
                continue
            location = raw.get("primary_location") or {}
            source = location.get("source") or {}
            works.append(
                {
                    "id": "",
                    "source": "OpenAlex",
                    "title": title,
                    "authors": self._format_openalex_authors(raw.get("authorships") or []),
                    "year": raw.get("publication_year"),
                    "doi": self._clean_doi(raw.get("doi")),
                    "venue": source.get("display_name") or "",
                    "url": raw.get("doi") or raw.get("id") or "",
                }
            )
        return works

    def _get_json(self, url: str, extra_headers: Optional[dict[str, str]] = None) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "OpenWebUI-Academic-Citation-Guard/1.0",
        }
        headers.update(extra_headers or {})
        request = urllib.request.Request(
            url,
            headers=headers,
        )
        with urllib.request.urlopen(request, timeout=float(self.valves.TIMEOUT_SECONDS)) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))

    def _dedupe_works(self, works: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for work in works:
            key = work.get("doi") or self._normalize_title(work.get("title", ""))
            if not key or key in seen:
                continue
            seen.add(key)
            work = dict(work)
            work["id"] = f"C{len(deduped) + 1}"
            deduped.append(work)
        return deduped

    def _inject_guard_instruction(self, body: dict, works: list[dict[str, Any]]) -> None:
        messages = body.setdefault("messages", [])
        guard = self._guard_prompt(works)
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = str(messages[0].get("content") or "").rstrip() + "\n\n" + guard
        else:
            messages.insert(0, {"role": "system", "content": guard})

    def _guard_prompt(self, works: list[dict[str, Any]]) -> str:
        lines = [
            "[Academic Citation Guard]",
            "You must not invent academic citation metadata, authors, years, venues, page ranges, or DOI values.",
            "If the user asks for papers, studies, citations, or references, use only the verified citation candidates below.",
            "Every cited paper must include its source id like [C1].",
            "If no candidate supports a requested citation, say in Korean: 검증된 인용 정보가 없습니다.",
            "Do not output a bibliography entry unless it exactly matches one of the verified candidates.",
        ]
        if not works:
            lines.append("Verified citation candidates: none.")
            return "\n".join(lines)

        lines.append("Verified citation candidates:")
        for work in works:
            parts = [
                f"- [{work['id']}]",
                f"title: {work.get('title') or 'unknown'}",
                f"authors: {work.get('authors') or 'unknown'}",
                f"year: {work.get('year') or 'unknown'}",
                f"venue: {work.get('venue') or 'unknown'}",
                f"doi: {work.get('doi') or 'unavailable'}",
                f"metadata_source: {work.get('source') or 'unknown'}",
            ]
            lines.append("; ".join(parts))
        return "\n".join(lines)

    def _extract_verification_context(self, body: dict) -> dict[str, set[str]]:
        metadata = (body.get("metadata") or {}).get("academic_citation_guard") or {}
        source_ids = {str(value).upper() for value in metadata.get("source_ids") or []}
        dois = {self._clean_doi(value) for value in metadata.get("dois") or [] if self._clean_doi(value)}
        titles = {self._normalize_title(value) for value in metadata.get("titles") or [] if value}

        for message in body.get("messages") or []:
            content = str(message.get("content") or "")
            if "[Academic Citation Guard]" not in content:
                continue
            source_ids.update(match.upper() for match in SOURCE_ID_RE.findall(content))
            dois.update(self._clean_doi(match) for match in DOI_RE.findall(content))
            for line in content.splitlines():
                if "title:" in line:
                    title = line.split("title:", 1)[1].split("; authors:", 1)[0].strip()
                    if title:
                        titles.add(self._normalize_title(title))

        return {
            "source_ids": {value for value in source_ids if value},
            "dois": {value for value in dois if value},
            "titles": {value for value in titles if value},
        }

    def _build_output_warning(self, content: str, verification: dict[str, set[str]]) -> str:
        has_citation_content = self._has_bibliography(content) or bool(DOI_RE.search(content))
        used_source_ids = {match.upper() for match in SOURCE_ID_RE.findall(content)}
        used_dois = {self._clean_doi(match) for match in DOI_RE.findall(content)}
        allowed_source_ids = verification.get("source_ids") or set()
        allowed_dois = verification.get("dois") or set()

        problems: list[str] = []
        if used_source_ids and allowed_source_ids:
            unknown = sorted(used_source_ids - allowed_source_ids)
            if unknown:
                problems.append("허용되지 않은 출처 ID: " + ", ".join(unknown))

        if used_dois and allowed_dois:
            unknown_dois = sorted(used_dois - allowed_dois)
            if unknown_dois:
                problems.append("검색 후보에 없는 DOI: " + ", ".join(unknown_dois))

        if has_citation_content and allowed_source_ids and not used_source_ids:
            problems.append("참고문헌 형식의 내용이 있지만 검증 출처 ID([C1] 등)가 없습니다.")

        if has_citation_content and not allowed_source_ids:
            problems.append("검증된 학술 메타데이터 후보 없이 참고문헌 형식의 내용이 생성되었습니다.")

        if not problems:
            return ""

        return (
            "> [!WARNING]\n"
            "> Academic Citation Guard: 이 답변의 인용 정보는 검증된 외부 메타데이터와 일치하지 않을 수 있습니다. "
            + " ".join(problems)
            + " 실제 제출/논문 작성 전 Semantic Scholar, arXiv, Crossref, OpenAlex, PubMed, 원문 DOI에서 다시 확인하십시오."
        )

    def _has_bibliography(self, content: str) -> bool:
        lowered = content.lower()
        if any(token in lowered for token in ["참고문헌", "references", "bibliography"]):
            return True
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        suspicious = 0
        for line in lines:
            if YEAR_RE.search(line) and ("," in line or "." in line) and len(line) > 40:
                suspicious += 1
        return suspicious >= 2

    async def _emit(self, emitter, description: str, done: bool) -> None:
        if not emitter or not self.valves.SHOW_STATUS:
            return
        try:
            await emitter(
                {
                    "type": "status",
                    "data": {"description": description, "done": done, "hidden": False},
                }
            )
        except Exception:
            return

    def _last_user_text(self, messages: list[dict[str, Any]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user":
                return self._content_to_text(message.get("content"))
        return ""

    def _last_assistant_text(self, messages: list[dict[str, Any]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "assistant":
                return self._content_to_text(message.get("content"))
        return ""

    def _set_last_assistant_text(self, messages: list[dict[str, Any]], content: str) -> None:
        for message in reversed(messages):
            if message.get("role") == "assistant":
                message["content"] = content
                return

    def _content_to_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text") or ""))
                elif isinstance(item, str):
                    parts.append(item)
            return "\n".join(parts)
        return str(content or "")

    def _format_crossref_authors(self, authors: list[dict[str, Any]]) -> str:
        names = []
        for author in authors[:6]:
            family = author.get("family") or ""
            given = author.get("given") or ""
            name = " ".join(part for part in [given, family] if part).strip()
            if name:
                names.append(name)
        return ", ".join(names)

    def _format_semantic_scholar_authors(self, authors: list[dict[str, Any]]) -> str:
        names = []
        for author in authors[:6]:
            name = author.get("name") or ""
            if name:
                names.append(name)
        return ", ".join(names)

    def _format_openalex_authors(self, authorships: list[dict[str, Any]]) -> str:
        names = []
        for authorship in authorships[:6]:
            author = authorship.get("author") or {}
            name = author.get("display_name") or ""
            if name:
                names.append(name)
        return ", ".join(names)

    def _crossref_year(self, issued: Any) -> Optional[int]:
        try:
            parts = issued.get("date-parts") or []
            return int(parts[0][0]) if parts and parts[0] else None
        except Exception:
            return None

    def _clean_doi(self, value: Any) -> str:
        text = str(value or "").strip()
        text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text, flags=re.IGNORECASE)
        return text.lower().rstrip(".,;)")

    def _first(self, value: Any) -> str:
        if isinstance(value, list):
            return str(value[0]).strip() if value else ""
        return str(value or "").strip()

    def _normalize_title(self, value: str) -> str:
        return re.sub(r"[^a-z0-9가-힣]+", " ", str(value).lower()).strip()

    def _xml_text(self, element: Optional[ET.Element]) -> str:
        return element.text if element is not None and element.text else ""

    def _clean_space(self, value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()
