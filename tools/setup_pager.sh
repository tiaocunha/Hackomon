#!/bin/sh
# Run explicitly over SSH after extracting/copying the complete setup bundle.
set -eu
SETUP_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export PATH="/mmc/usr/bin:/mmc/usr/sbin:$PATH"
export LD_LIBRARY_PATH="/mmc/usr/lib:/mmc/lib:${LD_LIBRARY_PATH:-}"
INSTALL_DEPS=0
if [ "${1:-}" = "--deps" ]; then
    INSTALL_DEPS=1
    shift
fi
if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import ctypes, ssl, urllib.request, json, threading, subprocess, hashlib' >/dev/null 2>&1; then
    if [ "$INSTALL_DEPS" -ne 1 ]; then
        echo 'Falta Python completo/ctypes/SSL. Repita com --deps para instalar no MMC.'
        exit 2
    fi
    if [ ! -d /mmc ] || [ ! -w /mmc ] || ! command -v opkg >/dev/null 2>&1; then
        echo 'MMC gravavel ou opkg indisponivel; instalacao interrompida.'
        exit 2
    fi
    echo 'Instalando Python 3 + ctypes no MMC pelos feeds configurados no Pager...'
    opkg update
    opkg install -d mmc python3 python3-ctypes
fi
python3 -c 'import ctypes, ssl, urllib.request, json, threading, subprocess, hashlib'
exec python3 "$SETUP_ROOT/tools/setup_pager.py" "$@"
