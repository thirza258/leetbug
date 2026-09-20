import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sqlalchemy import text

from app.api import router
from app.config import settings
from app.db import engine
from app.limits import redis_client
from app.sitemap import generate_robots_txt, generate_sitemap_xml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("leetbug.http")
app = FastAPI(title="LeetBug API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=True,
                   allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type", "X-CSRF-Token"])


@app.middleware("http")
async def boundary(request: Request, call_next):
    started = time.monotonic()
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") not in settings.origins:
            return JSONResponse({"detail": "This request origin is not allowed."}, status_code=403)
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse({"detail": "Invalid content length."}, status_code=400)
        if length > 100000:
            return JSONResponse({"detail": "Request exceeds the 100 KB limit."}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    log.info("%s %s status=%s duration_ms=%.2f", request.method, request.url.path,
             response.status_code, (time.monotonic() - started) * 1000)
    return response


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/ready")
def ready():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        redis_client.ping()
        return {"status": "ready", "database": "ok", "queue": "ok"}
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return PlainTextResponse(generate_robots_txt(), media_type="text/plain")


@app.get("/sitemap.xml", response_class=Response)
def sitemap_xml():
    return Response(content=generate_sitemap_xml(), media_type="application/xml")


app.include_router(router)

