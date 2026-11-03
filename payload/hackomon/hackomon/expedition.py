"""Offline expedition journal and serial radio sampling with continuous GPS."""

from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time
import uuid

from . import missions, progression, radio, visit, recon
from .exploration import MAC, export_csv, normalize_observation


def distance(first, second):
    lat1, lat2 = math.radians(first["lat"]), math.radians(second["lat"])
    dlat = lat2 - lat1
    dlon = math.radians(second["lon"] - first["lon"])
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 12742000 * math.asin(min(1, math.sqrt(max(0, value))))


def _append(path, payload):
    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "ab") as handle:
        handle.write(payload)


def _atomic(path, value):
    temporary = path.with_suffix(".tmp")
    fd = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(temporary), str(path))


def sensor_status(summary, key, now):
    """Describe recent evidence, without calling an empty scan a broken radio."""
    if summary.get("status") != "running":
        return "pausado", "Coleta parada"
    if key == "gps":
        stamp = summary.get("gps_at")
        if stamp is not None and 0 <= now - stamp <= 15:
            return "ok", "posicao recente (%ds)" % (now - stamp)
        return "waiting", "sem posicao recente"
    value = summary.get("radios", {}).get(key, {})
    if value.get("state") == "disabled":
        return "disabled", "desativado"
    if "at" not in value:
        return "waiting", "verificando"
    if not 0 <= now - value["at"] <= 45:
        return "waiting", "sem leitura recente"
    if not value.get("ok"):
        return "error", value.get("message", "falha de leitura")
    if value.get("count") == 0:
        return "empty", "busca OK; sem anuncios recentes"
    return "ok", value.get("message", "leitura recente")


