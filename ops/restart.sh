#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-status}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

HOST="127.0.0.1"
SEESEA_PORT="8888"
API_PORT="8000"
FRONTEND_PORT="4321"

RUN_DIR="/tmp/moyu-local"
SEESEA_LOG="$RUN_DIR/seesea.log"
API_LOG="$RUN_DIR/api.log"
FRONTEND_LOG="$RUN_DIR/frontend.log"
STOCK_SCHEDULER_LOG="$RUN_DIR/seesea-stock-scheduler.log"

SEESEA_PID_FILE="$RUN_DIR/seesea.pid"
API_PID_FILE="$RUN_DIR/api.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
STOCK_SCHEDULER_PID_FILE="$RUN_DIR/stock-scheduler.pid"

SEESEA_BIN="$BACKEND_DIR/.venv/bin/seesea"
UVICORN_BIN="$BACKEND_DIR/.venv/bin/uvicorn"
ASTRO_BIN="$FRONTEND_DIR/node_modules/.bin/astro"
SCHEDULER_CONFIG="$BACKEND_DIR/seesea/seesea-core/config/scheduler.toml"

mkdir -p "$RUN_DIR"

log() {
  printf '%s\n' "$*"
}

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    log "Missing required file: $path"
    exit 1
  fi
}

is_listening() {
  local port="$1"
  lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

wait_http_ready() {
  local name="$1"
  local url="$2"
  local timeout="${3:-45}"
  local elapsed=0

  while (( elapsed < timeout )); do
    if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
      log "$name ready: $url"
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done

  log "$name not ready after ${timeout}s: $url"
  return 1
}

stop_port_process() {
  local port="$1"
  local pids

  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN || true)"
  if [[ -z "$pids" ]]; then
    return 0
  fi

  log "Stopping listeners on port $port: $pids"
  kill $pids || true
  sleep 1

  if is_listening "$port"; then
    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN || true)"
    if [[ -n "$pids" ]]; then
      log "Force stopping listeners on port $port: $pids"
      kill -9 $pids || true
    fi
  fi
}

start_seesea() {
  if is_listening "$SEESEA_PORT"; then
    log "SeeSea already running on $HOST:$SEESEA_PORT"
    return 0
  fi

  log "Starting SeeSea on $HOST:$SEESEA_PORT"
  (
    cd "$BACKEND_DIR"
    nohup env NO_PROXY='*' no_proxy='*' HTTP_PROXY='' HTTPS_PROXY='' ALL_PROXY='' \
      "$SEESEA_BIN" server --host "$HOST" --port "$SEESEA_PORT" \
      >"$SEESEA_LOG" 2>&1 &
    local pid=$!
    disown "$pid" 2>/dev/null || true
    echo "$pid" >"$SEESEA_PID_FILE"
  )
}

start_api() {
  if is_listening "$API_PORT"; then
    log "API already running on $HOST:$API_PORT"
    return 0
  fi

  log "Starting API on $HOST:$API_PORT"
  (
    cd "$BACKEND_DIR"
    nohup env NO_PROXY='*' no_proxy='*' HTTP_PROXY='' HTTPS_PROXY='' ALL_PROXY='' PYTHONPATH=. \
      "$UVICORN_BIN" app.main:app --host "$HOST" --port "$API_PORT" \
      >"$API_LOG" 2>&1 &
    local pid=$!
    disown "$pid" 2>/dev/null || true
    echo "$pid" >"$API_PID_FILE"
  )
}

start_frontend() {
  if is_listening "$FRONTEND_PORT"; then
    log "Frontend already running on $HOST:$FRONTEND_PORT"
    return 0
  fi

  log "Starting frontend on $HOST:$FRONTEND_PORT"
  (
    cd "$FRONTEND_DIR"
    nohup env NO_PROXY='*' no_proxy='*' HTTP_PROXY='' HTTPS_PROXY='' ALL_PROXY='' \
      PUBLIC_API_BASE="http://$HOST:$API_PORT/api" \
      "$ASTRO_BIN" dev --host "$HOST" --port "$FRONTEND_PORT" \
      >"$FRONTEND_LOG" 2>&1 &
    local pid=$!
    disown "$pid" 2>/dev/null || true
    echo "$pid" >"$FRONTEND_PID_FILE"
  )
}

