"""Unprivileged transport harness. It receives inputs, NEVER test expectations.

The worker is the grading authority. All data returned here remains untrusted.
Each test launches a fresh process. Compilation and process output are bounded.
"""
import json
import os
import resource
import selectors
import subprocess
import sys
import tempfile
import time
from pathlib import Path

OUTPUT_LIMIT = 16384
PYTHON_DRIVER = '''import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("solution", "solution.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
data = json.loads(sys.stdin.read())
print(json.dumps(mod.solve(data), allow_nan=False))
'''
JS_DRIVER = '''const fs = require('fs');
const { solve } = require('./solution.js');
Promise.resolve().then(() => solve(JSON.parse(fs.readFileSync(0, 'utf8'))))
  .then(result => process.stdout.write(JSON.stringify(result)))
  .catch(error => { console.error(error.stack); process.exitCode = 1; });
'''
JAVA_DRIVER = '''import com.google.gson.*;
import java.io.*;
public class Main {
  public static void main(String[] args) throws Exception {
    JsonObject input = JsonParser.parseReader(new InputStreamReader(System.in)).getAsJsonObject();
    System.out.print(new Gson().toJson(Solution.solve(input)));
  }
}
'''
CPP_DRIVER = '''#include <iostream>
#include "solution.cpp"
int main() { nlohmann::json data; std::cin >> data; std::cout << solve(data).dump(); }
'''
GO_DRIVER = '''package main
import ("encoding/json"; "os")
func main() {
  var data map[string]interface{}
  if err := json.NewDecoder(os.Stdin).Decode(&data); err != nil { panic(err) }
  if err := json.NewEncoder(os.Stdout).Encode(Solve(data)); err != nil { panic(err) }
}
'''


def execute(command, data, timeout):
    started = time.monotonic()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        process.stdin.write(data.encode())
        process.stdin.close()
    except BrokenPipeError:
        pass
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    output = {"stdout": bytearray(), "stderr": bytearray()}
    status = None
    try:
        while selector.get_map():
            if time.monotonic() - started > timeout:
                status = "time_limit"
                break
            for key, _ in selector.select(timeout=0.025):
                chunk = os.read(key.fileobj.fileno(), 4096)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                output[key.data].extend(chunk)
                if sum(len(v) for v in output.values()) > OUTPUT_LIMIT:
                    status = "output_limit"
                    break
            if status:
                break
    finally:
        # Kill descendants too (including children keeping stdout open).
        try:
            os.killpg(process.pid, 9)
        except ProcessLookupError:
            pass
        process.wait(timeout=2)
        selector.close()
        process.stdout.close()
        process.stderr.close()
    elapsed = round((time.monotonic() - started) * 1000, 2)
    return {
        "status": status or ("ok" if process.returncode == 0 else "runtime_error"),
        "stdout": output["stdout"][:OUTPUT_LIMIT].decode(errors="replace"),
        "stderr": output["stderr"][:OUTPUT_LIMIT].decode(errors="replace"),
        "runtime_ms": elapsed,
    }


def run(payload):
    language, source = payload["language"], payload["code"]
    Path("go-cache").mkdir()
    # Copy-on-write Go build cache is writable without changing the image's cache.
    os.environ["GOCACHE"] = str(Path("go-cache").resolve())
    if language == "go":
        import shutil
        shutil.copytree("/opt/go-cache", "go-cache", dirs_exist_ok=True)
    configurations = {
        "python": ("solution.py", "main.py", PYTHON_DRIVER, None, ["python3", "-I", "main.py"]),
        "javascript": ("solution.js", "main.js", JS_DRIVER, None, ["node", "--max-old-space-size=128", "main.js"]),
        "java": ("Solution.java", "Main.java", JAVA_DRIVER,
                 ["javac", "-J-Xmx128m", "-cp", "/usr/share/java/gson.jar", "Solution.java", "Main.java"],
                 ["java", "-Xmx128m", "-XX:MaxMetaspaceSize=96m", "-XX:ReservedCodeCacheSize=32m",
                  "-XX:ActiveProcessorCount=1", "-XX:+UseSerialGC", "-cp", ".:/usr/share/java/gson.jar", "Main"]),
        "cpp": ("solution.cpp", "main.cpp", CPP_DRIVER,
                ["g++", "-std=c++17", "-O1", "-o", "program", "main.cpp"], ["./program"]),
        "go": ("solution.go", "main.go", GO_DRIVER,
               ["go", "build", "-p", "1", "-o", "program", "main.go", "solution.go"], ["./program"]),
    }
    source_name, driver_name, driver, compile_cmd, run_cmd = configurations[language]
    Path(source_name).write_text(source)
    Path(driver_name).write_text(driver)
    if compile_cmd:
        compiled = execute(compile_cmd, "", 30)
        if compiled["status"] != "ok":
            return {"compile_error": compiled["stderr"] or compiled["status"], "results": []}
    results = []
    for data in payload["inputs"]:
        result = execute(run_cmd, json.dumps(data), 2)
        if result["status"] == "ok":
            try:
                result["output"] = json.loads(result.pop("stdout"), parse_constant=lambda _: None)
            except (ValueError, TypeError):
                result["status"] = "runtime_error"
                result["stderr"] = "Expected a single JSON result. Remove debug prints from standard output."
        else:
            result.pop("stdout", None)
        results.append(result)
    return {"results": results, "memory_kb": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss}


if __name__ == "__main__":
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    payload = json.loads(sys.stdin.buffer.read(256000))
    with tempfile.TemporaryDirectory(prefix="submission-") as directory:
        os.chdir(directory)
        try:
            result = run(payload)
        except Exception as exc:
            result = {"compile_error": f"Harness could not execute the program: {type(exc).__name__}", "results": []}
        print(json.dumps(result, allow_nan=False))

