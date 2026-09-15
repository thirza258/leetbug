"""python -m app.ingest_docs [--refresh]: ingest reviewed summaries or live official docs."""
import argparse
import hashlib
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from app.documents import DOCUMENTS
from app.rag import ingest


def fetch_document(client, url, allowed):
    for _ in range(6):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in allowed or parsed.username or parsed.port not in (None, 443):
            raise ValueError("Only HTTPS pages on reviewed official documentation hosts can be ingested")
        response = client.get(url)
        if response.is_redirect:
            location = response.headers.get("location")
            if not location:
                raise ValueError("Documentation redirect is missing its destination")
            url = urljoin(str(response.url), location)
            continue
        response.raise_for_status()
        return response
    raise ValueError("Official documentation redirected too many times")


def refresh():
    chunks = []
    allowed = {urlsplit(doc["url"]).hostname for doc in DOCUMENTS}
    with httpx.Client(timeout=30, follow_redirects=False, headers={"User-Agent": "LeetBug-docs/1.0"}) as client:
        for doc in DOCUMENTS:
            url = doc["url"].split("#")[0]
            response = fetch_document(client, url, allowed)
            soup = BeautifulSoup(response.text, "html.parser")
            for element in soup(["script", "style", "nav", "header", "footer"]):
                element.decompose()
            main = soup.find("main") or soup.find("article") or soup.body or soup
            text = " ".join(main.stripped_strings)
            for offset in range(0, min(len(text), 80000), 1000):
                chunk = text[offset:offset + 1200]
                if len(chunk) < 80:
                    continue
                chunks.append({**doc, "id": doc["id"] + "-" + hashlib.sha256(chunk.encode()).hexdigest()[:12],
                               "text": chunk})
    # Fetch the entire batch successfully before changing the collection.
    return ingest(chunks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    print(f"Indexed {refresh() if args.refresh else ingest()} documentation chunks.")
