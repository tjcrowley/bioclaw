#!/bin/sh
# Builds and starts the Compose stack, polls the health endpoint, and
# tears down. Asserts the --workers 1 constraint is structural (no
# command:/entrypoint: override present in the resolved config) --
# DOCK-01 criteria 1 and 2.
set -e

# POSIX character class, not "\s": \s is a GNU extension and silently fails to
# match under a strict BSD grep, which would turn the criterion-2 assertion
# below into a false pass.
OVERRIDE_RE="^[[:space:]]*(command|entrypoint):"

echo "==> Validating compose config has no command:/entrypoint: override (DOCK-01 criterion 2)"
if docker compose config | grep -qE "$OVERRIDE_RE"; then
  echo "FAIL: docker-compose.yml declares command:/entrypoint: -- the single-worker constraint must come only from the image's ENTRYPOINT" >&2
  exit 1
fi

echo "==> Validating blank-credential guard"
# webapp/backend/auth.py::_valid treats an empty-string password as a valid
# expected value, so a blank BIOCLAW_WEB_PASSWORD authenticates anyone sending
# an empty password. docker-compose.yml uses ${VAR:?} to make Compose refuse to
# start in that case; assert the guard is still present.
if ! grep -q 'BIOCLAW_WEB_PASSWORD:?' docker-compose.yml; then
  echo "FAIL: docker-compose.yml lost its \${BIOCLAW_WEB_PASSWORD:?...} guard -- a blank password would start a wide-open instance" >&2
  exit 1
fi

echo "==> Building"
docker compose build

echo "==> Starting"
docker compose up -d

cleanup() {
  docker compose logs backend || true
  docker compose down
}

echo "==> Polling /api/health"
ok=0
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 2
done

if [ "$ok" -ne 1 ]; then
  echo "FAIL: /api/health did not become healthy in time" >&2
  cleanup
  exit 1
fi

echo "==> Healthy. Tearing down."
docker compose down
echo "==> Smoke test passed."
