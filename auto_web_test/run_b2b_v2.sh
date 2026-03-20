#!/bin/zsh

set -euo pipefail

SCRIPT_DIR="${0:A:h}"
REPO_ROOT="${SCRIPT_DIR:h}"
ENV_FILE="${1:-}"

EXPLICIT_B2B_HEADLESS="${B2B_HEADLESS-__UNSET__}"
EXPLICIT_SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL-__UNSET__}"

if [[ -z "${ENV_FILE}" ]]; then
  echo "Usage: auto_web_test/run_b2b_v2.sh <env-file> [pytest-args...]"
  echo "Example: auto_web_test/run_b2b_v2.sh auto_web_test/.env.dev -k test_verify_statistics_details_v2"
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Env file not found: ${ENV_FILE}"
  exit 1
fi

shift

set -a
source "${ENV_FILE}"
set +a

if [[ "${EXPLICIT_B2B_HEADLESS}" != "__UNSET__" ]]; then
  export B2B_HEADLESS="${EXPLICIT_B2B_HEADLESS}"
fi

if [[ "${EXPLICIT_SLACK_WEBHOOK_URL}" != "__UNSET__" ]]; then
  export SLACK_WEBHOOK_URL="${EXPLICIT_SLACK_WEBHOOK_URL}"
fi

cd "${REPO_ROOT}"

if [[ -x "${REPO_ROOT}/.venv/bin/pytest" ]]; then
  PYTEST_BIN="${REPO_ROOT}/.venv/bin/pytest"
elif command -v pytest >/dev/null 2>&1; then
  PYTEST_BIN="$(command -v pytest)"
else
  echo "pytest not found. Create/activate .venv or install pytest."
  exit 1
fi

"${PYTEST_BIN}" -q -s auto_web_test/B2B_tests/test_b2b_v2.py "$@"
