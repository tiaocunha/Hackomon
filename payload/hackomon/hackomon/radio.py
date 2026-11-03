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
        detail = (result.stderr or "") + (result.stdout or "")
        reason = "falhou; confira interface e permissao"
        for marker, message in (("Network is down", "interface desligada"),
                                ("Device or resource busy", "radio ocupado"),
                                ("Operation not supported", "operacao nao suportada"),
                                ("No such device", "interface inexistente"),
                                ("NotReady", "controlador nao esta pronto")):
            if marker in detail:
                reason = message
                break
        raise RuntimeError("%s: %s" % (args[0], reason))
    return result.stdout


def bluetooth_ready():
    text = command(["bluetoothctl", "show"], timeout=4)
    if "No default controller" in text or not re.search(r"(?m)^\s*Controller\s", text):
        raise RuntimeError("Bluetooth: nenhum controlador disponivel")
    if re.search(r"(?m)^\s*Powered:\s*no\s*$", text):
        raise RuntimeError("Bluetooth desligado; ative no Pager")
    if not re.search(r"(?m)^\s*Powered:\s*yes\s*$", text):
        raise RuntimeError("Bluetooth: estado do controlador desconhecido")


def bluetooth_scan_error(line):
    if "NotReady" in line:
        return "Bluetooth nao pronto; confira se esta ligado"
    if "No default controller" in line:
        return "Bluetooth: nenhum controlador disponivel"
    if "Failed to start discovery" in line or "Invalid command" in line or "Invalid argument" in line:
        return "BLE: busca recusada ou scan le nao suportado"
    return ""


GPS_MESSAGES = {
    "valid": "posicao recente", "no_receiver": "GPSd sem receptor USB",
    "unavailable": "GPSd indisponivel", "no_reports": "aguardando dados do receptor",
    "no_fix": "receptor sem fix", "missing_time": "horario GPS indisponivel",
    "invalid_time": "horario GPS invalido", "stale_time": "horario GPS/Pager divergente",
    "missing_position": "posicao incompleta", "bad_position": "posicao invalida",
    "missing_accuracy": "precisao indisponivel", "bad_accuracy": "precisao insuficiente (>100m)",
    "bad_altitude": "altitude invalida", "invalid_report": "dados GPS invalidos",
}


def _gps_number(value):
    try:
        return float(value) if type(value) in (int, float) and math.isfinite(value) else None
    except OverflowError:
        return None


def sanitize_gps_health(value):
    value = value if isinstance(value, dict) else {}
    code = value.get("code", "invalid_report")
    code = code if isinstance(code, str) and code in GPS_MESSAGES else "invalid_report"
    health = dict(code=code, message=GPS_MESSAGES[code])
    for key in ("mode", "time_offset_s", "accuracy_m", "receiver_count"):
        number = _gps_number(value.get(key))
        if number is not None:
            health[key] = number
    if value.get("accuracy_source") in ("epx_epy", "eph", "combined"):
        health["accuracy_source"] = value["accuracy_source"]
    return health


class GPSFixError(RuntimeError):
    def __init__(self, health):
        self.health = sanitize_gps_health(health)
        super().__init__(self.health["message"])


