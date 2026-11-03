"""Read-only installation checks. Never initialize display or scan radios."""

import importlib
import shutil


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
    from . import recon
    for database, reader, label in ((recon.DATABASE, recon.read_wifi, "Recon Wi-Fi"),
                                    (recon.BLUETOOTH_DATABASE, recon.read_bluetooth, "Blue5 LE")):
        if database.is_file():
            try:
                rows.append(("INFO", "%s: %d observacoes recentes lidas, sem nova busca" % (label, len(reader()))))
            except RuntimeError as error:
                rows.append(("OPCIONAL INDISPONIVEL", str(error)))
    rows.append(gps_check())
    rows.append(("INFO", "Nenhuma busca, captura, pareamento ou envio foi executado."))
    rows.append(("INFO", "Presenca dos comandos nao comprova driver, GPS, TLS ou compatibilidade no firmware."))
    return required_ok, rows


def gps_check():
    """Use the installed acceptance rules; never include coordinates or raw errors."""
    from . import radio
    try:
        fix = radio.gps_fix()
        health = radio.sanitize_gps_health(fix.get("gps_health", dict(code="valid")))
    except radio.GPSFixError as error:
        health = radio.sanitize_gps_health(error.health)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError):
        health = radio.sanitize_gps_health(dict(code="unavailable"))
    message = "GPS: " + health["message"]
    if "accuracy_m" in health:
        message += " | erro %.1fm" % health["accuracy_m"]
    if "time_offset_s" in health:
        message += " | GPS/Pager %+.2fs" % health["time_offset_s"]
    return "OK" if health["code"] == "valid" else "OPCIONAL INDISPONIVEL", message


def main(library=None):
    ok, rows = check(library)
    for status, description in rows:
        print("[%s] %s" % (status, description))
    return 0 if ok else 2
