"""Indian Kanoon judgment scraper.

Fetches HTML from indiankanoon.org/doc/{id}/ pages and extracts the
judgment body text, stripping site chrome. Used by scripts/scrape_seed.py
to build the local case corpus consumed by the embedding pipeline.
"""

from __future__ import annotations

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential


def extract_case_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("div", class_="judgments") or soup
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    return "\n\n".join(t for t in paragraphs if t)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
def fetch_case(url: str, client: httpx.Client) -> str:
    resp = client.get(url, timeout=30)
    resp.raise_for_status()
    return extract_case_text(resp.text)
