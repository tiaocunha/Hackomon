"""Atomic, versioned JSON persistence."""

import json
import os
import time
from pathlib import Path

from .model import GameState


class StateStore:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / "state.json"

    def load_or_create(self, catalog, line_id=None, now=None):
        if not self.path.exists():
            return GameState.new(catalog, line_id=line_id, now=now), None
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                original = json.load(handle)
                state = GameState.from_dict(original, catalog)
            state.apply_elapsed_time(now)
            if "generations_revision" not in original:
                backup = self.data_dir / "state.json.before-generations-v1"
                temporary_backup = self.data_dir / ("state.json.before-generations-v1.tmp-%d" % os.getpid())
                try:
                    if not backup.exists():
                        fd = os.open(str(temporary_backup), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                        with os.fdopen(fd, "w", encoding="utf-8") as handle:
                            json.dump(original, handle, ensure_ascii=False)
                            handle.flush()
                            os.fsync(handle.fileno())
                        if not backup.exists():
                            os.replace(str(temporary_backup), str(backup))
                except OSError:
                    return state, "Save carregado; copia anterior a geracoes indisponivel"
                finally:
                    try:
                        temporary_backup.unlink()
                    except OSError:
                        pass
            return state, None
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            stamp = int(time.time())
            quarantine = self.data_dir / ("state.json.corrupt-%d" % stamp)
            try:
                os.replace(str(self.path), str(quarantine))
                warning = "Save inválido movido para %s" % quarantine.name
            except OSError:
                warning = "Save inválido; não foi possível mover o arquivo"
            return GameState.new(catalog, line_id=line_id, now=now), "%s (%s)" % (warning, error)

    def save(self, state):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temp_path = self.data_dir / ("state.json.tmp-%d" % os.getpid())
        payload = json.dumps(state.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        try:
            with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temp_path), str(self.path))
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass

