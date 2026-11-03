"""Read-only installation checks. Never initialize display or scan radios."""

import importlib
import shutil
import socket


MODULES = ("ctypes", "ssl", "urllib.request", "json", "threading", "subprocess", "hashlib")
SYMBOLS = ("pager_init", "pager_cleanup", "pager_set_rotation", "pager_clear", "pager_flip",
           "pager_delay", "pager_fill_rect", "pager_draw_text", "pager_draw_text_centered",
           "pager_text_width", "pager_poll_input")


def check(library=None):
    rows = []
    required_ok = True
    for name in MODULES:
        try:
            importlib.import_module(name)
            rows.append(("OK", "Python: %s" % name))
        except ImportError:
            required_ok = False
            rows.append(("FALTA", "Python: %s" % name))
    try:
        import ctypes
        from .pager_backend import find_library
        lib = ctypes.CDLL(find_library(library))
        missing = [name for name in SYMBOLS if not hasattr(lib, name)]
        if missing:
            raise ValueError("API incompleta: %s" % ", ".join(missing))
        rows.append(("OK", "libpagerctl carregada; API presente (tela nao inicializada)"))
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        required_ok = False
        rows.append(("FALTA", "Tela: %s" % error))
    for command, purpose in (("iw", "descoberta Wi-Fi"), ("ip", "interfaces Wi-Fi"),
                             ("bluetoothctl", "descoberta BLE"), ("sdptool", "inventario Bluetooth classico"),
                             ("tcpdump", "captura selecionada no laboratorio"), ("aircrack-ng", "teste local de dicionario")):
        rows.append(("OK" if shutil.which(command) else "OPCIONAL AUSENTE", "%s: %s" % (purpose, command)))
    try:
        # A connect proves only a listening service, not GPS fix/accuracy.
        with socket.create_connection(("127.0.0.1", 2947), timeout=1):
            rows.append(("OK", "Porta GPSd local acessivel; confirme fix em Settings > GPS"))
    except OSError:
        rows.append(("OPCIONAL AUSENTE", "GPSd local nao acessivel na porta 2947"))
    rows.append(("INFO", "Nenhuma busca, captura, pareamento ou envio foi executado."))
    rows.append(("INFO", "Presenca dos comandos nao comprova driver, GPS, TLS ou compatibilidade no firmware."))
    return required_ok, rows


def main(library=None):
    ok, rows = check(library)
    for status, description in rows:
        print("[%s] %s" % (status, description))
    return 0 if ok else 2