class Journal:
    def __init__(self, data_dir, summary=None, now=None):
        now = int(time.time() if now is None else now)
        self.root = Path(data_dir) / "expeditions"
        self.root.mkdir(parents=True, exist_ok=True)
        self.summary = summary or dict(id=uuid.uuid4().hex, started_at=now, status="paused",
                                       wifi=0, ble=0, records=0, located=0, unlocated=0,
                                       distance_m=0.0, xp=0, audits=0, recoveries=0,
                                       gps_gaps=0, full=False, rewarded_discoveries=0)
        if "rewarded_discoveries" not in self.summary:
            self.summary["rewarded_discoveries"] = 0
            self.summary["reward_count_partial"] = True
        if not re.fullmatch(r"[0-9a-f]{32}", str(self.summary.get("id", ""))):
            raise ValueError("invalid expedition id")
        for key in ("started_at", "wifi", "ble", "records", "located", "unlocated", "xp", "audits", "recoveries", "gps_gaps", "rewarded_discoveries"):
            if not isinstance(self.summary.get(key), int) or self.summary[key] < 0:
                raise ValueError("invalid expedition counter")
        if not math.isfinite(float(self.summary["distance_m"])) or self.summary["distance_m"] < 0:
            raise ValueError("invalid expedition distance")
        missions.progress(self.summary)
        progression.field_progress(self.summary)
        self.folder = self.root / self.summary["id"]
        self.folder.mkdir(parents=True, exist_ok=True)
        self.seen = set()
        self.last = {}
        self.last_fix = None
        self.last_fix_time = None
        self.gps_since_checkpoint = 0
        history = self.folder / "observations.jsonl"
        if history.exists():
            with history.open(encoding="utf-8") as handle:
                for line in handle:
                    try:
                        item = json.loads(line)
                        identity = self.identity(item)
                    except (ValueError, KeyError, TypeError):
                        continue
                    if len(self.seen) < 10000 or identity in self.seen:
                        self.seen.add(identity)
                        self.last[identity] = item
        self.checkpoint()

    @classmethod
    def restore(cls, data_dir):
        path = Path(data_dir) / "expeditions" / "current.json"
        if not path.exists():
            return None
        if path.stat().st_size > 16384:
            raise ValueError("invalid expedition summary")
        summary = json.loads(path.read_text(encoding="utf-8"))
        if summary.get("status") != "ended":
            summary["status"] = "paused"
        return cls(data_dir, summary=summary)

    @staticmethod
    def identity(item):
        return hashlib.sha256((item["type"] + ":" + item["mac"].upper()).encode()).hexdigest()

    def checkpoint(self):
        _atomic(self.folder / "summary.json", self.summary)
        _atomic(self.root / "current.json", self.summary)

    def status(self, status):
        now = int(time.time())
        if self.summary["status"] == "running":
            self.summary["active_seconds"] = self.summary.get("active_seconds", 0) + max(0, now - self.summary.get("active_since", now))
        self.summary["status"] = status
        self.last_fix = None
        progression.reset_activity(self.summary)
        if status == "running":
            self.summary["active_since"] = now
        if status == "ended":
            self.summary["ended_at"] = now
            self.write_summary()
        self.checkpoint()

    def write_summary(self):
        pending = self.summary.get("upload", {})
        count = pending.get("pending")
        text = ("HACKOMON - RESUMO DA EXPEDICAO\nWi-Fi: %d\nBLE: %d\n"
                    "Registros com GPS: %d\nSem localizacao: %d\nPercurso aproximado: %.2f km\n"
                    "XP: %d\nAvaliacoes: %d\nSenhas recuperadas: %d\n"
                    "CSV contem apenas descobertas com localizacao; evidencias de testes ficam separadas.\n" % (
                        self.summary["wifi"], self.summary["ble"], self.summary["located"], self.summary["unlocated"],
                        self.summary["distance_m"] / 1000, self.summary["xp"], self.summary["audits"], self.summary["recoveries"]))
        text += "Novas descobertas premiadas desde 0.8.7: %d\n" % self.summary.get("rewarded_discoveries", 0)
        text += "Tempo ativo registrado: %d s\n" % self.summary.get("active_seconds", 0)
        text += "Revisitas premiadas desde 0.9.0: %d\n" % self.summary.get("revisit_awards", 0)
        breakdown = self.summary.get("xp_breakdown", {})
        text += "XP desde 0.9.0: novos=%d revisitas=%d atividade=%d percurso=%d\n" % tuple(
            breakdown.get(key, 0) for key in ("discoveries", "revisits", "activity", "distance"))
        medals = [title for identity, title, _key, _target in missions.RULES
                  if identity in self.summary.get("mission_medals", [])]
        text += "Medalhas nesta saida: %s\n" % (", ".join(medals) or "nenhuma")
        text += "Registros desta expedicao aguardando envio: %s\n" % (count if count is not None else "desconhecido")
        text += "WDGWars: %s\n" % pending.get("message", "nao consultado")
        path = self.folder / "summary.txt"
        temporary = path.with_suffix(".tmp")
        fd = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))

    def gps(self, fix):
        stamp = float(fix["fix_time"])
        if self.last_fix_time is not None and stamp <= self.last_fix_time:
            return
        path = self.folder / "track.jsonl"
        if path.exists() and path.stat().st_size >= 10 * 1024 * 1024:
            self.summary["full"] = True
            return
        if self.last_fix is not None:
            elapsed = stamp - self.last_fix["fix_time"]
            step = distance(fix, self.last_fix)
            sample_gap = stamp - self.last_fix_time
            if 0 < sample_gap <= 15 and elapsed > 0 and step / elapsed <= 70:
                if step >= max(5, fix["accuracy"], self.last_fix["accuracy"]):
                    self.summary["distance_m"] += step
                    self.last_fix = fix
            else:
                self.summary["gps_gaps"] += 1
                self.last_fix = fix
        else:
            self.last_fix = fix
        self.last_fix_time = stamp
        self.summary["gps_at"] = stamp
        _append(path, (json.dumps(fix) + "\n").encode())
        self.gps_since_checkpoint += 1
        if self.gps_since_checkpoint >= 10:
            self.checkpoint()
            self.gps_since_checkpoint = 0

    def observations(self, observations):
        located = []
        history = self.folder / "observations.jsonl"
        if history.exists() and history.stat().st_size >= 20 * 1024 * 1024:
            self.summary["full"] = True
            return located
        for value in observations:
            kind, address = value.get("type"), str(value.get("mac", "")).upper()
            if kind not in ("WIFI", "BLE") or not MAC.fullmatch(address):
                continue
            if address in ("00:00:00:00:00:00", "FF:FF:FF:FF:FF:FF") or (kind == "WIFI" and int(address[:2], 16) & 1):
                continue
            if str(value.get("name", "")).lower().endswith(("_nomap", "_optout")):
                continue
            item = {key: value[key] for key in ("type", "mac", "name", "auth", "timestamp", "channel", "frequency", "rssi", "time_source") if key in value}
            item["mac"] = address
            item["name"] = "".join(char for char in str(item.get("name", "")) if char.isprintable())[:128]
            try:
                if "lat" in value:
                    item.update(normalize_observation(value))
            except (ValueError, TypeError, KeyError, OverflowError):
                pass
            identity = self.identity(item)
            previous = self.last.get(identity)
            moved = previous and "lat" in previous and "lat" in item and distance(previous, item) >= 30
            newly_located = previous and "lat" not in previous and "lat" in item
            if previous and not moved and not newly_located and item["timestamp"] - previous["timestamp"] < 60:
                continue
            if identity not in self.seen:
                if len(self.seen) >= 10000:
                    self.summary["full"] = True
                    break
                self.seen.add(identity)
                self.summary["wifi" if kind == "WIFI" else "ble"] += 1
            self.last[identity] = item
            _append(history, (json.dumps(item, ensure_ascii=False) + "\n").encode())
            self.summary["records"] += 1
            if "lat" in item:
                csv_path = self.folder / "discoveries.csv"
                if not csv_path.exists():
                    _append(csv_path, export_csv([]))
                _append(csv_path, export_csv([item]).split(b"\n", 2)[2])
                self.summary["located"] += 1
                located.append(item)
            else:
                self.summary["unlocated"] += 1
        self.checkpoint()
        return located

    def audit(self, result):
        report = result["report"]
        event = dict(timestamp=int(time.time()), bssid=report["target"]["mac"],
                     capture=report["capture"]["status"], dictionary=report["dictionary"]["status"])
        _append(self.folder / "audits.jsonl", (json.dumps(event) + "\n").encode())
        self.summary["audits"] += 1
        if event["dictionary"] == "key_recovered":
            self.summary["recoveries"] += 1
        self.checkpoint()