def evaluate_gps_report(report, now):
    health = {}
    def reject(code):
        return None, sanitize_gps_health(dict(health, code=code))
    if not isinstance(report, dict) or report.get("class") != "TPV":
        return reject("invalid_report")
    mode = _gps_number(report.get("mode"))
    if mode is not None:
        health["mode"] = mode
    if mode not in (2, 3):
        return reject("no_fix")
    if not isinstance(report.get("time"), str):
        return reject("missing_time")
    try:
        stamp = datetime.datetime.fromisoformat(report["time"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return reject("invalid_time")
        delta = stamp.timestamp() - now
    except (ValueError, TypeError, OverflowError, OSError):
        return reject("invalid_time")
    health["time_offset_s"] = round(delta, 2)
    if abs(delta) > 15:
        return reject("stale_time")
    if "lat" not in report or "lon" not in report:
        return reject("missing_position")
    lat, lon = _gps_number(report["lat"]), _gps_number(report["lon"])
    if lat is None or lon is None or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return reject("bad_position")
    # GPSd may supply horizontal error (eph) instead of both axis errors.
    keys = [key for key in ("epx", "epy", "eph") if key in report]
    errors = [_gps_number(report[key]) for key in keys]
    if not ("eph" in report or "epx" in report and "epy" in report):
        return reject("missing_accuracy")
    if any(value is None or value <= 0 for value in errors):
        return reject("bad_accuracy")
    accuracy = max(errors)
    health["accuracy_m"] = accuracy
    health["accuracy_source"] = "combined" if "eph" in keys and len(keys) > 1 else "eph" if "eph" in keys else "epx_epy"
    if accuracy > 100:
        return reject("bad_accuracy")
    altitude = _gps_number(report.get("altMSL", 0))
    if altitude is None:
        return reject("bad_altitude")
    return dict(lat=lat, lon=lon, accuracy=accuracy, altitude=altitude,
                fix_time=stamp.timestamp()), sanitize_gps_health(dict(health, code="valid"))


class GPSReports:
    """Join optional fields only within exactly the same device and GPS epoch."""
    def __init__(self):
        self.epochs = {}
        self.health = sanitize_gps_health(dict(code="no_reports"))

    def consume(self, report, now):
        if not isinstance(report, dict):
            return None
        if report.get("class") == "DEVICES" and isinstance(report.get("devices"), list):
            if not report["devices"]:
                self.epochs.clear()
                self.health = sanitize_gps_health(dict(code="no_receiver", receiver_count=0))
            return None
        if report.get("class") != "TPV":
            return None
        if report.get("mode") not in (2, 3):
            self.epochs.clear()
        elif (isinstance(report.get("time"), str) and isinstance(report.get("device"), str)
              and report["device"]):
            key = (report["device"], report["time"])
            merged = dict(self.epochs.get(key, {}), **report)
            if key not in self.epochs and len(self.epochs) >= 8:
                self.epochs.pop(next(iter(self.epochs)))
            self.epochs[key] = merged
            report = merged
        fix, self.health = evaluate_gps_report(report, now)
        return fix


def gps_fix(now=None):
    reports = GPSReports()
    connected = False
    try:
        with socket.create_connection(("127.0.0.1", 2947), timeout=2) as connection:
            connected = True
            connection.settimeout(2)
            connection.sendall(b'?WATCH={"enable":true,"json":true};\n')
            deadline, buffer = time.monotonic() + 4, b""
            while time.monotonic() < deadline:
                try:
                    block = connection.recv(8192)
                except socket.timeout:
                    continue
                if not block:
                    break
                buffer += block
                if len(buffer) > 20480:
                    buffer = b""
                    continue
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if len(line) > 10240:
                        continue
                    try:
                        fix = reports.consume(json.loads(line), time.time() if now is None else now)
                    except (ValueError, TypeError, KeyError, OverflowError):
                        continue
                    if fix is not None:
                        fix["gps_health"] = reports.health
                        return fix
    except OSError:
        if not connected:
            reports.health = dict(code="unavailable")
    raise GPSFixError(reports.health)


def parse_gps_report(report, now):
    return evaluate_gps_report(report, now)[0]


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
                match = re.match(r"freq:\s*(\d+(?:\.\d+)?)(?:\s|$)", line)
                if match:
                    frequency = float(match.group(1))
                    if math.isfinite(frequency) and frequency.is_integer() and 2400 <= frequency <= 7125:
                        current["frequency"] = int(frequency)
            elif line.startswith("signal:"):
                match = re.match(r"signal:\s*(-?\d+(?:\.\d+)?)(?:\s|$)", line)
                if match:
                    signal = float(match.group(1))
                    if math.isfinite(signal) and -127 <= signal <= 0:
                        current["rssi"] = int(signal)
            elif line.startswith("last seen:"):
                age = re.search(r"last seen:\s+(\d+) ms ago", line)
                if age:
                    current["timestamp"] = int(now - int(age.group(1)) / 1000)
                    current["time_source"] = "iw_age"
            elif "DS Parameter set: channel " in line:
                match = re.search(r"DS Parameter set: channel (\d+)", line)
                if match and 0 <= int(match.group(1)) <= 233:
                    current["channel"] = int(match.group(1))
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
        bluetooth_ready()
        text = command(["bluetoothctl", "--timeout", "8", "scan", "le"], timeout=12)
        error = bluetooth_scan_error(text)
        if error:
            raise RuntimeError(error)
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
