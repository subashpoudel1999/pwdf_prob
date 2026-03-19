#!/bin/bash
# run.sh — starts backend + Flutter together
# Usage: bash run.sh

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PID=""

cleanup() {
  echo ""
  echo "Stopping backend..."
  if [ -n "$BACKEND_PID" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# Kill any stale process on port 8000
echo "Checking port 8000..."
powershell -Command "
  \$result = netstat -ano | Select-String ':8000\s.*LISTENING'
  if (\$result) {
    \$pid = (\$result -split '\s+')[-1]
    Stop-Process -Id \$pid -Force -ErrorAction SilentlyContinue
    Write-Host 'Killed stale process on port 8000'
  }
" 2>/dev/null || true

# Start backend
echo "Starting backend (uvicorn on port 8000)..."
cd "$PROJECT_ROOT/backend"
uvicorn main:app --host 0.0.0.0 --port 8000 > "$PROJECT_ROOT/backend.log" 2>&1 &
BACKEND_PID=$!

# Wait and verify it started
echo "Waiting for backend to be ready..."
sleep 4
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  echo ""
  echo "ERROR: Backend failed to start. Last lines of backend.log:"
  tail -20 "$PROJECT_ROOT/backend.log"
  exit 1
fi
echo "Backend running (PID: $BACKEND_PID, log: backend.log)"

# Run Flutter
cd "$PROJECT_ROOT"
flutter run -d chrome
