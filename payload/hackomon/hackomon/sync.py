"""Small resumable discovery uploads. Original sources are never removed."""

import csv
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import uuid

from .expedition import _atomic
from .exploration import COLUMNS, export_csv, normalize_observation
from . import wdgwars


BATCH_SIZE = 500


def guidance(status, retry_seconds=0):
    """Short next actions; distinguish failed GETs from uncertain uploads."""
    if status == "rate_limited":
        return ("Aguarde %ds antes de retomar." % retry_seconds,
                "Depois escolha Sincronizar expedicoes + fila.")
    return {
        "loading": ("Consultando apenas os arquivos locais.", "B interrompe a consulta."),
        "credentials": ("Confira a chave e a permissao da conta.", "A chave fica no config.json local."),
        "connection_error": ("Confira Internet e data/hora do Pager.", "Depois valide a conta e retome o envio."),
        "uncertain": ("Confira se o lote chegou ao WDGWars.", "Repetir envio incerto pode duplicar registros."),
        "sending": ("O ultimo envio ficou sem recibo local.", "Confira o servico antes de repetir o lote."),
        "pending_remote": ("O servidor ainda pode estar processando.", "Confira no WDGWars antes de repetir."),
        "needs_confirmation": ("Confira o lote no WDGWars antes de repetir.", "Use Repetir envio incerto se necessario."),
        "rejected": ("Confira os descartes e o historico de envios.", "CSV original preservado; corrija a causa."),
        "error": ("Confira armazenamento e historico local.", "Originais preservados; nao apague recibos."),
        "cancelled": ("Consulta/envio interrompido; dados preservados.", "Retome quando quiser pelo menu WDGWars."),
        "done_with_warnings": ("O servidor informou descartes.", "Confira o historico; aceite nao garante pontos."),
        "archived": ("Lote guardado sem confirmar recebimento.", "Um novo envio pode repetir registros."),
    }.get(status, ("A sincroniza expedicoes e fila avulsa.", "Nenhum dado sai durante esta consulta local."))


def token(item):
    return hashlib.sha256(export_csv([item]).split(b"\n", 2)[2]).hexdigest()


