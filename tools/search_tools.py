import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

import httpx
from langchain_core.tools import StructuredTool

from app.config.settings import Settings
from app.schemas.roadmap import LearningResource


class SearchTools:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build(self) -> list[StructuredTool]:
        tools = [
            StructuredTool.from_function(
                coroutine=self.search_arxiv,
                name="arxiv_search",
                description="Search arXiv for papers related to a roadmap node.",
            ),
            StructuredTool.from_function(
                coroutine=self.search_documentation,
                name="documentation_search",
                description="Search public documentation and articles for a roadmap node.",
            ),
        ]
        if self.settings.youtube_api_key:
            tools.append(
                StructuredTool.from_function(
                    coroutine=self.search_youtube,
                    name="youtube_search",
                    description="Search YouTube Data API for learning videos.",
                )
            )
        if self.settings.tavily_api_key:
            tools.append(
                StructuredTool.from_function(
                    coroutine=self.search_tavily,
                    name="tavily_search",
                    description="Search Tavily for high quality web learning resources.",
                )
            )
        return tools

    async def search_arxiv(self, query: str, max_results: int = 2) -> list[dict]:
        url = (
            "https://export.arxiv.org/api/query"
            f"?search_query=all:{quote_plus(query)}&start=0&max_results={max_results}"
        )
        async with httpx.AsyncClient(timeout=self.settings.external_tool_timeout_seconds) as client:
            response = await client.get(url)
            response.raise_for_status()
        root = ET.fromstring(response.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        resources = []
        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            link = entry.find("atom:link[@title='pdf']", ns) or entry.find("atom:link", ns)
            resources.append(
                LearningResource(
                    title=" ".join(title.split()),
                    url=link.attrib.get("href", "") if link is not None else "",
                    source="arXiv",
                    summary=(entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()[:240],
                    resource_type="paper",
                    confidence=0.72,
                ).model_dump()
            )
        return resources

    async def search_documentation(self, query: str, max_results: int = 2) -> list[dict]:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": f"{query} official documentation tutorial",
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }
        async with httpx.AsyncClient(timeout=self.settings.external_tool_timeout_seconds) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
        data = response.json()
        candidates = data.get("RelatedTopics", [])[:max_results]
        resources = []
        for item in candidates:
            if "Topics" in item:
                item = item["Topics"][0] if item["Topics"] else {}
            if not item.get("FirstURL"):
                continue
            resources.append(
                LearningResource(
                    title=item.get("Text", query)[:90],
                    url=item["FirstURL"],
                    source="DuckDuckGo",
                    summary=item.get("Text", "")[:240],
                    resource_type="documentation",
                    confidence=0.68,
                ).model_dump()
            )
        if not resources and data.get("AbstractURL"):
            resources.append(
                LearningResource(
                    title=data.get("Heading") or query,
                    url=data["AbstractURL"],
                    source="DuckDuckGo",
                    summary=data.get("AbstractText", "")[:240],
                    resource_type="documentation",
                    confidence=0.62,
                ).model_dump()
            )
        return resources

    async def search_youtube(self, query: str, max_results: int = 2) -> list[dict]:
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": f"{query} tutorial",
            "type": "video",
            "maxResults": max_results,
            "key": self.settings.youtube_api_key,
        }
        async with httpx.AsyncClient(timeout=self.settings.external_tool_timeout_seconds) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
        resources = []
        for item in response.json().get("items", []):
            video_id = item.get("id", {}).get("videoId")
            snippet = item.get("snippet", {})
            if not video_id:
                continue
            resources.append(
                LearningResource(
                    title=snippet.get("title", query),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    source=snippet.get("channelTitle", "YouTube"),
                    summary=snippet.get("description", "")[:240],
                    resource_type="video",
                    confidence=0.7,
                ).model_dump()
            )
        return resources

    async def search_tavily(self, query: str, max_results: int = 2) -> list[dict]:
        async with httpx.AsyncClient(timeout=self.settings.external_tool_timeout_seconds) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.settings.tavily_api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                },
            )
            response.raise_for_status()
        resources = []
        for item in response.json().get("results", [])[:max_results]:
            resources.append(
                LearningResource(
                    title=item.get("title", query),
                    url=item.get("url", ""),
                    source="Tavily",
                    summary=item.get("content", "")[:240],
                    resource_type="article",
                    confidence=float(item.get("score", 0.65)),
                ).model_dump()
            )
        return resources
