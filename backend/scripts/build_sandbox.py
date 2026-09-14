import time

import docker

from app.config import settings

client = docker.DockerClient(base_url=settings.docker_host, timeout=900)
for attempt in range(60):
    try:
        client.ping()
        break
    except docker.errors.DockerException:
        time.sleep(1)
else:
    raise SystemExit("Execution daemon did not become ready.")

print("Building the isolated, five-language execution image...", flush=True)
for entry in client.api.build(path="/app/sandbox", tag=settings.sandbox_image, rm=True, decode=True):
    if "stream" in entry:
        print(entry["stream"], end="", flush=True)
    if "error" in entry:
        raise SystemExit(entry["error"])
print("Sandbox image ready.", flush=True)

