#!/bin/bash
# Title: Hackomon
# Description: Virtual creatures, GPS discoveries, WDGWars sync and scoped office lab
# Author: tiaocunha
# Version: 0.10.3
# Category: Games
# Dependency: Python 3, python3-ctypes and PAGERCTL (MIT)

# Hak5 executes payloads from /tmp and provides the real location here.
# BASH_SOURCE is only a fallback for direct/source invocation outside that runner.
PAYLOAD_DIR="$(CDPATH= cd -- "${_PAYLOAD_HOME:-$(dirname -- "${BASH_SOURCE[0]}")}" 2>/dev/null && pwd)"
if ! command -v LOG >/dev/null 2>&1; then
    LOG() { printf '%s\n' "$*"; }
fi
if [ -z "$PAYLOAD_DIR" ] || [ ! -f "$PAYLOAD_DIR/run_hackomon.py" ]; then
    LOG "Hackomon: pasta instalada nao encontrada."
    LOG "Execute INSTALAR.cmd novamente para reparar a instalacao."
    exit 2
fi
DATA_DIR="${HACKOMON_DATA_DIR:-/mmc/root/hackomon}"
LOG_FILE="${HACKOMON_LOG_FILE:-/tmp/hackomon.log}"

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
    LOG "Execute INSTALAR.cmd novamente; ele inclui a biblioteca de tela."
    LOG "Pasta verificada: $PAYLOAD_DIR/lib"
    WAIT_FOR_INPUT >/dev/null 2>&1
    exit 2
fi

if [ "${HACKOMON_CHECK_INSTALL:-0}" = "1" ]; then
    LOG "Hackomon: verificando a instalacao em $PAYLOAD_DIR"
    "$PYTHON_BIN" "$PAYLOAD_DIR/run_hackomon.py" --doctor --pagerctl-lib "$PAGERCTL_LIB"
    exit $?
fi

mkdir -p "$DATA_DIR" 2>/dev/null
SPINNER_ID="$(START_SPINNER "Abrindo Hackomon...")"
STOP_SPINNER "$SPINNER_ID" >/dev/null 2>&1

# Stopping pineapplepager also stops PineAP on stock 2.0.0. Suspend only its
# visual process instead; a separate Python guard restores it even if the app dies.
GUARD_PID=""
stop_app() {
    trap '' INT TERM HUP
    if [ -n "$GUARD_PID" ]; then
        kill -TERM "$GUARD_PID" 2>/dev/null
        wait "$GUARD_PID" 2>/dev/null
    fi
    exit "$1"
}
trap 'stop_app 130' INT
trap 'stop_app 143' TERM
trap 'stop_app 129' HUP

"$PYTHON_BIN" -m hackomon.stock_ui -- "$PYTHON_BIN" "$PAYLOAD_DIR/run_hackomon.py" \
    --pagerctl-lib "$PAGERCTL_LIB" \
    --data-dir "$DATA_DIR" >"$LOG_FILE" 2>&1 &
GUARD_PID=$!
wait "$GUARD_PID"
EXIT_CODE=$?
GUARD_PID=""

if [ "$EXIT_CODE" -ne 0 ] && [ "$EXIT_CODE" -ne 130 ]; then
    LOG "Hackomon encerrou com codigo $EXIT_CODE."
    LOG "Log: $LOG_FILE"
    WAIT_FOR_INPUT >/dev/null 2>&1
fi

exit "$EXIT_CODE"

