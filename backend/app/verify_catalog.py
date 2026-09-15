"""Run the complete catalog and isolation probes against the real sandbox.

docker compose exec worker python -m app.verify_catalog
This calls the same execution/grading boundary as Celery, without creating user history.
"""
import json
import sys

from app.catalog import CATALOG, case
from app.execution import execute_code, grade


def main():
    report = []
    for problem in CATALOG:
        for language in problem["starters"]:
            for variant in ["starters", "solutions"]:
                output = execute_code(language, problem[variant][language], problem["tests"])
                status, results = grade(problem["tests"], output)
                public_failures = sum(not result["hidden"] and result["status"] != "passed" for result in results)
                # A broken scaffold or infrastructure failure is not evidence of an intentional bug.
                complete = not output.get("compile_error") and len(output.get("results", [])) == len(problem["tests"])
                ok = complete and (status == "passed" if variant == "solutions" else public_failures > 0)
                row = {"problem": problem["slug"], "language": language, "variant": variant,
                       "status": status, "ok": ok, "runtime_ms": output.get("runtime_ms"),
                       "test_cases": len(problem["tests"]), "public_failures": public_failures}
                report.append(row)
                print(json.dumps(row), flush=True)
                if not ok:
                    print(json.dumps({"execution": output, "results": results}), flush=True)
    probes = [
        ("network isolation", '''import socket
def solve(data):
    try:
        socket.create_connection(("1.1.1.1", 80), timeout=0.3)
        return False
    except OSError:
        return True
''', True, "passed"),
        ("read-only root", '''def solve(data):
    try:
        open("/etc/leetbug-probe", "w").write("bad")
        return False
    except OSError:
        return True
''', True, "passed"),
        ("unprivileged execution", 'import os\ndef solve(data): return os.getuid() == 10001', True, "passed"),
        ("execution deadline", 'def solve(data):\n    while True: pass', None, "time_limit"),
        ("output cap", 'def solve(data):\n    print("x" * 100000)\n    return 0', 0, "output_limit"),
        ("no supplied oracle", 'import os\ndef solve(data): return not os.path.exists("/var/run/docker.sock")', True, "passed"),
        ("forged grade rejected", 'def solve(data): return {"status": "passed", "fatal_status": "passed"}', 42, "failed"),
    ]
    for name, source, expected, wanted in probes:
        tests = [case(name, {}, expected)]
        output = execute_code("python", source, tests)
        status, _ = grade(tests, output)
        row = {"probe": name, "status": status, "ok": status == wanted}
        report.append(row)
        print(json.dumps(row), flush=True)
    print(json.dumps({"checks": len(report), "passed": sum(row["ok"] for row in report)}), flush=True)
    return 0 if all(row["ok"] for row in report) else 1


if __name__ == "__main__":
    sys.exit(main())
