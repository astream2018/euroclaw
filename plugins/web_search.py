import logging
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from opentelemetry import trace

logger = logging.getLogger("euroclaw.plugins.web")
tracer = trace.get_tracer(__name__)

class WebIntelligencePlugin:
    def __init__(self):
        self.headers = {
            "User-Agent": "EuroClaw Sovereign Agent / 1.0"
        }

    def search_internet(self, query: str, max_results: int = 3) -> str:
        """Searches DuckDuckGo and returns URLs and snippets."""
        with tracer.start_as_current_span("web_search") as span:
            span.set_attribute("euroclaw.search.query", query)
            try:
                results = DDGS().text(query, max_results=max_results)
                formatted_results = "\n".join([f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n" for r in results])
                return formatted_results if formatted_results else "No results found."
            except Exception as e:
                span.set_status(trace.StatusCode.ERROR, description=str(e))
                return f"Search failed: {e}"

    def scrape_website(self, url: str) -> str:
        """Scrapes the readable text from a URL, ignoring scripts and styles."""
        with tracer.start_as_current_span("web_scrape") as span:
            span.set_attribute("euroclaw.scrape.url", url)
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Strip out JavaScript, CSS, and structural tags
                for script in soup(["script", "style", "header", "footer", "nav"]):
                    script.extract()
                    
                text = soup.get_text(separator=' ', strip=True)
                return text[:5000] # Limit tokens returned to the LLM to prevent context overflow
                
            except requests.exceptions.RequestException as e:
                span.set_status(trace.StatusCode.ERROR, description=str(e))
                return f"Failed to scrape {url}. Reason: {e}"