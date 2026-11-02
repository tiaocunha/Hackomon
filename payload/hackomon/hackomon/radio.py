"""Optional installed Linux tools and a local GPSD receiver; no package installs."""

import datetime
import json
import math
import re
import socket
import subprocess
import time

from .exploration import MAC


def command(args, timeout=15):
    try:
        result = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, errors="replace", timeout=timeout)
    except FileNotFoundError:
        raise RuntimeError("Dependencia ausente: %s" % args[0]) from None
    except subprocess.TimeoutExpired:
        raise RuntimeError("Tempo esgotado: %s" % args[0]) from None
    if result.returncode:
        raise RuntimeError("%s falhou; confira interface e permissao" % args[0])
    return result.stdout


def gps_fix(now=None):
    now = time.time() if now is None else now
    try:
        with socket.create_connection(("127.0.0.1", 2947), timeout=2) as connection:
            connection.settimeout(2)
            connection.sendall(b'?WATCH={"enable":true,"json":true};\n')
            with connection.makefile("rb") as lines:
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    line = lines.readline(10241)
                    if not line or len(line) > 10240:
                        break
                    try:
                        fix = parse_gps_report(json.loads(line), now)
                    except (ValueError, TypeError, KeyError, OverflowError):
                        continue
                    if fix is not None:
                        return fix
    except OSError:
        pass
    raise RuntimeError("GPS sem fix recente; confira gpsd e o GPS externo")


def parse_gps_report(report, now):
    if report.get("class") != "TPV" or report.get("mode", 0) < 2:
        return None
    stamp = datetime.datetime.fromisoformat(report["time"].replace("Z", "+00:00"))
    if stamp.tzinfo is None or abs(now - stamp.timestamp()) > 15:
        return None
    lat, lon = float(report["lat"]), float(report["lon"])
    accuracy = max(float(report["epx"]), float(report["epy"]))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 0 < accuracy <= 100):
        return None
    altitude = float(report.get("altMSL", 0))
    if not math.isfinite(altitude):
        return None
    return dict(lat=lat, lon=lon, accuracy=accuracy, altitude=altitude)


def wifi_observations(text, now):
    results = []
    current = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("BSS "):
            address = line[4:21]
            current = None
            if MAC.fullmatch(address):
                current = dict(type="WIFI", mac=address, name="", auth="[OPEN]",
                               timestamp=now, channel=0, frequency=0)
                results.append(current)
        elif current is not None:
            if line.startswith("SSID:"):
                current["name"] = line[5:].strip()
            elif line.startswith("freq:"):
                current["frequency"] = int(line.split()[1])
            elif line.startswith("signal:"):
                current["rssi"] = int(float(line.split()[1]))
            elif "DS Parameter set: channel " in line:
                current["channel"] = int(line.rsplit(" ", 1)[1])
            elif line.startswith("RSN:"):
                current["auth"] = "[WPA2]"
            elif "Authentication suites:" in line and "SAE" in line:
                current["auth"] = "[WPA3]"
            elif line.startswith("WPA:"):
                current["auth"] = "[WPA]"
            elif line.startswith("capability:") and "Privacy" in line:
                current["auth"] = "[PRIVACY]"
    return [item for item in results if "rssi" in item][:500]


def ble_observations(text, now):
    devices = {}
    ansi = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
    for line in ansi.sub("", text).splitlines():
        match = re.search(r"Device ((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}) (.*)", line)
        if not match:
            continue
        address, detail = match.groups()
        item = devices.setdefault(address, dict(type="BLE", mac=address, name="", auth="[BLE]",
                                                timestamp=now, channel=0, frequency=0))
        if detail.startswith("RSSI: "):
            raw = detail[6:].split()[0]
            try:
                number = int(raw, 16) if raw.startswith("0x") else int(raw)
                if number > 127:
                    number -= 65536 if number > 255 else 256
                item["rssi"] = number
            except ValueError:
                continue
        elif detail.startswith(("Name: ", "Alias: ")):
            item["name"] = detail.split(": ", 1)[1]
        elif "[NEW]" in line:
            item["name"] = detail
    return [item for item in devices.values() if "rssi" in item][:500]


def discover(kind, interface):
    first_fix = gps_fix()
    if kind == "WIFI":
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", interface):
            raise RuntimeError("Defina wifi_interface no config.json")
        text = command(["iw", "dev", interface, "scan", "passive"], timeout=20)
        now = int(time.time())
        observations = wifi_observations(text, now)
    elif kind == "BLE":
        # A bounded LE discovery, without pairing or connecting to devices.
        text = command(["bluetoothctl", "--timeout", "8", "scan", "le"], timeout=12)
        now = int(time.time())
        observations = ble_observations(text, now)
    else:
        raise ValueError("unsupported radio")
    fix = gps_fix()
    lat_scale = math.cos(math.radians(fix["lat"]))
    distance = 111320 * math.hypot(fix["lat"] - first_fix["lat"],
                                  (fix["lon"] - first_fix["lon"]) * lat_scale)
    if distance > 30:
        raise RuntimeError("Movimento acima de 30m; repita parado para registrar o GPS")
    for item in observations:
        item.update(fix)
        if item["type"] == "WIFI" and not item["channel"]:
            freq = item["frequency"]
            if freq == 2484:
                item["channel"] = 14
            elif 2412 <= freq <= 2472:
                item["channel"] = (freq - 2407) // 5
            elif 5000 <= freq < 5925:
                item["channel"] = (freq - 5000) // 5
            elif freq == 5935:
                item["channel"] = 2
            elif 5955 <= freq <= 7115:
                item["channel"] = (freq - 5950) // 5
    return observations
