# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from typing import Any

import requests


DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
SOURCE_ID_RE = re.compile(r"\[(C\d+)\]", re.IGNORECASE)
REFERENCE_HEADING_RE = re.compile(
    r"(^|\n)\s{0,3}(#{1,6}\s*)?(참고문헌|References|Bibliography)\s*:?\s*(\n|$)",
    re.IGNORECASE,
)


@dataclass
class AcademicWork:
    id: str
    source: str
    title: str
    authors: str = ""
    year: str = ""
    doi: str = ""
    venue: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    abstract: str = ""
    url: str = ""
    citation: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class AcademicRagService:
    def __init__(self, timeout_seconds: float = 7.0) -> None:
        self.timeout_seconds = timeout_seconds

    def answer(
        self,
        question: str,
        model: str,
        max_results: int = 8,
        ollama_url: str = "http://127.0.0.1:11434",
    ) -> dict[str, Any]:
        question = question.strip()
        if not question:
            return {"ok": False, "message": "질문을 입력하십시오."}

        works = self.search(question, max_results=max_results)
        if not works:
            return {
                "ok": True,
                "answer": "검증된 학술 메타데이터를 찾지 못했습니다. 논문명, 저자명, DOI, 영어 핵심어를 함께 넣어 다시 검색하십시오.",
                "sources": [],
                "model": model,
            }

        prompt = self.build_literature_review_prompt(question, works)
        model_answer = self._call_ollama(ollama_url, model, prompt)
        answer = self._strip_reference_section(model_answer).strip()
        validation_issues = self._validation_issues(answer, works)
        if not any(work.abstract for work in works):
            validation_issues.append("검색 결과에 초록이 없어 본문 내용 추론을 차단했습니다")
        if validation_issues:
            answer = self._build_deterministic_summary(question, works)
            answer += (
                "\n\n> 모델 초안에 검증 검색 결과에 없는 정보가 포함되어, 앱이 검증된 메타데이터 기반 요약으로 대체했습니다. "
                + " / ".join(validation_issues)
            )
        answer = self._append_verified_references(answer, works)

        return {
            "ok": True,
            "answer": answer,
            "sources": [work.to_dict() for work in works],
            "formatted_results": self.format_search_results(question, works),
            "copy_prompt": self.build_literature_review_prompt(question, works),
            "model": model,
            "retrieved_at": int(time.time()),
        }

    def search_package(self, query: str, max_results: int = 10) -> dict[str, Any]:
        query = query.strip()
        if not query:
            return {"ok": False, "message": "검색어를 입력하십시오."}
        works = self.search(query, max_results=max_results)
        return {
            "ok": True,
            "query": query,
            "count": len(works),
            "sources": [work.to_dict() for work in works],
            "formatted_results": self.format_search_results(query, works),
            "copy_prompt": self.build_literature_review_prompt(query, works),
            "retrieved_at": int(time.time()),
        }

    def search(self, query: str, max_results: int = 8) -> list[AcademicWork]:
        query = self._clean_search_query(query)
        source_limit = min(max(max_results * 3, 10), 20)
        raw: list[AcademicWork] = []
        raw.extend(self._search_crossref(query, source_limit))
        raw.extend(self._search_openalex(query, source_limit))
        raw.extend(self._search_semantic_scholar(query, source_limit))
        raw.extend(self._search_pubmed(query, source_limit))
        raw.extend(self._search_arxiv(query, min(source_limit, 8)))
        return self._dedupe(raw, query)[:max_results]

    def _search_crossref(self, query: str, max_results: int) -> list[AcademicWork]:
        params = {
            "query.bibliographic": query[:500],
            "rows": str(max_results),
            "select": "DOI,title,author,issued,container-title,URL,volume,issue,page,abstract",
        }
        url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
        try:
            data = self._get_json(url)
        except Exception:
            return []
        items = ((data.get("message") or {}).get("items") or []) if isinstance(data, dict) else []
        works = []
        for item in items:
            title = self._first(item.get("title"))
            if not title:
                continue
            work = AcademicWork(
                id="",
                source="Crossref",
                title=title,
                authors=self._format_crossref_authors(item.get("author") or []),
                year=self._crossref_year(item.get("issued")),
                doi=self._clean_doi(item.get("DOI")),
                venue=self._first(item.get("container-title")),
                volume=str(item.get("volume") or ""),
                issue=str(item.get("issue") or ""),
                pages=str(item.get("page") or ""),
                abstract=self._clean_html(str(item.get("abstract") or "")),
                url=str(item.get("URL") or ""),
            )
            work.citation = self._format_apa(work)
            works.append(work)
        return works

    def _search_openalex(self, query: str, max_results: int) -> list[AcademicWork]:
        params = {
            "search": query[:500],
            "per-page": str(max_results),
            "select": "id,doi,title,publication_year,authorships,primary_location,biblio,abstract_inverted_index",
        }
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
        try:
            data = self._get_json(url)
        except Exception:
            return []
        items = data.get("results") or [] if isinstance(data, dict) else []
        works = []
        for item in items:
            title = str(item.get("title") or "")
            if not title:
                continue
            location = item.get("primary_location") or {}
            source = location.get("source") or {}
            biblio = item.get("biblio") or {}
            work = AcademicWork(
                id="",
                source="OpenAlex",
                title=title,
                authors=self._format_openalex_authors(item.get("authorships") or []),
                year=str(item.get("publication_year") or ""),
                doi=self._clean_doi(item.get("doi")),
                venue=str(source.get("display_name") or ""),
                volume=str(biblio.get("volume") or ""),
                issue=str(biblio.get("issue") or ""),
                pages=self._openalex_pages(biblio),
                abstract=self._openalex_abstract(item.get("abstract_inverted_index") or {}),
                url=str(item.get("doi") or item.get("id") or ""),
            )
            work.citation = self._format_apa(work)
            works.append(work)
        return works

    def _search_semantic_scholar(self, query: str, max_results: int) -> list[AcademicWork]:
        params = {
            "query": query[:500].replace("-", " "),
            "limit": str(max_results),
            "fields": "title,authors,year,venue,externalIds,url,abstract",
        }
        url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(params)
        try:
            data = self._get_json(url)
        except Exception:
            return []
        items = data.get("data") or [] if isinstance(data, dict) else []
        works = []
        for item in items:
            title = str(item.get("title") or "")
            if not title:
                continue
            external_ids = item.get("externalIds") or {}
            work = AcademicWork(
                id="",
                source="Semantic Scholar",
                title=title,
                authors=self._format_simple_authors(item.get("authors") or []),
                year=str(item.get("year") or ""),
                doi=self._clean_doi(external_ids.get("DOI")),
                venue=str(item.get("venue") or ""),
                abstract=str(item.get("abstract") or ""),
                url=str(item.get("url") or ""),
            )
            work.citation = self._format_apa(work)
            works.append(work)
        return works

    def _search_pubmed(self, query: str, max_results: int) -> list[AcademicWork]:
        params = {
            "db": "pubmed",
            "term": query[:500],
            "retmode": "json",
            "retmax": str(max_results),
        }
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(params)
        try:
            data = self._get_json(search_url)
            ids = ((data.get("esearchresult") or {}).get("idlist") or [])[:max_results]
        except Exception:
            return []
        if not ids:
            return []

        summary_params = {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
        summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" + urllib.parse.urlencode(summary_params)
        try:
            data = self._get_json(summary_url)
        except Exception:
            return []
        result = data.get("result") or {}
        works = []
        for pmid in ids:
            item = result.get(pmid) or {}
            title = self._clean_space(str(item.get("title") or ""))
            if not title:
                continue
            article_ids = item.get("articleids") or []
            doi = ""
            for article_id in article_ids:
                if article_id.get("idtype") == "doi":
                    doi = article_id.get("value") or ""
                    break
            authors = ", ".join((author.get("name") or "") for author in (item.get("authors") or [])[:6] if author.get("name"))
            pages = str(item.get("pages") or "")
            work = AcademicWork(
                id="",
                source="PubMed",
                title=title.rstrip("."),
                authors=authors,
                year=self._pubmed_year(str(item.get("pubdate") or "")),
                doi=self._clean_doi(doi),
                venue=str(item.get("fulljournalname") or item.get("source") or ""),
                volume=str(item.get("volume") or ""),
                issue=str(item.get("issue") or ""),
                pages=pages,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            )
            work.citation = self._format_apa(work)
            works.append(work)
        return works

    def _search_arxiv(self, query: str, max_results: int) -> list[AcademicWork]:
        terms = [term for term in re.split(r"\s+", query[:240]) if len(term) > 2][:8]
        if not terms:
            return []
        search_query = "+AND+".join("all:" + urllib.parse.quote(term) for term in terms)
        url = f"https://export.arxiv.org/api/query?search_query={search_query}&start=0&max_results={max_results}"
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "OpenWebUI-Launcher-Academic-RAG/1.0"})
            with urllib.request.urlopen(request, timeout=3.0) as response:
                text = response.read().decode("utf-8", errors="replace")
            root = ET.fromstring(text)
        except Exception:
            return []
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
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
            work = AcademicWork(
                id="",
                source="arXiv",
                title=title,
                authors=", ".join(authors),
                year=published[:4] if published[:4].isdigit() else "",
                doi=self._clean_doi(doi),
                venue="arXiv",
                url=self._xml_text(entry.find("atom:id", ns)),
            )
            work.citation = self._format_apa(work)
            works.append(work)
        return works

    def _call_ollama(self, ollama_url: str, model: str, prompt: str) -> str:
        url = ollama_url.rstrip("/") + "/api/chat"
        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an academic RAG assistant. Answer in Korean. "
            "Use only bibliographic facts and abstracts explicitly present in the JSON sources provided by the user. "
            "Cite claims with [C1], [C2] source IDs. "
            "Do not invent authors, years, titles, venues, page ranges, or DOI values. "
            "Do not infer first publication, origin, impact, or detailed theory content unless an abstract explicitly states it. "
            "Prefer an annotated bibliography format over broad narrative claims. "
            "Do not write a References section; the application will append verified references."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        message = data.get("message") or {}
        return str(message.get("content") or data.get("response") or "")

    def _build_prompt(self, question: str, works: list[AcademicWork]) -> str:
        source_json = {
            "query": question,
            "source": "Semantic Scholar/arXiv/Crossref/PubMed/OpenAlex",
            "results": [work.to_dict() for work in works],
        }
        return (
            "사용자 질문:\n"
            + question
            + "\n\n검증된 검색 결과 JSON:\n"
            + json.dumps(source_json, ensure_ascii=False, indent=2)
            + "\n\n규칙:\n"
            "- 위 JSON에 없는 논문/저자/연도/DOI/학술지명은 절대 쓰지 마십시오.\n"
            "- abstract가 비어 있으면 제목/저자/연도/출판정보 이상의 내용을 추론하지 마십시오.\n"
            "- '처음 소개', '입증했다', '대표 이론이다' 같은 평가는 검색 결과 JSON에 근거 문장이 있을 때만 쓰십시오.\n"
            "- 각 문장 또는 항목 끝에 근거 ID를 [C1]처럼 표시하십시오.\n"
            "- 근거가 부족하면 '검증된 검색 결과만으로는 답할 수 없습니다'라고 쓰십시오.\n"
            "- 참고문헌 목록은 만들지 마십시오.\n"
        )

    def format_search_results(self, query: str, works: list[AcademicWork]) -> str:
        lines = [
            "학술검색 결과",
            f"검색어: {query}",
            f"확인 결과: {len(works)}건",
            "",
        ]
        for index, work in enumerate(works, start=1):
            lines.append(f"{index}. {work.title}")
            lines.append(f"ID: [{work.id}]")
            lines.append(f"저자: {work.authors or '저자 정보 없음'}")
            lines.append(f"APA: {work.citation}")
            meta = [work.year, work.venue, f"DOI: {work.doi}" if work.doi else "", work.source]
            lines.append("서지: " + " · ".join(part for part in meta if part))
            if work.url:
                lines.append(f"링크: {work.url}")
            lines.append("")
            lines.append("초록 요약")
            lines.append(self._abstract_summary(work.abstract) if work.abstract else "검색 결과에 초록이 없습니다. 세부 이론 내용은 추론하지 마십시오.")
            lines.append("")
            lines.append("초록 원문")
            lines.append(work.abstract or "초록 없음")
            lines.append("")
        lines.append("복사 안내: 위 결과만 근거로 사용하고, 여기에 없는 참고문헌·저자·연도·DOI는 생성하지 마십시오.")
        return "\n".join(lines).strip()

    def build_literature_review_prompt(self, query: str, works: list[AcademicWork]) -> str:
        return (
            "아래 학술검색 결과의 APA 참고문헌과 초록만 근거로 사용해서 선행연구를 정리하십시오.\n"
            "검색 결과에 없는 저자, 연도, 제목, DOI, 학술지명, 페이지는 절대 생성하지 마십시오.\n"
            "초록이 없는 문헌은 서지정보만 언급하고 연구결과를 추론하지 마십시오.\n\n"
            + self.format_search_results(query, works)
            + "\n\n"
            "작성 형식:\n"
            f"# {query} 관련 초록 기반 선행연구 결과 정리\n\n"
            "## 1. 주어진 자료에서 추출 가능한 내용의 범위\n"
            "- 분석 대상 문헌 수, 연도 범위, 자료의 한계를 먼저 쓰십시오.\n"
            "- 직접 관련 연구와 간접 관련 연구를 구분하십시오.\n\n"
            "## 2. 초록에서 추출한 핵심 주장과 결과\n"
            "### 2.1. 핵심 주제 1\n"
            "- 초록에 실제로 적힌 결과만 정리하고 문장 끝에 [C1]처럼 근거 ID를 붙이십시오.\n"
            "### 2.2. 핵심 주제 2\n"
            "- 같은 방식으로 정리하십시오.\n"
            "### 2.3. 핵심 주제 3\n"
            "- 같은 방식으로 정리하십시오.\n\n"
            "## 3. 같은 결과를 지지하는 정보\n"
            "- 여러 초록에서 같은 방향으로 확인되는 내용을 묶으십시오.\n\n"
            "## 4. 반대되거나 제한적인 정보\n"
            "- 불일치, 비직접 관련성, 방법론 한계, 대상 차이를 쓰십시오.\n\n"
            "## 5. 연구주제에 대한 종합 해석\n"
            "- 검색 결과의 초록 범위 안에서만 해석하십시오.\n\n"
            "## 6. 최종 종합문\n"
            "- 논문에 넣을 수 있는 문단형 종합문으로 작성하십시오.\n\n"
            "## 7. APA 참고문헌\n"
            "- 위 학술검색 결과의 APA 항목을 그대로 재사용하십시오.\n"
        )

    def _append_verified_references(self, answer: str, works: list[AcademicWork]) -> str:
        lines = [answer.rstrip(), "", "## 검증된 참고문헌"]
        for work in works:
            lines.append(f"- [{work.id}] {work.citation}")
            if work.doi:
                lines.append(f"  DOI: {work.doi}")
            elif work.url:
                lines.append(f"  URL: {work.url}")
        return "\n".join(lines).strip()

    def _validation_issues(self, answer: str, works: list[AcademicWork]) -> list[str]:
        allowed = {work.id.upper() for work in works}
        used = {match.upper() for match in SOURCE_ID_RE.findall(answer)}
        unknown = sorted(used - allowed)
        issues = []
        if unknown:
            issues.append("검색 결과에 없는 출처 ID: " + ", ".join(unknown))

        allowed_years = {work.year for work in works if work.year}
        used_years = set(re.findall(r"\b(?:19|20)\d{2}\b", answer))
        unknown_years = sorted(year for year in used_years - allowed_years if year)
        if unknown_years:
            issues.append("검색 결과에 없는 연도: " + ", ".join(unknown_years))

        allowed_dois = {work.doi.lower() for work in works if work.doi}
        used_dois = {self._clean_doi(match) for match in DOI_RE.findall(answer)}
        unknown_dois = sorted(doi for doi in used_dois - allowed_dois if doi)
        if unknown_dois:
            issues.append("검색 결과에 없는 DOI: " + ", ".join(unknown_dois))

        return issues

    def _build_deterministic_summary(self, question: str, works: list[AcademicWork]) -> str:
        lines = [
            "검증된 외부 학술 DB 검색 결과만 기준으로 정리합니다.",
            f"질문: {question}",
            "",
            "## 검색 결과 기반 요약",
        ]
        for work in works:
            lines.append(f"- [{work.id}] {work.title}")
            lines.append(f"  - 저자: {work.authors or '검색 결과에 저자 정보 없음'}")
            lines.append(f"  - 연도/출처: {work.year or '연도 정보 없음'} / {work.venue or work.source}")
            if work.doi:
                lines.append(f"  - DOI: {work.doi}")
            if work.pages:
                lines.append(f"  - 페이지: {work.pages}")
            if work.abstract:
                lines.append(f"  - 초록 근거: {work.abstract[:350]}")
            else:
                lines.append("  - 초록 근거: 검색 결과에 초록이 없어 이 문헌의 세부 이론 내용은 요약하지 않습니다.")
        return "\n".join(lines)

    def _abstract_summary(self, abstract: str) -> str:
        cleaned = self._clean_space(abstract)
        if len(cleaned) <= 420:
            return cleaned
        sentences = re.split(r"(?<=[.!?。다])\s+", cleaned)
        selected = []
        for sentence in sentences:
            if sentence:
                selected.append(sentence)
            if len(" ".join(selected)) >= 360:
                break
        return " ".join(selected)[:520].strip()

    def _strip_reference_section(self, text: str) -> str:
        match = REFERENCE_HEADING_RE.search(text)
        if not match:
            return text
        return text[: match.start()].rstrip()

    def _dedupe(self, works: list[AcademicWork], query: str) -> list[AcademicWork]:
        seen: set[str] = set()
        deduped: list[AcademicWork] = []
        for work in works:
            key = work.doi or self._normalize_title(work.title)
            if not key or key in seen:
                continue
            seen.add(key)
            work.citation = self._format_apa(work)
            deduped.append(work)
        deduped.sort(key=lambda work: self._rank_score(query, work), reverse=True)
        for index, work in enumerate(deduped, start=1):
            work.id = f"C{index}"
            work.citation = self._format_apa(work)
        return deduped

    def _rank_score(self, query: str, work: AcademicWork) -> float:
        query_norm = self._normalize_title(query)
        title_norm = self._normalize_title(work.title)
        if not query_norm or not title_norm:
            return 0.0

        query_tokens = self._rank_tokens(query_norm)
        title_tokens = self._rank_tokens(title_norm)
        overlap = len(query_tokens & title_tokens) / max(len(query_tokens), 1)
        score = overlap

        if title_norm in query_norm or query_norm in title_norm:
            score += 2.0
        if work.authors and any(token in self._normalize_title(work.authors) for token in query_tokens):
            score += 0.2
        if work.doi:
            score += 0.1
        if work.abstract:
            score += 0.05
        return score

    def _clean_search_query(self, query: str) -> str:
        text = str(query or "")
        remove_patterns = [
            r"APA\s*참고문헌",
            r"참고문헌",
            r"인용정보",
            r"검증된",
            r"정리해줘",
            r"정리",
            r"알려줘",
            r"찾아줘",
            r"논문",
            r"연구",
            r"관련",
        ]
        for pattern in remove_patterns:
            text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
        return self._clean_space(text) or str(query or "").strip()

    def _rank_tokens(self, value: str) -> set[str]:
        stopwords = {
            "the",
            "and",
            "for",
            "with",
            "from",
            "into",
            "about",
            "대표",
            "논문",
            "연구",
            "참고문헌",
            "검증된",
            "정리",
        }
        return {token for token in value.split() if len(token) > 2 and token not in stopwords}

    def _format_apa(self, work: AcademicWork) -> str:
        authors = work.authors or "Unknown author"
        year = work.year or "n.d."
        title = work.title.rstrip(".")
        venue = work.venue.strip()
        vol_issue = ""
        if work.volume and work.issue:
            vol_issue = f", {work.volume}({work.issue})"
        elif work.volume:
            vol_issue = f", {work.volume}"
        pages = f", {work.pages}" if work.pages else ""
        doi = f" https://doi.org/{work.doi}" if work.doi else ""
        if venue:
            return f"{authors} ({year}). {title}. {venue}{vol_issue}{pages}.{doi}".strip()
        return f"{authors} ({year}). {title}.{doi}".strip()

    def _get_json(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "OpenWebUI-Launcher-Academic-RAG/1.0"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))

    def _format_crossref_authors(self, authors: list[dict[str, Any]]) -> str:
        names = []
        for author in authors[:6]:
            family = author.get("family") or ""
            given = author.get("given") or ""
            name = " ".join(part for part in [given, family] if part).strip()
            if name:
                names.append(name)
        return ", ".join(names)

    def _format_openalex_authors(self, authorships: list[dict[str, Any]]) -> str:
        names = []
        for authorship in authorships[:6]:
            author = authorship.get("author") or {}
            if author.get("display_name"):
                names.append(author["display_name"])
        return ", ".join(names)

    def _format_simple_authors(self, authors: list[dict[str, Any]]) -> str:
        return ", ".join(str(author.get("name") or "") for author in authors[:6] if author.get("name"))

    def _crossref_year(self, issued: Any) -> str:
        try:
            parts = issued.get("date-parts") or []
            return str(parts[0][0]) if parts and parts[0] else ""
        except Exception:
            return ""

    def _pubmed_year(self, pubdate: str) -> str:
        match = re.search(r"\b(19|20)\d{2}\b", pubdate)
        return match.group(0) if match else ""

    def _openalex_pages(self, biblio: dict[str, Any]) -> str:
        first = str(biblio.get("first_page") or "")
        last = str(biblio.get("last_page") or "")
        if first and last and first != last:
            return f"{first}-{last}"
        return first or last

    def _openalex_abstract(self, inverted_index: dict[str, list[int]]) -> str:
        if not inverted_index:
            return ""
        positioned: list[tuple[int, str]] = []
        for word, positions in inverted_index.items():
            for position in positions:
                positioned.append((position, word))
        return " ".join(word for _, word in sorted(positioned))[:1200]

    def _first(self, value: Any) -> str:
        if isinstance(value, list):
            return str(value[0]).strip() if value else ""
        return str(value or "").strip()

    def _clean_doi(self, value: Any) -> str:
        text = str(value or "").strip()
        text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text, flags=re.IGNORECASE)
        match = DOI_RE.search(text)
        return match.group(0).lower().rstrip(".,;)") if match else text.lower().rstrip(".,;)")

    def _clean_html(self, value: str) -> str:
        return self._clean_space(re.sub(r"<[^>]+>", " ", value))

    def _clean_space(self, value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def _normalize_title(self, value: str) -> str:
        return re.sub(r"[^a-z0-9가-힣]+", " ", str(value).lower()).strip()

    def _xml_text(self, element: ET.Element | None) -> str:
        return element.text if element is not None and element.text else ""