start_stock_scheduler() {
  if [[ ! -f "$SCHEDULER_CONFIG" ]]; then
    log "Stock scheduler config missing: $SCHEDULER_CONFIG"
    return 0
  fi

  if [[ -f "$STOCK_SCHEDULER_PID_FILE" ]]; then
    local pid
    pid="$(cat "$STOCK_SCHEDULER_PID_FILE" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      log "Stock scheduler already running (pid: $pid)"
      return 0
    fi
  fi

  log "Starting stock scheduler"
  (
    cd "$ROOT_DIR"
    nohup env NO_PROXY='*' no_proxy='*' HTTP_PROXY='' HTTPS_PROXY='' ALL_PROXY='' \
      "$SEESEA_BIN" stock-scheduler -c "$SCHEDULER_CONFIG" \
      >"$STOCK_SCHEDULER_LOG" 2>&1 &
    local pid=$!
    disown "$pid" 2>/dev/null || true
    echo "$pid" >"$STOCK_SCHEDULER_PID_FILE"
  )
}

show_status() {
  if is_listening "$SEESEA_PORT"; then
    log "SeeSea: listening on $HOST:$SEESEA_PORT"
  else
    log "SeeSea: stopped"
  fi

  if is_listening "$API_PORT"; then
    log "API: listening on $HOST:$API_PORT"
  else
    log "API: stopped"
  fi

  if is_listening "$FRONTEND_PORT"; then
    log "Frontend: listening on $HOST:$FRONTEND_PORT"
  else
    log "Frontend: stopped"
  fi

  if curl -fsS --max-time 5 "http://$HOST:$SEESEA_PORT/api/health" >/dev/null 2>&1; then
    log "SeeSea health: ok"
  else
    log "SeeSea health: fail"
  fi

  if curl -fsS --max-time 5 "http://$HOST:$API_PORT/healthz" >/dev/null 2>&1; then
    log "API health: ok"
  else
    log "API health: fail"
  fi

  if curl -fsS --max-time 5 "http://$HOST:$FRONTEND_PORT/" >/dev/null 2>&1; then
    log "Frontend health: ok"
  else
    log "Frontend health: fail"
  fi

  if [[ -f "$STOCK_SCHEDULER_PID_FILE" ]]; then
    local pid
    pid="$(cat "$STOCK_SCHEDULER_PID_FILE" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      log "Stock scheduler: running (pid: $pid)"
    else
      log "Stock scheduler: stopped"
    fi
  else
    log "Stock scheduler: unknown"
  fi

  log "Logs: $RUN_DIR"
}

start_all() {
  require_file "$SEESEA_BIN"
  require_file "$UVICORN_BIN"
  require_file "$ASTRO_BIN"

  start_seesea
  wait_http_ready "SeeSea" "http://$HOST:$SEESEA_PORT/api/health" 60

  start_api
  wait_http_ready "API" "http://$HOST:$API_PORT/healthz" 60

  start_frontend
  wait_http_ready "Frontend" "http://$HOST:$FRONTEND_PORT/" 90
  start_stock_scheduler

  show_status
}

stop_all() {
  if [[ -f "$STOCK_SCHEDULER_PID_FILE" ]]; then
    local pid
    pid="$(cat "$STOCK_SCHEDULER_PID_FILE" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      log "Stopping stock scheduler pid $pid"
      kill "$pid" || true
      sleep 1
      if kill -0 "$pid" >/dev/null 2>&1; then
        kill -9 "$pid" || true
      fi
    fi
  fi

  stop_port_process "$FRONTEND_PORT"
  stop_port_process "$API_PORT"
  stop_port_process "$SEESEA_PORT"

  rm -f "$SEESEA_PID_FILE" "$API_PID_FILE" "$FRONTEND_PID_FILE" "$STOCK_SCHEDULER_PID_FILE"
  log "All local services stopped"
}

case "$ACTION" in
  start)
    start_all
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    start_all
    ;;
  status)
    show_status
    ;;
  *)
    log "Usage: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac
