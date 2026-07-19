"""
title: Academic Verified Search
author: Joonghee Park PhD
version: 1.2.0
description: Search verified academic metadata from Crossref, OpenAlex, Semantic Scholar, PubMed, and arXiv, then return citation-safe Korean output for Open WebUI chat tools.
required_open_webui_version: 0.9.0
"""

from __future__ import annotations

import json
import re
import time
import html
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from typing import Any

from pydantic import BaseModel, Field


DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)


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
    abstract_source: str = ""
    url: str = ""
    citation: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class Tools:
    class Valves(BaseModel):
        max_results: int = Field(default=8, ge=1, le=12, description="Default number of verified academic records.")
        timeout_seconds: float = Field(default=7.0, ge=1.0, le=20.0, description="HTTP timeout for metadata APIs.")
        enrich_abstracts: bool = Field(default=True, description="Fetch DOI/OpenAlex/PubMed landing pages to recover missing abstracts.")
        abstract_fetch_limit: int = Field(default=8, ge=1, le=12, description="Maximum records to enrich by visiting landing pages.")
        include_json: bool = Field(default=True, description="Include retrieved source JSON in the tool output.")

    def __init__(self):
        self.valves = self.Valves()

    async def academic_verified_search(self, query: str, max_results: int = 8, __event_emitter__=None) -> str:
        """
        Search verified academic metadata and return citation-safe Korean output.
        Use this tool whenever the user asks for papers, studies, citations, references, authors, DOI, or academic evidence.
        The final answer must use only the returned records and must not invent references.

        :param query: Academic search query, paper title, DOI, author, or topic.
        :param max_results: Number of verified records to return, from 1 to 12.
        """
        query = (query or "").strip()
        if not query:
            return "질문 또는 검색어가 비어 있습니다."

        max_results = max(1, min(int(max_results or self.valves.max_results), 12))
        await self._emit(__event_emitter__, "외부 학술 DB에서 검증 메타데이터를 검색합니다.", False)
        works = self._search(query, max_results)
        await self._emit(__event_emitter__, f"검증 후보 {len(works)}개를 찾았습니다.", True)

        if not works:
            return (
                "검증된 학술 메타데이터를 찾지 못했습니다.\n\n"
                "논문명, 저자명, DOI, 영어 핵심어를 함께 넣어 다시 검색하십시오.\n"
                "주의: 검색 결과가 없을 때는 참고문헌을 생성하지 마십시오."
            )

        return self._build_tool_output(query, works)

    def _search(self, query: str, max_results: int) -> list[AcademicWork]:
        source_limit = min(max(max_results * 3, 10), 20)
        raw: list[AcademicWork] = []
        for search_query in self._query_variants(query):
            raw.extend(self._search_crossref(search_query, source_limit))
            raw.extend(self._search_openalex(search_query, source_limit))
            raw.extend(self._search_semantic_scholar(search_query, source_limit))
            raw.extend(self._search_pubmed(search_query, source_limit))
            raw.extend(self._search_arxiv(search_query, min(source_limit, 8)))
        works = self._dedupe(raw, query)[:max_results]
        if self.valves.enrich_abstracts:
            self._enrich_missing_abstracts(works)
        for work in works:
            work.citation = self._format_apa(work)
        return works

    def _query_variants(self, query: str) -> list[str]:
        cleaned = self._clean_space(query)
        variants = [cleaned]
        normalized = re.sub(r"[,+/|]+", " ", cleaned)
        normalized = self._clean_space(normalized)
        if normalized and normalized not in variants:
            variants.append(normalized)

        replacements = {
            "리더구성원교환관계": "리더 구성원 교환관계",
            "리더-구성원교환관계": "리더 구성원 교환관계",
            "리더-구성원 교환관계": "리더 구성원 교환관계",
            "LMX": "leader member exchange",
            "lmx": "leader member exchange",
            "경력몰입": "career commitment",
            "조직몰입": "organizational commitment",
            "부사관": "non commissioned officer",
            "육군": "army",
        }
        expanded = normalized
        for source, target in replacements.items():
            expanded = expanded.replace(source, f"{source} {target}")
        expanded = self._clean_space(expanded)
        if expanded and expanded not in variants:
            variants.append(expanded)

        token_variants = []
        for token in normalized.split():
            if len(token) >= 3:
                token_variants.append(token)
            if token in replacements:
                token_variants.append(replacements[token])
        for token_query in token_variants[:6]:
            if token_query and token_query not in variants:
                variants.append(token_query)
        return variants[:8]

    def _build_tool_output(self, query: str, works: list[AcademicWork]) -> str:
        lines = [
            "아래 내용은 Open WebUI Tool이 외부 학술 DB에서 검색한 검증 메타데이터입니다.",
            "모델은 이 결과 밖의 저자, 연도, 제목, DOI, 학술지명, 페이지를 생성하면 안 됩니다.",
            f"검색어: {query}",
            "",
            "## 검색 결과 기반 요약",
        ]
        for work in works:
            lines.append(f"- [{work.id}] {work.title}")
            lines.append(f"  - 저자: {work.authors or '검색 결과에 저자 정보 없음'}")
            lines.append(f"  - 연도/출처: {work.year or '연도 정보 없음'} / {work.venue or work.source}")
            if work.volume or work.issue or work.pages:
                details = ", ".join(part for part in [work.volume, f"({work.issue})" if work.issue else "", work.pages] if part)
                lines.append(f"  - 권호/쪽: {details}")
            if work.doi:
                lines.append(f"  - DOI: {work.doi}")
            elif work.url:
                lines.append(f"  - URL: {work.url}")
            if work.abstract:
                source = f" ({work.abstract_source})" if work.abstract_source else ""
                lines.append(f"  - 초록 근거{source}: {work.abstract[:700]}")
            else:
                lines.append("  - 초록 근거: 검색 결과에 초록이 없어 세부 이론 내용은 요약하지 마십시오.")

        lines.append("")
        lines.append("## 검증된 참고문헌")
        for work in works:
            lines.append(f"- [{work.id}] {work.citation}")
            if work.doi:
                lines.append(f"  DOI: {work.doi}")
            elif work.url:
                lines.append(f"  URL: {work.url}")

        if self.valves.include_json:
            source_json = {
                "query": query,
                "source": "Crossref/OpenAlex/Semantic Scholar/PubMed/arXiv",
                "results": [work.to_dict() for work in works],
            }
            lines.append("")
            lines.append("## 검색 결과 JSON")
            lines.append("```json")
            lines.append(json.dumps(source_json, ensure_ascii=False, indent=2))
            lines.append("```")

        lines.append("")
        lines.append("응답 규칙: 최종 답변은 위 [C1] 형식의 항목만 인용하고, 새 참고문헌을 추가하지 마십시오.")
        return "\n".join(lines)

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
                abstract_source="Crossref" if item.get("abstract") else "",
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
                abstract_source="OpenAlex" if item.get("abstract_inverted_index") else "",
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
                abstract_source="Semantic Scholar" if item.get("abstract") else "",
                url=str(item.get("url") or ""),
            )
            work.citation = self._format_apa(work)
            works.append(work)
        return works

    def _search_pubmed(self, query: str, max_results: int) -> list[AcademicWork]:
        params = {"db": "pubmed", "term": query[:500], "retmode": "json", "retmax": str(max_results)}
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(params)
        try:
            data = self._get_json(search_url)
            ids = ((data.get("esearchresult") or {}).get("idlist") or [])[:max_results]
        except Exception:
            return []
        if not ids:
            return []
        abstracts = self._fetch_pubmed_abstracts(ids)
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
            title = self._clean_space(str(item.get("title") or "")).rstrip(".")
            if not title:
                continue
            doi = ""
            for article_id in item.get("articleids") or []:
                if article_id.get("idtype") == "doi":
                    doi = article_id.get("value") or ""
                    break
            authors = ", ".join((author.get("name") or "") for author in (item.get("authors") or [])[:6] if author.get("name"))
            work = AcademicWork(
                id="",
                source="PubMed",
                title=title,
                authors=authors,
                year=self._pubmed_year(str(item.get("pubdate") or "")),
                doi=self._clean_doi(doi),
                venue=str(item.get("fulljournalname") or item.get("source") or ""),
                volume=str(item.get("volume") or ""),
                issue=str(item.get("issue") or ""),
                pages=str(item.get("pages") or ""),
                abstract=abstracts.get(pmid, ""),
                abstract_source="PubMed" if abstracts.get(pmid) else "",
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
            request = urllib.request.Request(url, headers={"User-Agent": "OpenWebUI-Academic-Verified-Search/1.2"})
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
            work = AcademicWork(
                id="",
                source="arXiv",
                title=title,
                authors=", ".join(authors),
                year=published[:4] if published[:4].isdigit() else "",
                doi=self._clean_doi(self._xml_text(entry.find("arxiv:doi", ns))),
                venue="arXiv",
                abstract=self._clean_space(self._xml_text(entry.find("atom:summary", ns))),
                abstract_source="arXiv",
                url=self._xml_text(entry.find("atom:id", ns)),
            )
            work.citation = self._format_apa(work)
            works.append(work)
        return works

    def _dedupe(self, works: list[AcademicWork], query: str) -> list[AcademicWork]:
        seen: set[str] = set()
        deduped: list[AcademicWork] = []
        for work in works:
            key = work.doi or self._normalize_title(work.title)
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(work)
        deduped.sort(key=lambda work: self._rank_score(query, work), reverse=True)
        for index, work in enumerate(deduped, start=1):
            work.id = f"C{index}"
            work.citation = self._format_apa(work)
        return deduped

    def _enrich_missing_abstracts(self, works: list[AcademicWork]) -> None:
        checked = 0
        for work in works:
            if work.abstract and len(work.abstract) >= 80:
                continue
            if checked >= int(self.valves.abstract_fetch_limit):
                return
            checked += 1

            enriched = ""
            source = ""
            if work.doi:
                enriched, source = self._semantic_scholar_by_doi(work)
            if not enriched and work.doi:
                enriched, source = self._abstract_from_landing_page(f"https://doi.org/{work.doi}", work)
            if not enriched and work.url:
                enriched, source = self._abstract_from_landing_page(work.url, work)

            if enriched:
                work.abstract = enriched
                work.abstract_source = source

    def _semantic_scholar_by_doi(self, work: AcademicWork) -> tuple[str, str]:
        url = (
            "https://api.semanticscholar.org/graph/v1/paper/DOI:"
            + urllib.parse.quote(work.doi)
            + "?fields=abstract,title,year,venue"
        )
        try:
            data = self._get_json(url)
        except Exception:
            return "", ""
        returned_title = str(data.get("title") or "")
        if returned_title and not self._titles_match_for_abstract(work.title, returned_title):
            return "", ""
        abstract = self._clean_space(str(data.get("abstract") or ""))
        if not self._abstract_matches_korean_title_start(work.title, abstract):
            return "", ""
        if not self._abstract_matches_title(work.title, abstract):
            return "", ""
        return (abstract, "Semantic Scholar DOI") if self._looks_like_abstract(abstract) else ("", "")

    def _fetch_pubmed_abstracts(self, ids: list[str]) -> dict[str, str]:
        if not ids:
            return {}
        params = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml"}
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(params)
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "OpenWebUI-Academic-Verified-Search/1.2"})
            with urllib.request.urlopen(request, timeout=float(self.valves.timeout_seconds)) as response:
                text = response.read().decode("utf-8", errors="replace")
            root = ET.fromstring(text)
        except Exception:
            return {}

        result: dict[str, str] = {}
        for article in root.findall(".//PubmedArticle"):
            pmid = self._xml_text(article.find(".//PMID"))
            parts = []
            for abstract_text in article.findall(".//Abstract/AbstractText"):
                label = abstract_text.attrib.get("Label") or abstract_text.attrib.get("NlmCategory") or ""
                text = self._clean_space("".join(abstract_text.itertext()))
                if text:
                    parts.append(f"{label}: {text}" if label else text)
            abstract = self._clean_space(" ".join(parts))
            if pmid and abstract:
                result[pmid] = abstract
        return result

    def _abstract_from_landing_page(self, url: str, work: AcademicWork) -> tuple[str, str]:
        if not url:
            return "", ""
        html_text, final_url = self._get_html(url)
        if not html_text:
            return "", ""

        candidates = []
        candidates.extend(self._extract_meta_values(html_text))
        candidates.extend(self._extract_jsonld_abstracts(html_text))
        candidates.extend(self._extract_visible_abstract_blocks(html_text))

        best = ""
        for candidate in candidates:
            cleaned = self._clean_candidate_abstract(candidate)
            if not self._looks_like_abstract(cleaned):
                continue
            if not self._abstract_matches_korean_title_start(work.title, cleaned):
                continue
            if not self._abstract_matches_title(work.title, cleaned):
                continue
            if len(cleaned) > len(best):
                best = cleaned
        if not best:
            return "", ""
        host = urllib.parse.urlparse(final_url or url).netloc or "landing page"
        return best[:2500], f"landing page: {host}"

    def _get_html(self, url: str) -> tuple[str, str]:
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "User-Agent": "Mozilla/5.0 OpenWebUI-Academic-Verified-Search/1.2",
                },
            )
            with urllib.request.urlopen(request, timeout=float(self.valves.timeout_seconds)) as response:
                content_type = response.headers.get("Content-Type", "")
                if "html" not in content_type and "xml" not in content_type and "text" not in content_type:
                    return "", response.geturl()
                raw = response.read(900000)
                charset = response.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace"), response.geturl()
        except Exception:
            return "", ""

    def _extract_meta_values(self, html_text: str) -> list[str]:
        values = []
        meta_re = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
        attr_re = re.compile(r"""([:\w-]+)\s*=\s*(['"])(.*?)\2""", re.IGNORECASE | re.DOTALL)
        wanted = {
            "citation_abstract",
            "dc.description",
            "dcterms.description",
            "description",
            "og:description",
            "twitter:description",
            "article:description",
        }
        for tag in meta_re.findall(html_text):
            attrs = {name.lower(): html.unescape(value) for name, _, value in attr_re.findall(tag)}
            key = (attrs.get("name") or attrs.get("property") or attrs.get("itemprop") or "").lower()
            if key in wanted and attrs.get("content"):
                values.append(attrs["content"])
        return values

    def _extract_jsonld_abstracts(self, html_text: str) -> list[str]:
        values = []
        script_re = re.compile(
            r"<script\b[^>]*type\s*=\s*['\"]application/ld\+json['\"][^>]*>(.*?)</script>",
            re.IGNORECASE | re.DOTALL,
        )
        for raw in script_re.findall(html_text):
            text = html.unescape(raw).strip()
            try:
                data = json.loads(text)
            except Exception:
                continue
            values.extend(self._jsonld_abstract_values(data))
        return values

    def _jsonld_abstract_values(self, data: Any) -> list[str]:
        values = []
        if isinstance(data, list):
            for item in data:
                values.extend(self._jsonld_abstract_values(item))
        elif isinstance(data, dict):
            for key in ("abstract", "description", "summary"):
                value = data.get(key)
                if isinstance(value, str):
                    values.append(value)
                elif isinstance(value, dict) and isinstance(value.get("@value"), str):
                    values.append(value["@value"])
            graph = data.get("@graph")
            if graph:
                values.extend(self._jsonld_abstract_values(graph))
        return values

    def _extract_visible_abstract_blocks(self, html_text: str) -> list[str]:
        values = []
        patterns = [
            r"<(?:section|div|article)[^>]+(?:id|class)\s*=\s*['\"][^'\"]*(?:abstract|초록|summary)[^'\"]*['\"][^>]*>(.*?)</(?:section|div|article)>",
            r"(?:Abstract|ABSTRACT|초록)\s*</[^>]+>\s*<[^>]+>(.{120,2500}?)</[^>]+>",
        ]
        for pattern in patterns:
            for match in re.findall(pattern, html_text, flags=re.IGNORECASE | re.DOTALL):
                values.append(match)
        return values

    def _clean_candidate_abstract(self, value: str) -> str:
        text = html.unescape(str(value or ""))
        text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = self._clean_space(text)
        text = re.sub(r"^(abstract|summary|초록|요약)\s*[:：]?\s*", "", text, flags=re.IGNORECASE)
        return text

    def _looks_like_abstract(self, value: str) -> bool:
        text = self._clean_space(value)
        if len(text) < 80:
            return False
        lowered = text.lower()
        bad_fragments = [
            "cookie",
            "javascript",
            "enable cookies",
            "access denied",
            "captcha",
            "page not found",
            "404",
            "all rights reserved",
            "이 페이지를",
        ]
        if any(fragment in lowered for fragment in bad_fragments):
            return False
        return True

    def _abstract_matches_title(self, title: str, abstract: str) -> bool:
        title_terms = [
            token
            for token in self._normalize_title(title).split()
            if token in self._rank_tokens(self._normalize_title(title))
        ]
        if not title_terms:
            return True
        abstract_norm = self._normalize_title(abstract)
        leading_terms = [self._korean_term_stem(term) for term in title_terms[:5] if len(term) >= 3]
        if not leading_terms:
            return True
        matches = sum(1 for term in leading_terms if term and term in abstract_norm)
        return matches >= 2 if len(leading_terms) >= 4 else matches >= 1

    def _abstract_matches_korean_title_start(self, title: str, abstract: str) -> bool:
        if not re.search(r"[가-힣]", title):
            return True
        title_terms = [
            self._korean_term_stem(token)
            for token in self._normalize_title(title).split()
            if re.search(r"[가-힣]", token) and len(token) >= 3
        ]
        first_terms = [term for term in title_terms[:3] if term]
        if not first_terms:
            return True
        abstract_norm = self._normalize_title(abstract)
        return any(term in abstract_norm for term in first_terms)

    def _korean_term_stem(self, term: str) -> str:
        text = str(term or "")
        for suffix in ("으로", "에서", "에게", "에는", "까지", "부터", "와", "과", "의", "을", "를", "은", "는", "이", "가"):
            if len(text) > len(suffix) + 2 and text.endswith(suffix):
                return text[: -len(suffix)]
        return text

    def _rank_score(self, query: str, work: AcademicWork) -> float:
        query_norm = self._normalize_title(query)
        title_norm = self._normalize_title(work.title)
        query_tokens = self._rank_tokens(query_norm)
        title_tokens = self._rank_tokens(title_norm)
        if not query_tokens:
            return 0.0
        score = len(query_tokens & title_tokens) / len(query_tokens)
        if title_norm and (title_norm in query_norm or query_norm in title_norm):
            score += 2.0
        if work.authors and any(token in self._normalize_title(work.authors) for token in query_tokens):
            score += 0.2
        if work.doi:
            score += 0.1
        if work.abstract:
            score += 0.05
        return score

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
            "자료",
            "찾아줘",
        }
        return {token for token in value.split() if len(token) > 2 and token not in stopwords}

    def _title_similarity(self, left: str, right: str) -> float:
        left_tokens = self._rank_tokens(self._normalize_title(left))
        right_tokens = self._rank_tokens(self._normalize_title(right))
        if not left_tokens or not right_tokens:
            return 0.0
        return len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)

    def _titles_match_for_abstract(self, left: str, right: str) -> bool:
        left_norm = self._normalize_title(left)
        right_norm = self._normalize_title(right)
        if not left_norm or not right_norm:
            return False
        if left_norm in right_norm or right_norm in left_norm:
            return True
        return self._title_similarity(left, right) >= 0.6

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
            headers={"Accept": "application/json", "User-Agent": "OpenWebUI-Academic-Verified-Search/1.2"},
        )
        with urllib.request.urlopen(request, timeout=float(self.valves.timeout_seconds)) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))

    async def _emit(self, emitter, description: str, done: bool) -> None:
        if not emitter:
            return
        try:
            await emitter({"type": "status", "data": {"description": description, "done": done, "hidden": False}})
        except Exception:
            return

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
