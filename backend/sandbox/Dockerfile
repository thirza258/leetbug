FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 nodejs openjdk-17-jdk-headless libgoogle-gson-java \
    g++ nlohmann-json3-dev golang-go ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY runner.py /opt/runner.py
RUN chmod 555 /opt/runner.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp GOCACHE=/opt/go-cache GOPATH=/tmp/go
# Precompile the Go standard library so a submission does not pay its cold build cost.
RUN mkdir -p /opt/go-cache && printf 'package main\nimport ("encoding/json"; "os")\nfunc main(){json.NewEncoder(os.Stdout).Encode(0)}\n' > /tmp/warm.go \
    && go build -o /tmp/warm /tmp/warm.go && rm /tmp/warm /tmp/warm.go \
    && chmod -R a+rX /opt/go-cache
USER 10001:10001
WORKDIR /tmp
ENTRYPOINT ["python3", "-I", "/opt/runner.py"]

