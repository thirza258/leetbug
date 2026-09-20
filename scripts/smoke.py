"""A small persisted end-to-end flow against an already running Compose deployment."""
import argparse
import time
import uuid

import httpx


def poll(client, resource, timeout=150):
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        response = client.get(resource)
        response.raise_for_status()
        row = response.json()
        if row["status"] not in {"queued", "running"}:
            return row
        time.sleep(0.8)
    raise AssertionError(f"Job timed out: {resource}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--ai", action="store_true", help="Also make a real request to the configured model")
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url, timeout=30) as root_client:
        robots = root_client.get("/robots.txt")
        assert robots.status_code == 200, f"robots.txt failed: {robots.status_code}"
        assert "text/plain" in robots.headers.get("content-type", "")
        assert "User-agent: *" in robots.text
        assert "Sitemap: " in robots.text

        sitemap = root_client.get("/sitemap.xml")
        assert sitemap.status_code == 200, f"sitemap.xml failed: {sitemap.status_code}"
        assert "xml" in sitemap.headers.get("content-type", "")
        assert "<urlset" in sitemap.text
        assert "/problems/" in sitemap.text
        print("Root robots.txt and sitemap.xml: passed.", flush=True)

    with httpx.Client(base_url=args.base_url + "/api", timeout=30) as client:
        name = "smoke_" + uuid.uuid4().hex[:10]
        response = client.post("/auth/register", json={"email": name + "@example.com", "username": name,
                                                     "password": uuid.uuid4().hex + "!Aa"})
        response.raise_for_status()
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        problem = client.get("/problems/missing-last-item").json()
        for _ in range(2):
            response = client.post("/submissions", json={"problem_id": problem["id"], "language": "python",
                                                       "code": problem["starters"]["python"], "kind": "run"})
            response.raise_for_status()
            row = poll(client, "/submissions/" + response.json()["id"])
            assert row["status"] == "failed", row
        response = client.post("/problems/missing-last-item/hints", json={"language": "python"})
        response.raise_for_status()
        hint = poll(client, "/hints/" + response.json()["id"])
        assert hint["status"] == "completed" and hint["sources"], hint
        print(f"Documentation-backed hint: {hint['retrieval']}", flush=True)
        response = client.post("/submissions", json={"problem_id": problem["id"], "language": "python",
                                                   "code": 'def solve(data):\n    return sum(data["nums"])'})
        response.raise_for_status()
        row = poll(client, "/submissions/" + response.json()["id"])
        assert row["status"] == "passed", row
        assert all("expected" not in test for test in row["results"] if test["hidden"])
        assert client.get("/problems/missing-last-item/solutions").status_code == 200
        assert client.get("/analytics/me").json()["solved"] == 1
        print(f"Accepted Python fix: {row['runtime_ms']} ms; progress and solution unlock persisted.", flush=True)
        if args.ai:
            response = client.post("/submissions", json={"problem_id": problem["id"], "language": "python", "mode": "ai",
                "code": problem["starters"]["python"],
                "prompt": 'Replace the loop with return sum(data["nums"]). Include every value and return zero for an empty list. Keep def solve(data). Return only Python source.'})
            response.raise_for_status()
            row = poll(client, "/submissions/" + response.json()["id"])
            assert row["generated_code"] and row["status"] == "passed", row
            print(f"Live AI fix accepted: {row['turnaround_ms']} ms, {row['llm_tokens']} provider tokens.", flush=True)
        print("HTTP → API → PostgreSQL → Celery → sandbox → feedback: passed.", flush=True)


if __name__ == "__main__":
    main()

