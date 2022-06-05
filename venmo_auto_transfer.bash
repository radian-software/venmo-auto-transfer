#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_PATH="${SCRIPT_DIR}/venmo_auto_transfer.bash"

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    export SAVED_WD="${PWD}"
    cd "${SCRIPT_DIR}"
    exec poetry run "${SCRIPT_PATH}" "$@"
fi

if [[ -n "${SAVED_WD:-}" ]]; then
    cd "${SAVED_WD}"
    unset SAVED_WD
fi

if ! diff -q "${SCRIPT_DIR}/poetry.lock" "${VIRTUAL_ENV}/poetry.lock" &>/dev/null; then
    (
        cd "${SCRIPT_DIR}"
        poetry install
        cp "${SCRIPT_DIR}/poetry.lock" "${VIRTUAL_ENV}/poetry.lock"
    )
fi

function venmo_auto_transfer {
    "${SCRIPT_DIR}/venmo_auto_transfer.py" "$@"
}

venmo_auto_transfer "$@"
