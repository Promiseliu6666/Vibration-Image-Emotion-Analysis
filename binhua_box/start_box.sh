#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/box.env"
LOG_FILE="${SCRIPT_DIR}/box.log"

if [ ! -f "${ENV_FILE}" ]; then
  echo "missing ${ENV_FILE}"
  echo "copy ${SCRIPT_DIR}/box.env.example to ${ENV_FILE} and update BOX_SERIAL, BOX_PUBLIC_HOST, and RabbitMQ settings"
  exit 1
fi

set -a
source "${ENV_FILE}"
set +a

cd "${SCRIPT_DIR}"
nohup python3 main.py > "${LOG_FILE}" 2>&1 &
echo "box started, pid=$!, log: ${LOG_FILE}"
