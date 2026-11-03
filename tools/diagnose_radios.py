#!/usr/bin/env python3
"""Read-only support report. No scans, identifiers, account keys or GPS coordinates."""

import datetime
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import time
import traceback
import sys


def run(args):
    try:
        result = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, errors="replace", timeout=4)
        return result.returncode, result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return -1, ""


def gps_status():
    try:
        with socket.create_connection(("127.0.0.1", 2947), timeout=2) as connection:
            connection.settimeout(2)
            connection.sendall(b'?WATCH={"enable":true,"json":true};\n')
            with connection.makefile("rb") as stream:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    line = stream.readline(10241)
                    if not line or len(line) > 10240:
                        break
                    try:
                        report = json.loads(line)
                        if report.get("class") != "TPV":
                            continue
                        stamp = datetime.datetime.fromisoformat(report["time"].replace("Z", "+00:00"))
                        age = int(abs(time.time() - stamp.timestamp()))
                        return "modo=%s idade=%ss epx/epy=%s" % (
                            report.get("mode", "?"), age, "presentes" if "epx" in report and "epy" in report else "ausentes")
                    except (ValueError, KeyError, TypeError, OverflowError):
                        continue
        return "porta acessivel, sem TPV valido na amostra"
    except OSError:
        return "GPSd inacessivel/sem resposta"


def runtime_checks(interfaces):
    lines = ["", "Integracao do app (leitura de cache; sem nova busca):"]
    app = Path("/root/payloads/user/games/hackomon")
    if app.is_dir():
        try:
            sys.path.insert(0, str(app))
            from hackomon import radio, recon
            try:
                values = recon.read_wifi(limit=500)
                lines.append("  Leitor Recon instalado: %s APs aceitos" % len(values))
                if hasattr(recon, "read_bluetooth") and recon.BLUETOOTH_DATABASE.is_file():
                    lines.append("  Leitor Blue5 instalado: %s LE aceitos" % len(recon.read_bluetooth()))
            except Exception as error:
                frames = traceback.extract_tb(error.__traceback__)
                lines.append("  Leitor Recon: %s em %s" % (type(error).__name__, ";".join("%s:%s:%s" % (Path(f.filename).name, f.lineno, f.name) for f in frames[-4:])))
            for item in [v for v in interfaces if v["type"] == "managed"][:2]:
                code, cached = run(["iw", "dev", item["name"], "scan", "dump"])
                lines.append("  Cache iw %s: codigo=%s BSS=%s" % (item["name"], code, len(re.findall(r"(?m)^BSS ", cached))))
                if code == 0:
                    frequencies = re.findall(r"(?m)^\s*freq:\s*([0-9.]+)\s*$", cached)
                    lines.append("  Formato de frequencia iw: decimal=%s inteiro=%s" % (sum("." in v for v in frequencies), sum("." not in v for v in frequencies)))
                    try:
                        lines.append("  Parser iw: %s APs aceitos" % len(radio.wifi_observations(cached, time.time())))
                    except Exception as error:
                        frames = traceback.extract_tb(error.__traceback__)
                        lines.append("  Parser iw: %s em %s" % (type(error).__name__, ";".join("%s:%s:%s" % (Path(f.filename).name, f.lineno, f.name) for f in frames[-4:])))
        except Exception as error:
            lines.append("  App nao consultado: %s" % type(error).__name__)
    lines.append("  HCI no kernel: " + ",".join(p.name for p in Path("/sys/class/bluetooth").glob("hci*")))
    for name in ("bluetoothd", "blue5", "dbus-daemon", "pineapd", "pineapple"):
        code, text = run(["pidof", name])
        lines.append("  Processo %s ativo=%s" % (name, code == 0 and bool(text.strip())))
    for name in ("btmgmt", "hciconfig"):
        lines.append("  Ferramenta %s=%s" % (name, bool(shutil.which(name))))
    lines.append("  Servicos disponiveis: " + ",".join(p.name for p in Path("/etc/init.d").glob("*") if re.search(r"blue|bluetooth|dbus|gps|pineap", p.name)))
    try:
        import sqlite3
        for path in sorted(Path("/root/recon").glob("*.db"))[:12]:
            connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.2)
            try:
                connection.execute("PRAGMA query_only=ON")
                tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'") if re.fullmatch(r"[A-Za-z0-9_]+", row[0])]
                lines.append("  Banco %s: tabelas=%s" % (path.name, ",".join(tables)))
                for table in [t for t in tables if re.search(r"blue|^bt_|ble", t, re.I)]:
                    fields = [row[1] for row in connection.execute('PRAGMA table_info("' + table + '")')]
                    lines.append("    %s: campos=%s" % (table, ",".join(fields)))
                    if table == "bt_device" and {"last_seen", "transports", "le_random", "mac"}.issubset(fields):
                        count, stamp = connection.execute("SELECT count(*),max(last_seen) FROM bt_device").fetchone()
                        age = int(time.time() - float(stamp)) if stamp is not None else "sem aparelhos"
                        lines.append("    BT total=%s idade_ultimo_seg=%s" % (count, age))
                        rows = connection.execute("SELECT typeof(transports),transports,le_random,typeof(mac),length(mac),count(*) FROM bt_device GROUP BY 1,2,3,4,5 LIMIT 16")
                        for kind, transport, random, mac_type, mac_length, count in rows:
                            transport = transport if isinstance(transport, (int, float)) or str(transport).lower() in ("le", "bredr", "le,bredr", "bredr,le") else "texto/valor omitido"
                            lines.append("    BT tipos transporte=%s valor=%s randomLE=%s mac=%s tamanho=%s count=%s" % (kind, transport, random, mac_type, mac_length, count))
                if "ssid" in tables:
                    rows = connection.execute("SELECT typeof(bssid),length(bssid),typeof(freq),typeof(channel),typeof(signal),typeof(time),count(*) FROM ssid WHERE type=8 GROUP BY 1,2,3,4,5,6 LIMIT 10")
                    for row in rows:
                        lines.append("    Tipos BSSID/tamanho/freq/canal/sinal/tempo/contagem: " + "/".join(str(v) for v in row))
            finally:
                connection.close()
    except Exception as error:
        lines.append("  Esquemas adicionais: %s" % type(error).__name__)
    return lines


