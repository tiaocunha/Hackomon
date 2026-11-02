#!/bin/bash
# Title: Hackomon
# Description: Virtual creature game with 250 evolutions; no radio scanning or attacks
# Author: tiaocunha
# Version: 0.1.0
# Category: Games
# Dependency: Python 3, python3-ctypes and PAGERCTL (MIT)

PAYLOAD_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DATA_DIR="${HACKOMON_DATA_DIR:-/mmc/root/hackomon}"
LOG_FILE="/tmp/hackomon.log"

export PATH="/mmc/usr/bin:/mmc/usr/sbin:$PATH"
export LD_LIBRARY_PATH="/mmc/usr/lib:/mmc/lib:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$PAYLOAD_DIR:${PYTHONPATH:-}"

PYTHON_BIN="$(command -v python3 2>/dev/null)"
if [ -z "$PYTHON_BIN" ]; then
    LOG "Hackomon: Python 3 nao encontrado."
    LOG "Instale python3 e python3-ctypes no MMC."
    WAIT_FOR_INPUT >/dev/null 2>&1
    exit 2
fi

if ! "$PYTHON_BIN" -c "import ctypes" >/dev/null 2>&1; then
    LOG "Hackomon: modulo python3-ctypes nao encontrado."
    LOG "Instale python3-ctypes no MMC."
    WAIT_FOR_INPUT >/dev/null 2>&1
    exit 2
fi

PAGERCTL_LIB=""
for candidate in \
    "$PAYLOAD_DIR/lib/libpagerctl.so" \
    "/root/payloads/user/utilities/PAGERCTL/libpagerctl.so" \
    "/mmc/root/payloads/user/utilities/PAGERCTL/libpagerctl.so"; do
    if [ -f "$candidate" ]; then
        PAGERCTL_LIB="$candidate"
        break
    fi
done

if [ -z "$PAGERCTL_LIB" ]; then
    LOG "Hackomon: libpagerctl.so nao encontrada."
    LOG "Instale o payload PAGERCTL antes de iniciar."
    WAIT_FOR_INPUT >/dev/null 2>&1
    exit 2
fi

restore_stock_ui() {
    /etc/init.d/pineapplepager start >/dev/null 2>&1
}

trap restore_stock_ui EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

mkdir -p "$DATA_DIR" 2>/dev/null
SPINNER_ID="$(START_SPINNER "Abrindo Hackomon...")"
/etc/init.d/pineapplepager stop >/dev/null 2>&1
STOP_SPINNER "$SPINNER_ID" >/dev/null 2>&1

"$PYTHON_BIN" "$PAYLOAD_DIR/run_hackomon.py" \
    --pagerctl-lib "$PAGERCTL_LIB" \
    --data-dir "$DATA_DIR" >"$LOG_FILE" 2>&1
EXIT_CODE=$?

if [ "$EXIT_CODE" -ne 0 ] && [ "$EXIT_CODE" -ne 130 ]; then
    LOG "Hackomon encerrou com codigo $EXIT_CODE."
    LOG "Log: $LOG_FILE"
    WAIT_FOR_INPUT >/dev/null 2>&1
fi

exit "$EXIT_CODE"

