import json
import math
import socket
import time

import docker
from docker.errors import DockerException
from requests.exceptions import RequestException

from app.config import settings


class SandboxUnavailable(Exception):
    pass


def equal(actual, expected):
    # Python considers True == 1; JSON contracts do not.
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(actual) is type(expected) and actual == expected
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(expected, dict):
        return isinstance(actual, dict) and actual.keys() == expected.keys() and all(
            equal(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            equal(a, b) for a, b in zip(actual, expected, strict=True)
        )
    return type(actual) is type(expected) and actual == expected


def at_path(value, path):
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def grade(tests, execution):
    """The only grading authority. Hidden case inputs, expectations, errors stay private."""
    if execution.get("fatal_status"):
        return execution["fatal_status"], []
    if execution.get("compile_error"):
        return "runtime_error", [{"name": "Compilation", "hidden": False, "status": "runtime_error",
                                  "message": execution["compile_error"][:4000]}]
    raw_results = execution.get("results", [])
    if not isinstance(raw_results, list) or len(raw_results) != len(tests):
        return "runtime_error", [{"name": "Execution", "hidden": False, "status": "runtime_error",
                                  "message": "Program returned an invalid number of results."}]
    results = []
    for index, (test, raw) in enumerate(zip(tests, raw_results, strict=True), 1):
        if not isinstance(raw, dict):
            raw = {"status": "runtime_error", "stderr": "Invalid program output."}
        actual = raw.get("output")
        assertions = []
        for assertion in test.get("assertions", []):
            try:
                ok = equal(at_path(actual, assertion["path"]), assertion["equals"])
            except (KeyError, IndexError, TypeError, ValueError):
                ok = False
            assertions.append({"path": assertion["path"], "passed": ok, "expected": assertion["equals"]})
        status = raw.get("status", "runtime_error")
        if status == "ok":
            status = "passed" if equal(actual, test["expected"]) and all(a["passed"] for a in assertions) else "failed"
        if status not in {"passed", "failed", "runtime_error", "time_limit", "output_limit"}:
            status = "runtime_error"
        result = {"name": f"Hidden case {index}" if test["hidden"] else test["name"],
                  "hidden": test["hidden"], "status": status}
        if not test["hidden"]:
            result.update(input=test["input"], expected=test["expected"], actual=actual,
                          assertions=assertions, message=str(raw.get("stderr", ""))[:4000],
                          runtime_ms=raw.get("runtime_ms", 0))
        results.append(result)
    statuses = {r["status"] for r in results}
    overall = next((s for s in ["time_limit", "output_limit", "runtime_error", "failed"] if s in statuses), "passed")
    return overall, results


def execute_code(language, code, tests):
    client = docker.DockerClient(base_url=settings.docker_host, timeout=10)
    container = None
    transport = None
    start = time.monotonic()
    try:
        container = client.containers.create(
            settings.sandbox_image, network_mode="none", read_only=True,
            mem_limit=f"{settings.sandbox_memory_mb}m", memswap_limit=f"{settings.sandbox_memory_mb}m",
            nano_cpus=1_000_000_000, pids_limit=96, cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"], user="10001:10001", stdin_open=True,
            tmpfs={"/tmp": "rw,nosuid,nodev,size=192m,mode=1777"},
            environment={"GOMAXPROCS": "1", "GOTOOLCHAIN": "local"},
            labels={"app": "leetbug-sandbox", "expires_at": str(time.time() + settings.sandbox_timeout_seconds + 15)},
            log_config=docker.types.LogConfig(type="json-file", config={"max-size": "1m", "max-file": "1"}),
        )
        transport = container.attach_socket(params={"stdin": 1, "stream": 1})
        container.start()
        raw_socket = getattr(transport, "_sock", transport)
        raw_socket.sendall(json.dumps({"language": language, "code": code,
                                      "inputs": [test["input"] for test in tests]}).encode())
        raw_socket.shutdown(socket.SHUT_WR)
        try:
            outcome = container.wait(timeout=settings.sandbox_timeout_seconds)
        except (RequestException, DockerException, TimeoutError):
            return {"fatal_status": "time_limit", "results": [], "runtime_ms": (time.monotonic() - start) * 1000}
        container.reload()
        if container.attrs["State"].get("OOMKilled"):
            return {"fatal_status": "memory_limit", "results": [], "runtime_ms": (time.monotonic() - start) * 1000}
        logs = container.logs(stdout=True, stderr=False, tail=20)
        if outcome["StatusCode"] != 0 or len(logs) > 128000:
            return {"fatal_status": "runtime_error", "results": [], "runtime_ms": (time.monotonic() - start) * 1000}
        try:
            result = json.loads(logs)
            if not isinstance(result, dict):
                raise ValueError("Invalid response")
        except (ValueError, TypeError):
            return {"fatal_status": "runtime_error", "results": []}
        # Wall time is measured outside the container and cannot be forged by the program.
        result["runtime_ms"] = round((time.monotonic() - start) * 1000, 2)
        memory = result.get("memory_kb")
        result["memory_kb"] = min(memory, settings.sandbox_memory_mb * 1024) if isinstance(memory, int) and memory >= 0 else None
        return result
    except (DockerException, RequestException, OSError) as exc:
        raise SandboxUnavailable("The isolated execution service is unavailable. Please retry shortly.") from exc
    finally:
        if transport:
            transport.close()
        if container:
            try:
                container.remove(force=True)
            except DockerException:
                pass
        client.close()

