#!/bin/bash
# dc.sh - podman-compose wrapper
#
# 문제: podman-compose 1.3.0 + podman 4.0.2 조합에서
#   "podman-compose up -d"가 depends_on 의존 컨테이너를 재생성하려다
#   hang 걸리고, 하위 서비스가 Created 상태에서 멈추는 버그가 있음.
#
# 해결: podman-compose는 create(컨테이너 생성)에만 사용하고,
#   실제 start는 podman으로 직접 의존성 순서대로 실행.

set -e
cd "$(dirname "$0")"

# pyenv venv 활성화 (podman-compose가 venv에 설치되어 있음)
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/versions/venv/bin:$PYENV_ROOT/bin:$PATH"

CONTAINERS_ORDER=(postgres-db redis netview_fastapi netview_django netview_nginx network-admin-batch)
HEALTHY_CONTAINERS=(postgres-db netview_fastapi netview_django)

wait_healthy() {
  local name="$1" max="${2:-30}"
  echo "  Waiting for $name to be healthy..."
  for i in $(seq 1 "$max"); do
    if podman healthcheck run "$name" &>/dev/null; then
      echo "  $name is healthy."
      return 0
    fi
    [ "$i" -eq "$max" ] && { echo "  WARNING: $name health timeout" >&2; return 1; }
    sleep 2
  done
}

do_up() {
  echo "=== Starting all services ==="

  # 1) 컨테이너가 없으면 생성 (podman-compose create는 hang 안 걸림)
  echo "[1/3] Creating containers..."
  podman-compose up --no-start 2>&1 | grep -v "already in use" || true

  # 2) 의존성 순서대로 podman start
  echo "[2/3] Starting containers in order..."

  # postgres, redis 먼저
  echo "  Starting postgres-db, redis..."
  podman start postgres-db 2>/dev/null || true
  podman start redis 2>/dev/null || true
  wait_healthy postgres-db 30

  # FastAPI (postgres, redis 의존)
  echo "  Starting netview_fastapi..."
  podman start netview_fastapi 2>/dev/null || true
  wait_healthy netview_fastapi 20

  # Django (postgres 의존)
  echo "  Starting netview_django..."
  podman start netview_django 2>/dev/null || true
  wait_healthy netview_django 30

  # Nginx, Batch (django, fastapi 의존)
  echo "  Starting netview_nginx, network-admin-batch..."
  podman start netview_nginx 2>/dev/null || true
  podman start network-admin-batch 2>/dev/null || true

  # 3) 결과 확인
  echo ""
  echo "[3/3] Final status:"
  podman ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

do_down() {
  echo "=== Stopping all services ==="
  # 역순으로 stop
  for name in network-admin-batch netview_nginx netview_django netview_fastapi redis postgres-db; do
    podman stop "$name" 2>/dev/null && echo "  Stopped $name" || true
  done
  podman-compose down 2>/dev/null || true
}

case "${1:-up}" in
  up)       do_up ;;
  down)     do_down ;;
  restart)  do_down; sleep 2; do_up ;;
  status)   podman ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" ;;
  logs)
    if [ -n "$2" ]; then
      podman logs --tail 50 -f "$2"
    else
      podman-compose logs --tail 50
    fi
    ;;
  *)
    echo "Usage: $0 {up|down|restart|status|logs [container]}"
    exit 1
    ;;
esac
