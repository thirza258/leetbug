#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
  cp .env.example .env
  task_password=$(openssl rand -hex 24)
  task_env=$(mktemp)
  sed "s/change-this-local-password/$task_password/" .env > "$task_env"
  mv "$task_env" .env
  chmod 600 .env
fi
docker compose up -d --build
port=$(grep -E '^APP_PORT=' .env 2>/dev/null | cut -d '=' -f2 || echo "9042")
printf '\nLeetBug is starting at http://localhost:%s\nFollow startup: docker compose logs -f worker sandbox-build\n' "${port:-9042}"

