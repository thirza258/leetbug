"""Helpers for writing incident artifacts compactly and consistently.

Every value they produce is plain JSON. Timestamps are UTC ISO-8601 strings; log timestamps carry
milliseconds so entries in the same second keep their order.
"""
from datetime import datetime, timedelta

ISO = "%Y-%m-%dT%H:%M:%SZ"


def at(base: str, minutes: float = 0, seconds: float = 0) -> str:
    """``base`` shifted by the given minutes and seconds, to whole seconds."""
    return (datetime.strptime(base, ISO) + timedelta(minutes=minutes, seconds=seconds)).strftime(ISO)


def ts(base: str, seconds: float) -> str:
    """``base`` shifted by ``seconds``, with millisecond precision (for log entries)."""
    moment = datetime.strptime(base, ISO) + timedelta(milliseconds=round(seconds * 1000))
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def log(timestamp: str, level: str, service: str, message: str, trace_id: str | None = None, **fields) -> dict:
    entry = {"ts": timestamp, "level": level, "service": service, "message": message, "fields": fields}
    if trace_id:
        entry["trace_id"] = trace_id
    return entry


def series(name: str, unit: str, start: str, step_minutes: float, values: list) -> dict:
    """A metric series with one point every ``step_minutes`` from ``start``."""
    return {"name": name, "unit": unit,
            "points": [[at(start, minutes=index * step_minutes), value] for index, value in enumerate(values)]}


def span(span_id: str, parent_id: str | None, service: str, name: str, start_ms: float, duration_ms: float,
         status: str = "ok", **attributes) -> dict:
    return {"span_id": span_id, "parent_id": parent_id, "service": service, "name": name,
            "start_ms": start_ms, "duration_ms": duration_ms, "status": status, "attributes": attributes}


def artifact(artifact_id: str, kind: str, title: str, description: str, data: dict) -> dict:
    return {"id": artifact_id, "type": kind, "title": title, "description": description, "data": data}


def text_artifact(artifact_id: str, kind: str, title: str, description: str, path: str, language: str,
                  content: str) -> dict:
    return artifact(artifact_id, kind, title, description,
                    {"path": path, "language": language, "content": content.strip("\n") + "\n"})


def event(timestamp: str, kind: str, title: str, detail: str) -> dict:
    return {"at": timestamp, "kind": kind, "title": title, "detail": detail}
