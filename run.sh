#!/usr/bin/env bash
# Fallback one-command runner for when Docker is unavailable.
# Prefer:  docker compose up --build
set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
PORT_API="${PORT_API:-8000}"
PORT_WEB="${PORT_WEB:-3000}"
VENV="backend/.venv"

command -v "$PYTHON" >/dev/null || { echo "python3 not found"; exit 1; }

echo "==> Setting up the Python environment"
[ -d "$VENV" ] || "$PYTHON" -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r backend/requirements.txt

export TWIN_DB_PATH="${TWIN_DB_PATH:-$PWD/data/twin.db}"
mkdir -p "$(dirname "$TWIN_DB_PATH")"

cleanup() { jobs -p | xargs -r kill 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "==> Starting the Twin API on :$PORT_API"
( cd backend && "../$VENV/bin/uvicorn" app.main:app --host 0.0.0.0 --port "$PORT_API" ) &

echo "==> Waiting for the API (it seeds 1,000 customers on first boot)"
for _ in $(seq 1 90); do
  if curl -fsS "http://localhost:$PORT_API/api/health" >/dev/null 2>&1; then
    echo "    API is up."
    break
  fi
  sleep 1
done

# Serve the frontend and proxy /api to the backend, so there is one origin and
# no CORS - the same arrangement nginx provides in the Docker setup.
echo "==> Starting the frontend on :$PORT_WEB"
"$VENV/bin/python" - "$PORT_WEB" "$PORT_API" <<'PY' &
import http.server, socketserver, sys, urllib.error, urllib.request, os

WEB_PORT, API_PORT = int(sys.argv[1]), int(sys.argv[2])
os.chdir(os.path.join(os.path.dirname(os.path.abspath("run.sh")), "frontend"))

class Handler(http.server.SimpleHTTPRequestHandler):
    def _proxy(self, body=None):
        url = f"http://localhost:{API_PORT}{self.path}"
        req = urllib.request.Request(
            url, data=body, method=self.command,
            headers={"Content-Type": self.headers.get("Content-Type", "application/json")},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as upstream:
                payload = upstream.read()
                self.send_response(upstream.status)
                self.send_header("Content-Type", upstream.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            self.send_response(exc.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as exc:
            self.send_error(502, f"Twin API unreachable: {exc}")

    def _is_api(self):
        return self.path.startswith(("/api/", "/docs", "/openapi.json", "/redoc"))

    def do_GET(self):
        self._proxy() if self._is_api() else super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        self._proxy(self.rfile.read(length) if length else b"")

    def do_DELETE(self):
        self._proxy()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):
        pass

socketserver.TCPServer.allow_reuse_address = True
with socketserver.ThreadingTCPServer(("", WEB_PORT), Handler) as httpd:
    httpd.serve_forever()
PY

sleep 2
cat <<BANNER

  ------------------------------------------------------------------
   Financial Twin is running

     Demo        http://localhost:$PORT_WEB
     Twin API    http://localhost:$PORT_API/api/health
     API docs    http://localhost:$PORT_API/docs

   Tier 3: ${ANTHROPIC_API_KEY:+Claude (ANTHROPIC_API_KEY found)}${ANTHROPIC_API_KEY:-deterministic templates (no API key needed)}

   Ctrl+C to stop.
  ------------------------------------------------------------------

BANNER

wait