def _read_row(line):
    values = next(csv.reader([line.decode("utf-8")], strict=True))
    if len(values) != len(COLUMNS):
        raise ValueError("invalid row")
    row = dict(zip(COLUMNS, values))
    stamp = datetime.datetime.strptime(row["FirstSeen"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
    item = normalize_observation(dict(type=row["Type"], mac=row["MAC"], name=row["SSID"],
        auth=row["AuthMode"], timestamp=int(stamp.timestamp()), channel=row["Channel"],
        frequency=row["Frequency"], rssi=row["RSSI"], lat=row["CurrentLatitude"],
        lon=row["CurrentLongitude"], altitude=row["AltitudeMeters"], accuracy=row["AccuracyMeters"]))
    if item["name"].lower().endswith(("_nomap", "_optout")):
        raise ValueError("excluded")
    return item


class Manager:
    def __init__(self, data_dir, api_key, opener=None, cancel=None, progress=None, wait=None, clock=None):
        wdgwars.validate_key(api_key)
        self.data_dir = Path(data_dir)
        self.key = api_key
        self.opener = opener
        self.cancel = cancel or threading.Event()
        self.progress = progress or (lambda value: None)
        self.wait = wait or self.cancel.wait
        self.clock = clock or time.time
        self.root = self.data_dir / "wdgwars"
        self.outbox = self.root / "outbox"
        self.outbox.mkdir(parents=True, exist_ok=True)
        identity = hashlib.sha256(api_key.encode()).hexdigest()[:32]
        self.path = self.root / (identity + ".json")
        self.state = dict(version=1, files={}, queue_receipts=[], history=[], retry_at=0, inflight=None)
        if self.path.exists():
            try:
                if self.path.stat().st_size > 2 * 1024 * 1024:
                    raise ValueError("large manifest")
                self.state = json.loads(self.path.read_text(encoding="utf-8"))
                if (self.state.get("version") != 1 or not isinstance(self.state.get("files"), dict)
                        or not isinstance(self.state.get("history"), list)
                        or not isinstance(self.state.get("queue_receipts"), list)):
                    raise ValueError("invalid manifest")
                if (not isinstance(self.state.get("account", {}), dict)
                        or type(self.state.get("retry_at", 0)) not in (int, float)
                        or not math.isfinite(self.state.get("retry_at", 0))
                        or len(self.state["history"]) > 100
                        or len(self.state["queue_receipts"]) > 500):
                    raise ValueError("invalid metadata")
                account = self.state.get("account", {})
                if "username" in account and not isinstance(account["username"], str):
                    raise ValueError("invalid account")
                for source, saved in self.state["files"].items():
                    if (not re.fullmatch(r"[0-9a-f]{32}", source) or not isinstance(saved, dict)
                            or type(saved.get("offset")) is not int or saved["offset"] < 0
                            or not re.fullmatch(r"[0-9a-f]{64}", str(saved.get("prefix_hash", "")))):
                        raise ValueError("invalid source cursor")
                if any(not isinstance(entry, dict) or not isinstance(entry.get("counters", {}), dict)
                       for entry in self.state["history"]):
                    raise ValueError("invalid history")
                if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                       for value in self.state["queue_receipts"]):
                    raise ValueError("invalid queue receipt")
                if self.state.get("inflight") is not None and not isinstance(self.state["inflight"], dict):
                    raise ValueError("invalid in-flight record")
                confirmed = self.state.get("last_confirmed")
                if confirmed is not None and (not isinstance(confirmed, dict)
                        or type(confirmed.get("at")) is not int or not 0 <= confirmed["at"] <= 4102444800
                        or type(confirmed.get("records")) is not int or confirmed["records"] <= 0):
                    raise ValueError("invalid confirmation")
            except (ValueError, TypeError, OSError, AttributeError):
                raise RuntimeError("Historico WDGWars invalido; arquivo preservado") from None
        self.report = dict(status="ready", sent=0, batches=0, skipped=0, counters={},
                           cleared_tokens=[], account=self.state.get("account", {}), message="Pronto")
        self.watched = set()
        self.recovered_pending = bool(self.state.get("inflight"))

    def save(self):
        _atomic(self.path, self.state)

    def note(self, status, **fields):
        entry = dict(at=int(self.clock()), status=status, **fields)
        self.state["history"] = (self.state["history"] + [entry])[-100:]

    def update(self, message):
        self.report["message"] = message
        self.report["cleared_tokens"] = list(self.watched.intersection(self.state["queue_receipts"]))
        self.progress(dict(self.report))

    def source(self, identity):
        if not re.fullmatch(r"[0-9a-f]{32}", identity):
            raise RuntimeError("Identificador de expedicao invalido")
        root = self.data_dir / "expeditions"
        folder = root / identity
        path = folder / "discoveries.csv"
        if folder.is_symlink() or path.is_symlink() or not path.is_file():
            raise RuntimeError("CSV original ausente ou nao permitido; envio preservado")
        if not path.resolve().is_relative_to(root.resolve()):
            raise RuntimeError("CSV fora das expedicoes")
        return path

    def sources(self):
        root = self.data_dir / "expeditions"
        found = []
        if root.exists():
            for folder in root.iterdir():
                if not re.fullmatch(r"[0-9a-f]{32}", folder.name) or folder.is_symlink():
                    continue
                path = folder / "discoveries.csv"
                if not path.is_file() or path.is_symlink():
                    continue
                stat = path.stat()
                saved = self.state["files"].get(folder.name, {})
                if stat.st_size != saved.get("offset", 0) or stat.st_mtime_ns != saved.get("mtime_ns"):
                    found.append((stat.st_mtime_ns, folder.name, stat.st_size))
        return sorted(found)[:500]

    def expedition_pending(self, identity):
        """Local snapshot only; count valid unsent rows against this key's receipts."""
        path = self.source(identity)
        pending = skipped = 0
        for batch in self.batches(identity, path.stat().st_size):
            pending += len(batch["rows"])
            skipped += batch["skipped"]
        inflight = self.state.get("inflight") or {}
        kind = inflight.get("kind")
        delay = max(0, int(self.state.get("retry_at", 0) - self.clock()))
        if kind in ("uncertain", "pending_remote", "sending"):
            message = "Lote incerto; revisar em WDGWars"
        elif delay:
            message = "Retomar em %ds no menu WDGWars" % delay
        elif inflight:
            message = "Lote salvo; retome em WDGWars"
        else:
            message = "Sincronize no menu WDGWars" if pending else "CSV processado; confira historico"
        return dict(pending=pending, skipped=skipped, message=message, at=int(self.clock()))

    def overview(self, observations=(), status=None):
        """Stream all local expeditions in bounded batches, with no HTTP requests."""
        remaining = {token(item) for item in observations}.difference(self.state["queue_receipts"])
        missing = set(self.state["files"])
        result = dict(csv_records=0, queue_records=0, pending_expeditions=0,
                      skipped=0, incomplete=0, source_errors=0, scanned=0,
                      complete=True, at=int(self.clock()))
        root = self.data_dir / "expeditions"
        try:
            if root.exists():
                with os.scandir(root) as folders:
                    for folder in folders:
                        if self.cancel.is_set():
                            result["complete"] = False
                            break
                        if not re.fullmatch(r"[0-9a-f]{32}", folder.name):
                            continue
                        try:
                            if not folder.is_dir(follow_symlinks=False):
                                if folder.is_symlink() or folder.name in missing:
                                    result["source_errors"] += 1
                                    missing.discard(folder.name)
                                continue
                            missing.discard(folder.name)
                            path = Path(folder.path) / "discoveries.csv"
                            if not path.exists():
                                summary_path = Path(folder.path) / "summary.json"
                                if summary_path.is_file():
                                    if summary_path.is_symlink() or summary_path.stat().st_size > 16384:
                                        raise ValueError("invalid summary")
                                    summary = json.loads(summary_path.read_text(encoding="utf-8"))
                                    if not isinstance(summary, dict):
                                        raise ValueError("invalid summary")
                                    if summary.get("located", 0):
                                        raise ValueError("missing discoveries")
                                if folder.name in self.state["files"]:
                                    raise ValueError("missing processed source")
                                continue
                            path = self.source(folder.name)
                            limit = path.stat().st_size
                            count = 0
                            for batch in self.batches(folder.name, limit):
                                if self.cancel.is_set():
                                    result["complete"] = False
                                    break
                                count += len(batch["rows"])
                                result["csv_records"] += len(batch["rows"])
                                result["skipped"] += batch["skipped"]
                                if remaining:
                                    remaining.difference_update(token(item) for item in batch["rows"])
                            result["pending_expeditions"] += bool(count)
                            result["scanned"] += 1
                            if limit:
                                with path.open("rb") as stream:
                                    stream.seek(limit - 1)
                                    result["incomplete"] += stream.read(1) != b"\n"
                        except (RuntimeError, OSError, ValueError, KeyError, TypeError, csv.Error):
                            result["source_errors"] += 1
        except OSError:
            result["source_errors"] += 1
        if not self.cancel.is_set():
            result["source_errors"] += len(missing)
        result["complete"] = result["complete"] and not result["source_errors"]
        result["queue_records"] = len(remaining)
        result["known_pending"] = result["csv_records"] + result["queue_records"]
        result["pending"] = result["known_pending"] if result["complete"] else None
        last = self.state.get("last_confirmed")
        if last is None:
            last = next((dict(at=entry["at"], records=entry["records"])
                         for entry in reversed(self.state["history"])
                         if entry.get("status") == "confirmed" and type(entry.get("at")) is int
                         and 0 <= entry["at"] <= 4102444800
                         and type(entry.get("records")) is int and entry["records"] > 0), None)
        result["last_confirmed"] = last
        delay = max(0, int(self.state.get("retry_at", 0) - self.clock()))
        pending = self.state.get("inflight") or {}
        fallback = "done_with_warnings" if last and last.get("warnings") else "ready"
        kind = ("rate_limited" if delay else status if status in (
            "credentials", "connection_error", "error", "cancelled") else
            pending.get("kind") or status or fallback)
        if result["source_errors"]:
            kind = "error"
        elif not result["complete"]:
            kind = "cancelled"
        result["guidance"] = guidance(kind, delay)
        return result

    def batches(self, identity, limit):
        path = self.source(identity)
        saved = self.state["files"].get(identity, {})
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            first, columns = stream.readline(8193), stream.readline(8193)
            if (not first.startswith(b"WigleWifi-1.6,") or len(first) > 8192
                    or tuple(next(csv.reader([columns.decode("utf-8").strip()]))) != COLUMNS):
                raise RuntimeError("Cabecalho CSV de expedicao invalido")
            digest.update(first + columns)
            offset = saved.get("offset", stream.tell())
            if type(offset) is not int or not stream.tell() <= offset <= limit:
                raise RuntimeError("CSV truncado/alterado; retomada bloqueada")
            while stream.tell() < offset:
                piece = stream.read(min(65536, offset - stream.tell()))
                if not piece:
                    raise RuntimeError("CSV truncado; retomada bloqueada")
                digest.update(piece)
            if saved and digest.hexdigest() != saved.get("prefix_hash"):
                raise RuntimeError("CSV alterado; progresso preservado para revisao")
            rows, skipped = [], 0
            start = offset
            complete_end = offset
            while stream.tell() < limit:
                line = stream.readline(min(8193, limit - stream.tell()))
                if len(line) > 8192:
                    raise RuntimeError("Linha CSV muito grande; envio interrompido")
                if not line.endswith(b"\n"):
                    break  # An active collector may still be writing this record.
                digest.update(line)
                complete_end = stream.tell()
                try:
                    rows.append(_read_row(line))
                except (ValueError, TypeError, KeyError, OverflowError, UnicodeError, csv.Error, OSError):
                    skipped += 1
                if len(rows) + skipped >= BATCH_SIZE:
                    yield dict(source=identity, start=start, offset=stream.tell(),
                               prefix_hash=digest.hexdigest(), rows=rows, skipped=skipped)
                    start = stream.tell()
                    rows, skipped = [], 0
            # Never checkpoint a partial trailing line that was not hashed.
            if rows or skipped:
                yield dict(source=identity, start=start, offset=complete_end,
                           prefix_hash=digest.hexdigest(), rows=rows, skipped=skipped)
            elif not saved and limit == offset:
                yield dict(source=identity, start=offset, offset=offset,
                           prefix_hash=digest.hexdigest(), rows=[], skipped=0)

    def _payload_path(self, name):
        if not re.fullmatch(r"[0-9a-f]{32}\.csv", str(name)):
            raise RuntimeError("Lote local invalido")
        path = self.outbox / name
        if path.is_symlink():
            raise RuntimeError("Lote local nao permitido")
        return path

    def stage(self, batch):
        rows = batch.pop("rows")
        data = export_csv(rows)
        if len(data) > 1024 * 1024:
            raise RuntimeError("Lote local excede 1 MB")
        name = uuid.uuid4().hex + ".csv"
        path = self._payload_path(name)
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        tokens = {token(item) for item in rows}
        self.state["inflight"] = dict(batch, payload=name, payload_hash=hashlib.sha256(data).hexdigest(),
                                      records=len(rows), queue_tokens=list(tokens.intersection(self.watched)),
                                      kind="prepared")
        self.recovered_pending = False
        self.save()

    def acknowledge(self, pending, counters):
        source = pending["source"]
        previous_state = self.state
        next_state = dict(self.state, files=dict(self.state["files"]),
                          queue_receipts=list(self.state["queue_receipts"]))
        if source != "queue":
            next_state["files"][source] = dict(offset=pending["offset"], prefix_hash=pending["prefix_hash"],
                                               mtime_ns=self.source(source).stat().st_mtime_ns)
        receipts = set(next_state["queue_receipts"])
        receipts.update(pending.get("queue_tokens", []))
        next_state["queue_receipts"] = list(receipts.intersection(self.watched))
        self.state = next_state
        self.note("confirmed" if pending["records"] else "skipped_local",
                  source=source, records=pending["records"], skipped=pending.get("skipped", 0), counters=counters)
        if pending["records"]:
            self.state["last_confirmed"] = dict(at=int(self.clock()), records=pending["records"],
                                                warnings=bool(pending.get("skipped", 0) or any(
                                                    counters.get(key, 0) for key in ("bad_rows", "no_gps"))))
        self.state["inflight"] = None
        self.state["retry_at"] = 0
        try:
            self.save()
        except OSError:
            self.state = previous_state
            raise
        self.report["sent"] += pending["records"]
        self.report["batches"] += bool(pending["records"])
        self.report["skipped"] += pending.get("skipped", 0)
        for key, value in counters.items():
            self.report["counters"][key] = self.report["counters"].get(key, 0) + value
        name = pending.get("payload")
        if name:
            try:
                self._payload_path(name).unlink()
            except OSError:
                pass  # Only an acknowledged temporary payload; originals stay intact.

    def send_pending(self, force=False):
        pending = self.state.get("inflight")
        if not pending:
            return True
        if pending.get("kind") in ("uncertain", "pending_remote", "sending") and not force:
            self.report["status"] = "needs_confirmation"
            self.update("Lote sem confirmacao; use Repetir envio incerto")
            return False
        if self.cancel.is_set():
            self.report["status"] = "cancelled"
            return False
        if self.report["batches"] and self.wait(1):
            self.report["status"] = "cancelled"
            return False
        path = self._payload_path(pending["payload"])
        if path.stat().st_size > 1024 * 1024:
            raise RuntimeError("Lote local muito grande")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != pending["payload_hash"]:
            raise RuntimeError("Lote local alterado; envio bloqueado")
        lines = data.splitlines(keepends=True)
        if (len(lines) < 3 or not lines[0].startswith(b"WigleWifi-1.6,")
                or tuple(next(csv.reader([lines[1].decode().strip()]))) != COLUMNS):
            raise RuntimeError("Conteudo do lote invalido")
        payload_tokens = {token(_read_row(line)) for line in lines[2:]}
        if pending["source"] == "queue" and not payload_tokens.issubset(self.watched):
            raise RuntimeError("Fila original alterada; lote pendente preservado")
        pending["queue_tokens"] = list(payload_tokens.intersection(self.watched))
        if pending["source"] != "queue":
            source = self.source(pending["source"])
            if source.stat().st_size < pending["offset"]:
                raise RuntimeError("CSV original truncado; lote preservado")
            if self.recovered_pending:
                digest = hashlib.sha256()
                remaining = pending["offset"]
                with source.open("rb") as stream:
                    while remaining:
                        piece = stream.read(min(65536, remaining))
                        if not piece:
                            raise RuntimeError("CSV original truncado; lote preservado")
                        digest.update(piece)
                        remaining -= len(piece)
                if digest.hexdigest() != pending["prefix_hash"]:
                    raise RuntimeError("CSV original alterado; lote preservado")
        self.update("Enviando lote de %d registros... B cancela apos resposta" % pending["records"])
        pending["kind"] = "sending"
        self.save()
        try:
            counters = wdgwars.upload_payload(data, self.key, self.opener)
        except wdgwars.UploadError as error:
            pending["kind"] = error.kind
            pending["job_id"] = error.job_id
            self.state["retry_at"] = int(self.clock()) + error.retry_after
            self.note(error.kind, source=pending["source"], records=pending["records"], retry_at=self.state["retry_at"], job_id=error.job_id)
            self.save()
            self.report["status"] = error.kind
            self.update(str(error))
            return False
        self.acknowledge(pending, counters)
        self.recovered_pending = False
        self.update("Lote confirmado; %d registros enviados nesta sessao" % self.report["sent"])
        return True

    def run(self, mode, observations=(), retry_uncertain=False):
        self.watched = {token(item) for item in observations}
        self.state["queue_receipts"] = list(set(self.state["queue_receipts"]).intersection(self.watched))
        try:
            if mode not in ("account", "queue", "expeditions", "retry", "archive"):
                raise RuntimeError("Modo de sincronizacao invalido")
            if self.cancel.is_set():
                self.report["status"] = "cancelled"
                self.update("Cancelado antes de iniciar a conexao")
                return self.report
            if mode == "archive":
                pending = self.state.get("inflight")
                if pending:
                    self.note("archived_local", source=pending.get("source", ""), records=pending.get("records", 0),
                              payload=pending.get("payload", ""), job_id=pending.get("job_id", ""))
                    self.state["inflight"] = None
                    self.save()
                self.report["status"] = "archived"
                self.update("Lote guardado localmente; recebimento nao foi confirmado" if pending else "Nao ha lote pendente para guardar")
                return self.report
            delay = int(self.state.get("retry_at", 0) - self.clock())
            if delay > 0:
                self.report["status"] = "rate_limited"
                self.update("Aguarde %ds antes de tentar novamente" % delay)
                return self.report
            pending = self.state.get("inflight")
            if (mode != "account" and pending and not retry_uncertain
                    and pending.get("kind") in ("uncertain", "pending_remote", "sending")):
                self.report["status"] = "needs_confirmation"
                self.update("Lote sem confirmacao; use Repetir envio incerto")
                return self.report
            self.update("Validando conta WDGWars...")
            self.state["account"] = wdgwars.account(self.key, self.opener)
            self.report["account"] = self.state["account"]
            self.save()
            if mode == "account":
                self.report["status"] = "account_ok"
                self.update("Conta confirmada: " + self.state["account"]["username"])
                return self.report
            pending = self.state.get("inflight")
            if mode == "queue" and pending and pending["source"] != "queue":
                self.report["status"] = "pending_source"
                self.update("Lote de expedicao pendente; escolha Expedicoes ou Repetir")
                return self.report
            if mode == "retry" and not pending:
                self.report["status"] = "done"
                self.update("Nao ha lote pendente para repetir")
                return self.report
            if self.cancel.is_set() or not self.send_pending(force=retry_uncertain):
                if self.cancel.is_set():
                    self.report["status"] = "cancelled"
                return self.report
            if mode == "expeditions":
                for _mtime, identity, size in self.sources():
                    for batch in self.batches(identity, size):
                        if self.cancel.is_set():
                            self.report["status"] = "cancelled"
                            return self.report
                        if not batch["rows"]:
                            self.acknowledge(dict(batch, records=0), {})
                            continue
                        self.stage(batch)
                        if not self.send_pending():
                            return self.report
                    saved = self.state["files"].get(identity)
                    if saved and saved["offset"] == size:
                        saved["mtime_ns"] = self.source(identity).stat().st_mtime_ns
                        self.save()
            if mode in ("queue", "expeditions"):
                remaining = [item for item in observations if token(item) not in self.state["queue_receipts"]]
                for start in range(0, len(remaining), BATCH_SIZE):
                    self.stage(dict(source="queue", rows=remaining[start:start + BATCH_SIZE], skipped=0))
                    if not self.send_pending():
                        return self.report
            self.report["status"] = "done"
            self.report["remaining_sources"] = len(self.sources())
            if self.report["remaining_sources"]:
                self.report["status"] = "partial"
                self.update("Lotes confirmados; ha expedicoes com dados novos/incompletos")
            elif self.report["skipped"] or any(self.report["counters"].get(key, 0) for key in ("bad_rows", "no_gps")):
                self.report["status"] = "done_with_warnings"
                self.update("Envio concluido com descartes; confira o historico")
            else:
                self.update("Concluido: %d registros, %d lotes confirmados" % (self.report["sent"], self.report["batches"]))
        except wdgwars.UploadError as error:
            # This exception is from account validation, before any new POST.
            self.report["status"] = "connection_error" if error.kind == "uncertain" else error.kind
            self.update("Conta nao validada; confira Internet e chave" if error.kind == "uncertain" else str(error))
            if error.retry_after:
                self.state["retry_at"] = int(self.clock()) + error.retry_after
                try:
                    self.save()
                except OSError:
                    self.report["status"] = "error"
                    self.update("Falha ao salvar espera; confira armazenamento")
        except (RuntimeError, ValueError, KeyError, TypeError, OSError, csv.Error) as error:
            self.report["status"] = "error"
            self.update(str(error) if isinstance(error, RuntimeError) else "Falha local na sincronizacao; arquivos preservados")
        finally:
            self.report["cleared_tokens"] = list(self.watched.intersection(self.state["queue_receipts"]))
            self.report["history"] = self.state["history"][-8:]
            self.report["overview"] = self.overview(observations, status=self.report["status"])
        return self.report