class Pump:
    def __init__(self, config, radio_lock):
        self.config = config
        self.radio_lock = radio_lock
        self.events = queue.Queue(maxsize=128)
        self.stop_event = threading.Event()
        self.active = threading.Event()
        self.fixes = deque(maxlen=120)
        self.fix_lock = threading.Lock()
        self.threads = []
        self.ble_process = None
        self.dropped = 0

    def emit(self, kind, value):
        try:
            self.events.put((kind, value), timeout=0.1)
        except queue.Full:
            self.dropped += 1

    def start(self):
        self.active.set()
        self.threads = [threading.Thread(target=self._gps, daemon=False),
                        threading.Thread(target=self._scan, daemon=False)]
        for thread in self.threads:
            thread.start()

    def pause(self):
        self.active.clear()

    def resume(self):
        self.active.set()

    def stop(self, wait=False):
        self.stop_event.set()
        self.active.set()
        process = self.ble_process
        if process is not None and process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass
        if wait:
            for thread in self.threads:
                if thread.ident is not None:
                    thread.join()

    def alive(self):
        return any(thread.is_alive() for thread in self.threads)

    def locate(self, observation):
        item = dict(observation)
        if item.get("time_source") not in ("iw_age", "ble_receipt", "hak5_recon", "hak5_blue5"):
            return item
        with self.fix_lock:
            fixes = list(self.fixes)
        if fixes:
            fix = min(fixes, key=lambda value: abs(value["fix_time"] - item["timestamp"]))
            if abs(fix["fix_time"] - item["timestamp"]) <= 3:
                item.update({key: fix[key] for key in ("lat", "lon", "accuracy", "altitude")})
        return item

    def _gps(self):
        while not self.stop_event.is_set():
            try:
                fix = radio.gps_fix()
                with self.fix_lock:
                    self.fixes.append(fix)
                if self.active.is_set() and not self.stop_event.is_set():
                    self.emit("gps", fix)
            except (RuntimeError, OSError, ValueError, KeyError):
                if self.active.is_set():
                    self.emit("gps_error", "GPS sem posicao recente")
            self.stop_event.wait(1)

    def _ble(self):
        if recon.BLUETOOTH_DATABASE.is_file():
            return recon.read_bluetooth()
        values = {}
        names = {}
        radio.bluetooth_ready()
        failure = ""
        try:
            with subprocess.Popen(["bluetoothctl", "--timeout", "8", "scan", "le"],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, errors="replace", bufsize=1) as process:
                self.ble_process = process
                timer = threading.Timer(12, lambda: process.kill() if process.poll() is None else None)
                timer.start()
                try:
                    for line in process.stdout:
                        if self.stop_event.is_set():
                            break
                        cleaned = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", line)
                        failure = radio.bluetooth_scan_error(cleaned) or failure
                        match = re.search(r"Device ((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}) (.*)", cleaned)
                        if match and "RSSI:" not in match.group(2):
                            detail = match.group(2).strip()
                            if detail.startswith(("Name: ", "Alias: ")):
                                names[match.group(1).upper()] = detail.split(": ", 1)[1]
                            elif "[NEW]" in cleaned:
                                names[match.group(1).upper()] = detail
                        for item in radio.ble_observations(line, int(time.time())):
                            item["mac"] = item["mac"].upper()
                            item["name"] = names.get(item["mac"], "")
                            item["time_source"] = "ble_receipt"
                            if len(values) < 500 or item["mac"] in values:
                                values[item["mac"]] = self.locate(item)
                    if process.poll() is None:
                        process.kill()
                    process.wait()
                    if not self.stop_event.is_set() and (failure or process.returncode):
                        raise RuntimeError(failure or "Descoberta BLE terminou sem sucesso")
                finally:
                    timer.cancel()
                    self.ble_process = None
        except FileNotFoundError:
            raise RuntimeError("bluetoothctl ausente; Wi-Fi continua") from None
        for address, item in values.items():
            item["name"] = names.get(address, item["name"])
        return list(values.values())

    def _scan(self):
        turn = 0
        while not self.stop_event.is_set():
            if not self.active.wait(0.2):
                continue
            if self.stop_event.is_set():
                break
            if not self.radio_lock.acquire(timeout=0.2):
                continue
            try:
                if not self.active.is_set():
                    continue
                if turn % 2 and self.config.get("expedition_ble", True):
                    values = self._ble()
                    self.emit("observations", [self.locate(item) for item in values])
                    source = getattr(values, "source", "BLE")
                    self.emit("radio_status", dict(radio="ble", ok=True, count=len(values), message="%s: %d anuncios LE" % (source, len(values))))
                else:
                    observations = visit.find_networks(self.config, limit=500)
                    self.emit("targets", observations[:100])
                    self.emit("observations", [self.locate(item) for item in observations])
                    source = getattr(observations, "source", "iw")
                    self.emit("radio_status", dict(radio="wifi", ok=True, count=len(observations), message="%s: %d APs recentes" % (source, len(observations))))
            except (RuntimeError, OSError, ValueError) as error:
                message = str(error) if isinstance(error, RuntimeError) else "Falha ao ler o radio (%s)" % type(error).__name__
                self.emit("radio_status", dict(radio="ble" if turn % 2 and self.config.get("expedition_ble", True) else "wifi", ok=False, message=message))
            finally:
                self.radio_lock.release()
                turn += 1
            self.stop_event.wait(3)
