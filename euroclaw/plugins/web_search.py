import logging

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

from euroclaw.tracing import get_tracer

logger = logging.getLogger("euroclaw.plugins.web")
tracer = get_tracer(__name__)


class WebIntelligencePlugin:
    def __init__(self):
        self.headers = {"User-Agent": "EuroClaw Sovereign Agent / 1.0"}

    def search_internet(self, query: str, max_results: int = 3) -> str:
        with tracer.start_as_current_span("web_search") as span:
            span.set_attribute("euroclaw.search.query", query)
            try:
                results = DDGS().text(query, max_results=max_results)
                formatted = "\n".join(
                    f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n"
                    for r in results
                )
                return formatted or "No results found."
            except Exception as exc:  # noqa: BLE001
                from opentelemetry import trace

                span.set_status(trace.StatusCode.ERROR, description=str(exc))
                return f"Search failed: {exc}"

    def scrape_website(self, url: str) -> str:
        with tracer.start_as_current_span("web_scrape") as span:
            span.set_attribute("euroclaw.scrape.url", url)
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                for tag in soup(["script", "style", "header", "footer", "nav"]):
                    tag.extract()
                return soup.get_text(separator=" ", strip=True)[:5000]
            except requests.exceptions.RequestException as exc:
                from opentelemetry import trace

                span.set_status(trace.StatusCode.ERROR, description=str(exc))
                return f"Failed to scrape {url}. Reason: {exc}"
