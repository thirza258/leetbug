import httpx
import pytest

from app.ingest_docs import fetch_document


def test_document_refresh_follows_official_redirects():
    paths = []
    def respond(request):
        paths.append(request.url.path)
        if request.url.path == "/old":
            return httpx.Response(301, headers={"Location": "/new"})
        return httpx.Response(200, text="Official documentation")
    with httpx.Client(transport=httpx.MockTransport(respond), follow_redirects=False) as client:
        response = fetch_document(client, "https://docs.python.org/old", {"docs.python.org"})
    assert response.text == "Official documentation" and paths == ["/old", "/new"]


def test_document_refresh_rejects_unreviewed_redirect_before_fetching():
    hosts = []
    def respond(request):
        hosts.append(request.url.host)
        return httpx.Response(302, headers={"Location": "http://internal-service/private"})
    with httpx.Client(transport=httpx.MockTransport(respond), follow_redirects=False) as client:
        with pytest.raises(ValueError, match="reviewed official"):
            fetch_document(client, "https://docs.python.org/old", {"docs.python.org"})
    assert hosts == ["docs.python.org"]
