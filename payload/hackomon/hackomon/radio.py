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
    if not isinstance(report, dict) or not isinstance(report.get("time"), str):
        return None
    if report.get("class") != "TPV" or report.get("mode", 0) < 2:
        return None
    stamp = datetime.datetime.fromisoformat(report["time"].replace("Z", "+00:00"))
    if stamp.tzinfo is None or abs(now - stamp.timestamp()) > 15:
        return None
    lat, lon = float(report["lat"]), float(report["lon"])
    x_error, y_error = float(report["epx"]), float(report["epy"])
    if not (0 < x_error <= 100 and 0 < y_error <= 100):
        return None
    accuracy = max(x_error, y_error)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 0 < accuracy <= 100):
        return None
    altitude = float(report.get("altMSL", 0))
    if not math.isfinite(altitude):
        return None
    return dict(lat=lat, lon=lon, accuracy=accuracy, altitude=altitude,
                fix_time=stamp.timestamp())


def wifi_observations(text, now):
    results = []
    current = None
    rsn_section = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("BSS "):
            rsn_section = False
            address = line[4:21]
            current = None
            if MAC.fullmatch(address):
                current = dict(type="WIFI", mac=address.upper(), name="", auth="[UNKNOWN]",
                               timestamp=now, channel=0, frequency=0,
                               security=dict(capability_seen=False, privacy=False, wpa=False,
                                             rsn=False, wps=False, akm=[], ciphers=[], pmf=None))
                results.append(current)
        elif current is not None:
            if not line.startswith("*"):
                rsn_section = line.startswith("RSN:")
            if line.startswith("SSID:"):
                current["name"] = line[5:].strip()
            elif line.startswith("freq:"):
                current["frequency"] = int(line.split()[1])
            elif line.startswith("signal:"):
                current["rssi"] = int(float(line.split()[1]))
            elif line.startswith("last seen:"):
                age = re.search(r"last seen:\s+(\d+) ms ago", line)
                if age:
                    current["timestamp"] = int(now - int(age.group(1)) / 1000)
                    current["time_source"] = "iw_age"
            elif "DS Parameter set: channel " in line:
                current["channel"] = int(line.rsplit(" ", 1)[1])
            elif line.startswith("RSN:"):
                current["security"]["rsn"] = True
            elif "Authentication suites:" in line:
                current["security"]["akm"].extend(line.split(":", 1)[1].strip().split())
            elif line.startswith("WPA:"):
                current["security"]["wpa"] = True
            elif line.startswith("WPS:"):
                current["security"]["wps"] = True
            elif "Pairwise ciphers:" in line or "Group cipher:" in line:
                current["security"]["ciphers"].extend(line.split(":", 1)[1].strip().split())
            elif line.startswith("capability:"):
                current["security"]["capability_seen"] = True
                current["security"]["privacy"] = "Privacy" in line
            elif line.startswith("* Capabilities:") and rsn_section:
                flags = re.search(r"\(0x([0-9a-fA-F]{4})\)", line)
                if flags:
                    bits = int(flags.group(1), 16)
                    current["security"]["pmf"] = "required" if bits & 0x40 else "optional" if bits & 0x80 else "not_advertised"
    for item in results:
        security = item["security"]
        akm = security["akm"]
        if "SAE" in akm:
            item["auth"] = "[WPA2+WPA3]" if "PSK" in akm else "[WPA3]"
        elif "OWE" in akm:
            item["auth"] = "[OWE]"
        elif security["rsn"]:
            item["auth"] = "[WPA2]"
        elif security["wpa"]:
            item["auth"] = "[WPA]"
        elif security["privacy"]:
            item["auth"] = "[LEGACY/UNKNOWN]"
        elif security["capability_seen"]:
            item["auth"] = "[OPEN]"
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
                signed = re.search(r"\((-?\d+)\)", detail)
                number = int(signed.group(1)) if signed else int(raw, 16) if raw.startswith("0x") else int(raw)
                if not signed and number > 127:
                    number -= 256 if number <= 255 else 65536 if number <= 65535 else 4294967296
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
