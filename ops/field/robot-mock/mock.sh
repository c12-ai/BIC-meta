#!/usr/bin/env bash
# Quick start/stop for the field mock robot, with a hard consumer-mutex guard:
# the real mars_interface and this mock must never consume the same
# ${ROBOT_ID}.cmd queue. `up` refuses if the queue already has a consumer.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$HERE/../.env}"
[ -f "$ENV_FILE" ] || { echo "ERROR: $ENV_FILE not found (run deploy.sh init-env first)"; exit 1; }

# shellcheck disable=SC1090
MQ_CONTAINER=$(grep -m1 '^MQ_CONTAINER=' "$ENV_FILE" | cut -d= -f2-); MQ_CONTAINER=${MQ_CONTAINER:-bic-rabbitmq}
ROBOT_ID=$(grep -m1 '^MOCK_ROBOT_ID=' "$ENV_FILE" | cut -d= -f2-); ROBOT_ID=${ROBOT_ID:-talos.001}
CMD_QUEUE="${ROBOT_ID}.cmd"

compose() { docker compose -f "$HERE/docker-compose.yml" --env-file "$ENV_FILE" "$@"; }

cmd_consumers() {
  docker exec "$MQ_CONTAINER" rabbitmqctl list_queues name consumers 2>/dev/null \
    | awk -v q="$CMD_QUEUE" '$1 == q {print $2}'
}

case "${1:-}" in
  up)
    n="$(cmd_consumers)"; n="${n:-0}"
    if [ "$n" -gt 0 ]; then
      echo "✗ REFUSED: ${CMD_QUEUE} already has ${n} consumer(s) — a real robot"
      echo "  (mars_interface) or another mock is live. Two consumers on one cmd"
      echo "  queue split commands nondeterministically. Stop the other side first."
      exit 1
    fi
    compose up -d
    for _ in $(seq 1 15); do
      sleep 2
      n="$(cmd_consumers)"; n="${n:-0}"
      [ "$n" -gt 0 ] && { echo "✓ mock up — ${CMD_QUEUE} consumers: ${n}"; exit 0; }
    done
    echo "✗ mock container started but ${CMD_QUEUE} never gained a consumer — check: docker logs bic-robot-mock"
    exit 1
    ;;
  down)
    compose down
    echo "✓ mock down — ${CMD_QUEUE} consumers now: $(cmd_consumers | head -1)"
    ;;
  status)
    docker ps -a --filter name=bic-robot-mock --format 'table {{.Names}}\t{{.Status}}'
    echo "${CMD_QUEUE} consumers: $(cmd_consumers | head -1)"
    ;;
  logs)
    docker logs --tail "${2:-100}" -f bic-robot-mock
    ;;
  *)
    echo "usage: $0 up|down|status|logs [n]"
    echo "  up      start mock (REFUSES if ${CMD_QUEUE} already has a consumer)"
    echo "  down    stop mock (run this BEFORE bringing up the real robot)"
    exit 2
    ;;
esac