def report(db_path=Path("/root/recon/recon.db"), state_root=Path("/mmc/root/hackomon")):
    lines = ["HACKOMON - DIAGNOSTICO DE RADIOS", "Sem buscas, pareamentos, mudancas ou envios a servicos.", ""]
    lines.append("Ferramentas: " + ", ".join("%s=%s" % (name, "sim" if shutil.which(name) else "nao")
                 for name in ("iw", "ip", "bluetoothctl", "gpsd", "sqlite3")))
    code, text = run(["iw", "dev"])
    lines.append("Wi-Fi / iw dev: codigo %s" % code)
    interfaces = []
    current = None
    for line in text.splitlines():
        match = re.match(r"\s*Interface ([A-Za-z0-9_.-]{1,32})\s*$", line)
        if match:
            current = {"name": match.group(1), "type": "?"}
            interfaces.append(current)
        elif current is not None and re.match(r"\s*type ", line):
            current["type"] = line.strip()[5:][:30]
    for item in interfaces:
        suffix = ""
        if item["type"] == "managed":
            status, link = run(["iw", "dev", item["name"], "link"])
            suffix = " conectada=%s codigo=%s" % ("nao" if "Not connected." in link else "sim" if "Connected to " in link else "desconhecido", status)
        lines.append("  interface=%s tipo=%s%s" % (item["name"], item["type"], suffix))
    if not interfaces:
        lines.append("  Nenhuma interface reconhecida")
    lines.append("Recon: banco presente=%s" % db_path.is_file())
    if db_path.is_file():
        try:
            import sqlite3
            connection = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.2)
            try:
                connection.execute("PRAGMA query_only=ON")
                deadline = time.monotonic() + 2
                connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
                fields = {row[1] for row in connection.execute("PRAGMA table_info(ssid)")}
                lines.append("  Campos ssid: " + ",".join(sorted(fields)))
                if {"time", "type"}.issubset(fields):
                    count, stamp = connection.execute("SELECT count(*), max(time) FROM ssid WHERE type=8").fetchone()
                    recent = connection.execute("SELECT count(*) FROM ssid WHERE type=8 AND time>=? AND time<=?", (time.time() - 30, time.time())).fetchone()[0]
                    age = int(time.time() - float(stamp)) if stamp is not None else "sem APs"
                    lines.append("  APs totais=%s recentes30s=%s idade_ultimo_seg=%s" % (count, recent, age))
            finally:
                connection.close()
        except ImportError:
            lines.append("  Modulo Python sqlite3 ausente")
        except Exception as error:
            lines.append("  Banco nao consultado: %s" % type(error).__name__)
    code, text = run(["bluetoothctl", "show"])
    lines.append("Bluetooth / show: codigo %s controlador=%s" % (code, "sim" if re.search(r"(?m)^\s*Controller\s", text) else "nao"))
    for key in ("Powered", "Discovering", "Discoverable", "Pairable"):
        match = re.search(r"(?m)^\s*" + key + r":\s*(yes|no)\s*$", text)
        lines.append("  %s=%s" % (key, match.group(1) if match else "desconhecido"))
    code, text = run(["bluetoothctl", "devices"])
    lines.append("  Dispositivos em cache=%s (nao comprova descoberta atual)" % len(re.findall(r"(?m)^Device ", text)))
    lines.append("GPS: " + gps_status())
    summary = state_root / "expeditions/current.json"
    if summary.is_file() and summary.stat().st_size <= 16384:
        try:
            value = json.loads(summary.read_text(encoding="utf-8"))
            lines.append("Expedicao: estado=%s wifi=%s ble=%s" % (value.get("status"), value.get("wifi"), value.get("ble")))
            for key in ("wifi", "ble"):
                message = str(value.get("radios", {}).get(key, {}).get("message", "sem estado registrado"))
                message = re.sub(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", "[endereco omitido]", message)
                lines.append("  %s: %s" % (key, "".join(c for c in message if c.isprintable())[:180]))
        except (ValueError, OSError, TypeError, AttributeError):
            lines.append("Expedicao: resumo nao consultado")
    lines.extend(runtime_checks(interfaces))
    lines.append("Fim. Nao inclui nomes de redes, MACs, coordenadas, config ou senhas.")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(report(), end="")
