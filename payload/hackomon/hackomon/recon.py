"""Read recent AP observations from the stock Pager database, without writes."""

import math
from pathlib import Path
import re
import time

from .exploration import MAC


DATABASE = Path("/root/recon/recon.db")
BLUETOOTH_DATABASE = Path("/root/recon/blue5.db")
FIELDS = {"type", "bssid", "ssid", "freq", "channel", "signal", "time"}


class NetworkScan(list):
    def __init__(self, values=(), source="iw"):
        super().__init__(values)
        self.source = source


def decode_address(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        value = bytes(value)
        value = value.hex() if len(value) == 6 else value.decode("ascii")
    value = str(value).upper()
    if re.fullmatch(r"[0-9A-F]{12}", value):
        value = ":".join(value[i:i + 2] for i in range(0, 12, 2))
    if not MAC.fullmatch(value):
        raise ValueError("invalid discovery address encoding")
    return value


def read_wifi(path=DATABASE, now=None, limit=100):
    try:
        import sqlite3
    except ImportError:
        raise RuntimeError("Recon: falta python3-sqlite3") from None
    path = Path(path)
    now = time.time() if now is None else now
    if not path.is_file():
        raise RuntimeError("Recon: banco nativo indisponivel")
    deadline = time.monotonic() + 2
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.2)
        try:
            connection.execute("PRAGMA query_only=ON")
            connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            fields = {row[1] for row in connection.execute("PRAGMA table_info(ssid)")}
            if not FIELDS.issubset(fields):
                raise RuntimeError("Recon: formato do firmware nao reconhecido")
            rows = connection.execute(
                "SELECT bssid, ssid, freq, channel, signal, time FROM ssid "
                "WHERE type=8 AND time>=? AND time<=? ORDER BY time DESC LIMIT ?",
                (now - 30, now + 1, min(500, max(1, int(limit)))))
            values = {}
            for address, name, frequency, channel, signal, stamp in rows:
                try:
                    address = decode_address(address)
                    if int(address[:2], 16) & 1 or address == "00:00:00:00:00:00":
                        continue
                    stamp, signal = float(stamp), float(signal)
                    frequency, channel = int(frequency), int(channel)
                    if not math.isfinite(signal) or not -127 <= signal <= 20 or not 0 <= now - stamp <= 30:
                        continue
                    if not (2400 <= frequency <= 7125) or not 0 <= channel <= 233:
                        continue
                    if address in values:
                        continue
                    if isinstance(name, bytes):
                        name = name.decode("utf-8", "replace")
                    values[address] = dict(type="WIFI", mac=address, name=str(name or "")[:128],
                                           auth="[UNKNOWN]", frequency=frequency, channel=channel,
                                           rssi=int(signal), timestamp=stamp, time_source="hak5_recon",
                                           security={})
                except (ValueError, TypeError, OverflowError):
                    continue
            return NetworkScan(sorted(values.values(), key=lambda item: item["rssi"], reverse=True), "Recon")
        finally:
            connection.close()
    except sqlite3.Error:
        raise RuntimeError("Recon: banco ocupado, indisponivel ou incompativel") from None


def read_bluetooth(path=BLUETOOTH_DATABASE, now=None, limit=500):
    """Consume recent LE records from the Pager 2.0 Blue5 collector."""
    try:
        import sqlite3
    except ImportError:
        raise RuntimeError("Blue5: falta python3-sqlite3") from None
    path = Path(path)
    if not path.is_file():
        raise RuntimeError("Blue5: banco nativo indisponivel")
    now = time.time() if now is None else now
    deadline = time.monotonic() + 2
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.2)
        try:
            connection.execute("PRAGMA query_only=ON")
            connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            fields = {row[1] for row in connection.execute("PRAGMA table_info(bt_device)")}
            if not {"mac", "name", "rssi", "last_seen", "transports"}.issubset(fields):
                raise RuntimeError("Blue5: formato do firmware nao reconhecido")
            rows = connection.execute(
                "SELECT mac, name, rssi, last_seen, transports FROM bt_device "
                "WHERE last_seen>=? AND last_seen<=? ORDER BY last_seen DESC LIMIT ?",
                (now - 30, now + 1, min(500, max(1, int(limit)))))
            values = {}
            for address, name, signal, stamp, transport in rows:
                try:
                    # Blue5 2.0 uses LE=1, BR/EDR=2 and both=3. Unknown bits
                    # and classic-only rows never become BLE map discoveries.
                    if type(transport) is not int or transport not in (1, 3):
                        continue
                    address = decode_address(address)
                    signal, stamp = float(signal), float(stamp)
                    if address in ("00:00:00:00:00:00", "FF:FF:FF:FF:FF:FF") or address in values:
                        continue
                    if not math.isfinite(signal) or not -127 <= signal <= 0 or not 0 <= now - stamp <= 30:
                        continue
                    if isinstance(name, bytes):
                        name = name.decode("utf-8", "replace")
                    values[address] = dict(type="BLE", mac=address, name=str(name or "")[:128],
                                           auth="[BLE]", rssi=int(signal), timestamp=stamp,
                                           frequency=0, channel=0, time_source="hak5_blue5")
                except (ValueError, TypeError, OverflowError):
                    continue
            return NetworkScan(sorted(values.values(), key=lambda item: item["rssi"], reverse=True), "Blue5")
        finally:
            connection.close()
    except sqlite3.Error:
        raise RuntimeError("Blue5: banco ocupado, indisponivel ou incompativel") from None
