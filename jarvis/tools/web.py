"""Weather and research tools (Phases 1 and 5)."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

import httpx

from jarvis.config_loader import Settings
from jarvis.security.permissions import PermissionLevel
from jarvis.tools.registry import Tool, ToolRegistry

_UA = "JarvisPersonalAssistant/0.1 (research; +local)"


def register_web_tools(registry: ToolRegistry, settings: Settings) -> None:
    def get_weather(place: str = "") -> str:
        if place:
            geo = httpx.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": place, "count": 1},
                headers={"User-Agent": _UA},
                timeout=15.0,
            )
            geo.raise_for_status()
            results = geo.json().get("results") or []
            if not results:
                return json.dumps({"error": f"Could not geocode {place}"})
            lat, lon = results[0]["latitude"], results[0]["longitude"]
            label = f"{results[0].get('name')}, {results[0].get('country_code', '')}"
        else:
            lat, lon = settings.latitude, settings.longitude
            label = settings.location_name
        wx = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True},
            headers={"User-Agent": _UA},
            timeout=15.0,
        )
        wx.raise_for_status()
        current = wx.json().get("current_weather") or {}
        return json.dumps({"place": label, "latitude": lat, "longitude": lon, "current": current})

    def web_search(query: str, max_results: int = 5) -> str:
        results = _ddg_search(query, max_results=max(1, min(max_results, 8)))
        return json.dumps({"query": query, "results": results})

    def fetch_url(url: str) -> str:
        if not url.startswith(("http://", "https://")):
            raise ValueError("Only http(s) URLs are allowed.")
        response = httpx.get(
            url,
            headers={"User-Agent": _UA},
            timeout=20.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        ctype = response.headers.get("content-type", "")
        if "html" in ctype or url.endswith(".html"):
            text = _html_to_text(response.text)
        else:
            text = response.text
        return json.dumps({"url": str(response.url), "text": text[:12000]})

    def research_topic(question: str, context: str = "") -> str:
        query = question if not context else f"{question} {context}"
        hits = _ddg_search(query, max_results=5)
        extracts = []
        for hit in hits[:3]:
            href = hit.get("url") or ""
            if not href.startswith("http"):
                continue
            try:
                page = httpx.get(href, headers={"User-Agent": _UA}, timeout=15.0, follow_redirects=True)
                page.raise_for_status()
                extracts.append(
                    {
                        "title": hit.get("title"),
                        "url": href,
                        "excerpt": _html_to_text(page.text)[:2500],
                    }
                )
            except httpx.HTTPError:
                extracts.append({"title": hit.get("title"), "url": href, "excerpt": hit.get("snippet", "")})
        return json.dumps({"question": question, "sources": extracts})

    registry.register(
        Tool(
            "get_weather",
            "Get current weather. Defaults to the configured home location.",
            {
                "type": "object",
                "properties": {"place": {"type": "string", "description": "City name; empty = home."}},
                "additionalProperties": False,
            },
            PermissionLevel.READ,
            get_weather,
        )
    )
    registry.register(
        Tool(
            "web_search",
            "Search the web and return titles, URLs, and snippets.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            PermissionLevel.READ,
            web_search,
        )
    )
    registry.register(
        Tool(
            "fetch_url",
            "Fetch a URL and extract readable text for analysis.",
            {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
                "additionalProperties": False,
            },
            PermissionLevel.READ,
            fetch_url,
        )
    )
    registry.register(
        Tool(
            "research_topic",
            "Multi-step research: search, fetch top sources, return excerpts to compare and cite.",
            {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "context": {"type": "string", "description": "Optional project context e.g. ShipLink / React Native"},
                },
                "required": ["question"],
                "additionalProperties": False,
            },
            PermissionLevel.READ,
            research_topic,
        )
    )


def _ddg_search(query: str, *, max_results: int) -> list[dict[str, str]]:
    url = "https://html.duckduckgo.com/html/"
    response = httpx.post(
        url,
        data={"q": query},
        headers={"User-Agent": _UA, "Content-Type": "application/x-www-form-urlencoded"},
        timeout=20.0,
        follow_redirects=True,
    )
    response.raise_for_status()
    return _parse_ddg(response.text, max_results=max_results)


def _parse_ddg(html: str, *, max_results: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for match in re.finditer(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)',
        html,
        re.I | re.S,
    ):
        href, title, snippet = match.group(1), _strip_tags(match.group(2)), _strip_tags(match.group(3))
        href = _unwrap_ddg(href)
        results.append({"title": title.strip(), "url": href, "snippet": snippet.strip()})
        if len(results) >= max_results:
            break
    if results:
        return results
    for match in re.finditer(r'href="(https?://[^"]+)"[^>]*>([^<]{5,120})</a>', html):
        href, title = match.group(1), match.group(2)
        if "duckduckgo.com" in href:
            continue
        results.append({"title": title.strip(), "url": href, "snippet": ""})
        if len(results) >= max_results:
            break
    return results


def _unwrap_ddg(href: str) -> str:
    if "uddg=" in href:
        from urllib.parse import parse_qs, unquote, urlparse

        qs = parse_qs(urlparse(href).query)
        if "uddg" in qs:
            return unquote(qs["uddg"][0])
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return urljoin("https://duckduckgo.com", href)
    return href


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).replace("&amp;", "&").replace("&nbsp;", " ")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in {"script", "style", "noscript"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1
        if tag in {"p", "br", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = data.strip()
        if text:
            self.parts.append(text + " ")


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        return _strip_tags(html)
    text = re.sub(r"[ \t]+", " ", "".join(parser.parts))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
