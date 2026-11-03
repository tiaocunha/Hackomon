"""Interactive Pager application loop."""

import os
from pathlib import Path
import queue
import threading
import time

from .catalog import CreatureCatalog
from .evolution import advance_one_if_ready
from .pager_backend import PagerDisplay
from .storage import StateStore
from .ui import HackomonUI, NETWORK_MENU
from .exploration import export_csv, record_observations
from .network_config import load_config
from . import bluetooth_lab, expedition, lab, radio, visit, wdgwars
from . import sync as wdg_sync


ACTION_KEYS = ("feed", "play", "rest")
NETWORK_ACTIONS = tuple(action for action, _label in NETWORK_MENU)


class HackomonApp:
    def __init__(self, display, catalog, store, clock=None):
        self.display = display
        self.catalog = catalog
        self.store = store
        self.clock = clock or time.time
        self.state, self.warning = store.load_or_create(catalog, now=int(self.clock()))
        self.ui = HackomonUI(display, catalog)
        self.selected = 0
        self.screen = "home"
        self.bestiary_index = catalog.creature(self.state.creature_id)["index"]
        self.message = self.warning or ""
        self.message_until = time.monotonic() + (5.0 if self.warning else 0.0)
        self.pose = "idle"
        self.pose_until = 0.0
        self.network_selected = 0
        self.network_message = "GPS externo via gpsd necessario"
        self.worker = None
        self.results = queue.Queue()
        self.visit_networks = []
        self.visit_selected = 0
        self.visit_message = "Escolha a rede do cliente para este atendimento"
        self.visit_report = None
        self.radio_lock = threading.Lock()
        self.pump = None
        self.expedition_message = "A inicia uma expedicao"
        self.expedition_targets = []
        self.visit_origin = "network"
        self.resume_expedition = False
        self.sync_selected = 0
        self.sync_history_offset = 0
        self.sync_mode = "expeditions"
        self.sync_status = {"message": "Escolha o que sincronizar", "status": "ready"}
        self.sync_cancel = threading.Event()
        self.sync_events = queue.Queue(maxsize=64)
        self.worker_action = ""
        try:
            self.journal = expedition.Journal.restore(self.store.data_dir)
        except (ValueError, OSError, KeyError, TypeError):
            self.journal = None
            self.expedition_message = "Diario anterior ilegivel; arquivos preservados"

    def _start_expedition(self):
        try:
            config = load_config(self.store.data_dir)
            if self.journal is None or self.journal.summary["status"] == "ended":
                self.journal = expedition.Journal(self.store.data_dir, now=int(self.clock()))
                self.expedition_targets = []
            if self.journal.summary.get("full"):
                self.expedition_message = "Diario cheio; encerre e inicie outra expedicao"
                return
            self.journal.summary.pop("storage_error", None)
            self.journal.summary["radios"] = {
                "wifi": dict(ok=True, message="aguardando busca"),
                "ble": dict(ok=True, message="aguardando busca" if config.get("expedition_ble", True) else "desativado no config"),
            }
            self.journal.status("running")
            if self.pump is None:
                self.pump = expedition.Pump(config, self.radio_lock)
                self.pump.start()
            else:
                self.pump.resume()
            self.expedition_message = "Explorando... GPS e radios em verificacao"
        except (RuntimeError, OSError, ValueError):
            if self.pump is not None:
                self.pump.stop(wait=True)
                self.pump = None
            if self.journal is not None:
                self.journal.summary["status"] = "paused"
            self.expedition_message = "Falha ao iniciar; confira config e armazenamento"

    def _handle_expedition(self, pressed):
        if self.worker is not None:
            return True
        if pressed & self.display.BTN_A:
            if self.journal is not None and self.pump is not None and self.journal.summary["status"] == "running":
                self.pump.pause()
                self.journal.status("paused")
                self.expedition_message = "Pausada; ciclo atual pode terminar"
            elif self.journal is None or self.journal.summary["status"] != "ending":
                self._start_expedition()
        if pressed & self.display.BTN_LEFT and self.pump is not None:
            self.journal.status("ending")
            self.pump.stop()
            self.expedition_message = "Encerrando o ciclo atual..."
        if pressed & self.display.BTN_RIGHT:
            if self.expedition_targets:
                self.visit_networks = [dict(item) for item in self.expedition_targets]
                self.visit_selected = 0
                self.visit_origin = "expedition"
                self.screen = "visit"
                self.visit_message = "Escolha apenas um AP autorizado para testar"
            else:
                self.expedition_message = "Aguarde uma busca Wi-Fi para escolher o alvo"
        if pressed & (self.display.BTN_B | self.display.BTN_POWER):
            self.screen = "home"
        return True

    def _tick_expedition(self):
        if self.pump is None or self.journal is None:
            return
        for _ in range(32):
            try:
                kind, value = self.pump.events.get_nowait()
            except queue.Empty:
                break
            try:
                if kind == "gps" and self.journal.summary["status"] == "running":
                    self.journal.gps(value)
                elif kind == "targets":
                    self.expedition_targets = value
                elif kind == "observations":
                    located = self.journal.observations(value)
                    result = record_observations(self.state, located, int(self.clock()))
                    self.journal.summary["xp"] += result["xp"]
                    self.journal.checkpoint()
                    evolved = advance_one_if_ready(self.state, self.catalog)
                    if result["xp"] or evolved.evolved:
                        self.pose = "happy"
                        self.pose_until = time.monotonic() + 2
                    self.expedition_message = "%d na amostra; +%d XP%s" % (
                        len(value), result["xp"], " (fila mapa cheia; CSV preservado)" if result["full"] else "")
                    self.store.save(self.state)
                elif kind == "radio_status" and value.get("radio") in ("wifi", "ble"):
                    self.journal.summary.setdefault("radios", {})[value["radio"]] = value
                elif kind == "gps_error":
                    self.journal.summary["gps_error"] = value
                elif kind == "radio_error":
                    self.expedition_message = value
                if self.journal.summary.get("full"):
                    self.pump.pause()
                    self.journal.status("paused")
                    self.expedition_message = "Limite do diario; encerre e inicie outra expedicao"
            except (ValueError, OSError, KeyError, TypeError):
                self.pump.pause()
                self.journal.summary["status"] = "paused"
                self.journal.summary["storage_error"] = True
                self.journal.last_fix = None
                self.expedition_message = "Falha de armazenamento; coleta pausada"
        if self.journal.summary["status"] == "ending" and not self.pump.alive() and self.pump.events.empty():
            self.journal.summary["dropped_events"] = self.pump.dropped
            self.journal.status("ended")
            self.pump = None
            self.expedition_targets = []
            self.expedition_message = "Expedicao encerrada; diario e CSV salvos"

    def _network_job(self, action):
        if self.worker is not None:
            return
        snapshot = list(self.state.network_queue)
        sync_mode = self.sync_mode
        if action.startswith("sync"):
            self.sync_cancel.clear()
        visit_target = (dict(self.visit_networks[self.visit_selected])
                        if action == "visit_assess" and self.visit_networks else None)
        def work():
            locked = False
            try:
                if action not in ("upload", "export", "sync", "sync_history"):
                    self.radio_lock.acquire()
                    locked = True
                config = load_config(self.store.data_dir)
                if action in ("WIFI", "BLE"):
                    result = radio.discover(action, config.get("wifi_interface", ""))
                elif action == "upload":
                    count = wdgwars.upload(snapshot, config.get("wdgwars_api_key", ""))
                    result = (count, [item["identity"] for item in snapshot])
                elif action in ("sync", "sync_history"):
                    manager = wdg_sync.Manager(self.store.data_dir, config.get("wdgwars_api_key", ""),
                                               cancel=self.sync_cancel, progress=self._sync_progress)
                    if action == "sync_history":
                        result = dict(status="history", account=manager.state.get("account", {}),
                                      history=manager.state["history"], cleared_tokens=[], message="Historico local")
                    else:
                        result = manager.run(sync_mode, snapshot, retry_uncertain=sync_mode == "retry")
                elif action == "export":
                    path = Path(self.store.data_dir) / "discoveries.csv"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open("wb") as handle:
                        handle.write(export_csv(snapshot))
                    result = "CSV salvo em discoveries.csv"
                elif action == "capture":
                    result = lab.capture(config, self.store.data_dir)
                elif action == "bluetooth_audit":
                    result = bluetooth_lab.audit(config, self.store.data_dir)
                elif action == "test":
                    result = lab.test_dictionary(config, self.store.data_dir)
                elif action == "visit_scan":
                    result = visit.find_networks(config)
                elif action == "visit_assess" and visit_target is not None:
                    result = visit.assess(config, visit_target, self.store.data_dir)
                else:
                    raise RuntimeError("Acao de rede desconhecida")
                self.results.put((action, result, None))
            except Exception as error:
                # Never put credentials, tool output or server response bodies on screen/log.
                safe = str(error) if isinstance(error, RuntimeError) else "Falha local; confira configuracao"
                self.results.put((action, None, safe))
            finally:
                if locked:
                    self.radio_lock.release()
        self.network_message = "Trabalhando... aguarde (max. 90s)"
        self.worker_action = action
        if action.startswith("visit_"):
            self.visit_message = "Buscando redes..." if action == "visit_scan" else "Avaliando o alvo selecionado..."
        self.worker = threading.Thread(target=work, daemon=False)
        self.worker.start()

    def _finish_network_job(self):
        try:
            action, result, error = self.results.get_nowait()
        except queue.Empty:
            return
        self.worker.join()
        self.worker = None
        self.worker_action = ""
        if error:
            self.network_message = error
            if action.startswith("sync"):
                self.sync_status = dict(status="error", message=error)
            if action.startswith("visit_"):
                self.visit_message = error
            self._resume_after_audit()
            return
        if action.startswith("sync"):
            self.sync_status = result
            acknowledged = set(result.get("cleared_tokens", []))
            self.state.network_queue = [item for item in self.state.network_queue
                                        if wdg_sync.token(item) not in acknowledged]
            if result.get("status") == "cancelled":
                self.sync_status["message"] = "Cancelado; lotes confirmados preservados"
            self.store.save(self.state)
            return
        if action == "visit_scan":
            self.visit_networks = result
            self.visit_selected = 0
            self.visit_message = "%d redes; escolha apenas a rede do cliente" % len(result)
            return
        if action == "visit_assess":
            self.visit_report = result["report"]
            self.visit_message = result["message"]
            self.screen = "visit_report"
            if self.visit_origin == "expedition" and self.journal is not None:
                self.journal.audit(result)
            self._resume_after_audit()
        if action in ("WIFI", "BLE"):
            summary = record_observations(self.state, result, int(self.clock()))
            self.network_message = "%d registros, +%d XP%s" % (
                summary["added"], summary["xp"], " (fila cheia)" if summary["full"] else "")
        elif action == "upload":
            uploaded = set(result[1])
            self.state.network_queue = [item for item in self.state.network_queue if item["identity"] not in uploaded]
            self.network_message = "WDGWars confirmou o recebimento de %d registros" % result[0]
        elif action == "export":
            self.network_message = result
        else:
            self.network_message = result["message"]
            reward = result.get("reward_id")
            if result.get("found") and reward not in self.state.lab_rewards:
                self.state.lab_rewards.append(reward)
                self.state.xp += 10
                self.state.level = min(99, 1 + self.state.xp // 30)
            elif (action == "bluetooth_audit" and result.get("completed")
                  and reward not in self.state.lab_rewards):
                self.state.lab_rewards.append(reward)
                self.state.xp += 5
                self.state.level = min(99, 1 + self.state.xp // 30)
                self.network_message += " +5 XP"
            elif (action == "visit_assess" and result.get("completed")
                  and reward not in self.state.lab_rewards):
                self.state.lab_rewards.append(reward)
                self.state.xp += 5
                self.state.level = min(99, 1 + self.state.xp // 30)
        evolution = advance_one_if_ready(self.state, self.catalog)
        if evolution.evolved:
            self.network_message = "EVOLUCAO! " + self.network_message
            self.display.vibrate(180)
        self.store.save(self.state)

    def _resume_after_audit(self):
        requested = self.resume_expedition
        self.resume_expedition = False
        if (requested and self.pump is not None and self.journal is not None
                and self.journal.summary["status"] == "paused"
                and not self.journal.summary.get("full")
                and not self.journal.summary.get("storage_error")):
            self.journal.status("running")
            self.pump.resume()

    def _handle_network(self, pressed):
        if self.worker is not None:
            return True
        if pressed & (self.display.BTN_B | self.display.BTN_POWER):
            self.screen = "home"
            return True
        if self.screen == "upload_confirm":
            if pressed & self.display.BTN_A:
                self.screen = "network"
                self._network_job("upload")
            return True
        if pressed & self.display.BTN_UP:
            self.network_selected = (self.network_selected - 1) % len(NETWORK_ACTIONS)
        if pressed & self.display.BTN_DOWN:
            self.network_selected = (self.network_selected + 1) % len(NETWORK_ACTIONS)
        if pressed & self.display.BTN_A:
            action = NETWORK_ACTIONS[self.network_selected]
            if action == "upload":
                self.screen = "wdgwars"
            elif action == "visit_scan":
                self.visit_origin = "network"
                self.screen = "visit"
                self.visit_networks = []
                self.visit_report = None
                self._network_job(action)
            else:
                self._network_job(action)
        return True

    def _sync_progress(self, value):
        try:
            self.sync_events.put_nowait(value)
        except queue.Full:
            try:
                self.sync_events.get_nowait()
            except queue.Empty:
                pass
            self.sync_events.put_nowait(value)

    def _drain_sync_progress(self):
        while True:
            try:
                self.sync_status = self.sync_events.get_nowait()
            except queue.Empty:
                return

    def _handle_wdgwars(self, pressed):
        if self.worker is not None:
            if self.worker_action.startswith("sync") and pressed & (self.display.BTN_B | self.display.BTN_POWER):
                self.sync_cancel.set()
                self.sync_status["message"] = "Cancelando apos a resposta; timeout de rede 15s"
            return True
        if pressed & (self.display.BTN_B | self.display.BTN_POWER):
            self.screen = "wdgwars" if self.screen != "wdgwars" else "network"
            return True
        if self.screen == "wdgwars_confirm":
            if pressed & self.display.BTN_A:
                self.screen = "wdgwars"
                self._network_job("sync")
            return True
        if self.screen == "wdgwars_history":
            size = len(self.sync_status.get("history", []))
            if pressed & self.display.BTN_DOWN:
                self.sync_history_offset = min(max(0, (size - 1) // 6 * 6), self.sync_history_offset + 6)
            if pressed & self.display.BTN_UP:
                self.sync_history_offset = max(0, self.sync_history_offset - 6)
            return True
        if pressed & self.display.BTN_UP:
            self.sync_selected = (self.sync_selected - 1) % 6
        if pressed & self.display.BTN_DOWN:
            self.sync_selected = (self.sync_selected + 1) % 6
        if pressed & self.display.BTN_A:
            self.sync_mode = ("expeditions", "queue", "account", "history", "retry", "archive")[self.sync_selected]
            if self.sync_mode == "account":
                self._network_job("sync")
            elif self.sync_mode == "history":
                self.sync_history_offset = 0
                self.screen = "wdgwars_history"
                self._network_job("sync_history")
            else:
                self.screen = "wdgwars_confirm"
        return True

    def _handle_visit(self, pressed):
        if self.worker is not None:
            return True
        if pressed & (self.display.BTN_B | self.display.BTN_POWER):
            if self.screen == "visit_report":
                self.screen = "expedition" if self.visit_origin == "expedition" else "visit"
            else:
                self.screen = "expedition" if self.visit_origin == "expedition" else "network"
                self.visit_networks = []
                self.visit_report = None
            return True
        if self.screen == "visit_report":
            return True
        if pressed & self.display.BTN_LEFT:
            if self.visit_origin == "expedition":
                self.visit_networks = [dict(item) for item in self.expedition_targets]
                self.visit_selected = 0
                return True
            self.visit_networks = []
            self._network_job("visit_scan")
            return True
        if self.visit_networks:
            if pressed & self.display.BTN_UP:
                self.visit_selected = (self.visit_selected - 1) % len(self.visit_networks)
            if pressed & self.display.BTN_DOWN:
                self.visit_selected = (self.visit_selected + 1) % len(self.visit_networks)
            if pressed & self.display.BTN_A:
                if self.visit_origin == "expedition" and self.pump is not None:
                    self.resume_expedition = self.journal.summary["status"] == "running"
                    self.pump.pause()
                    self.journal.status("paused")
                self._network_job("visit_assess")
        return True

    def _set_message(self, message, seconds=2.0):
        self.message = message
        self.message_until = time.monotonic() + seconds

    def _current_pose(self):
        now = time.monotonic()
        if now < self.pose_until:
            return self.pose
        if self.state.energy < 15:
            return "sleep"
        if self.state.hunger < 15 or self.state.happiness < 15:
            return "sad"
        return "idle"

    def _care(self, action):
        outcome = self.state.perform_care(action, now=int(self.clock()))
        self._set_message(outcome.message)
        if not outcome.accepted:
            return
        evolution = advance_one_if_ready(self.state, self.catalog)
        self.pose = "happy"
        self.pose_until = time.monotonic() + 1.5
        if evolution.evolved:
            creature = self.catalog.creature(evolution.creature_id)
            self._set_message("EVOLUCAO: %s!" % creature["name"], seconds=4.0)
            self.display.vibrate(180)
        else:
            self.display.vibrate(55)
        self.store.save(self.state)

    def _handle_home(self, pressed):
        if pressed & self.display.BTN_UP:
            self.selected = (self.selected - 1) % 7
        if pressed & self.display.BTN_DOWN:
            self.selected = (self.selected + 1) % 7
        if pressed & self.display.BTN_A:
            if self.selected < 3:
                self._care(ACTION_KEYS[self.selected])
            elif self.selected == 3:
                self.bestiary_index = self.catalog.creature(self.state.creature_id)["index"]
                self.screen = "bestiary"
            elif self.selected == 4:
                self.screen = "network"
            elif self.selected == 5:
                self.screen = "expedition"
            else:
                self.screen = "help"
        if pressed & (self.display.BTN_B | self.display.BTN_POWER):
            return False
        return True

    def _handle_bestiary(self, pressed):
        if pressed & self.display.BTN_LEFT:
            self.bestiary_index = (self.bestiary_index - 1) % 250
        if pressed & self.display.BTN_RIGHT:
            self.bestiary_index = (self.bestiary_index + 1) % 250
        if pressed & self.display.BTN_UP:
            self.bestiary_index = (self.bestiary_index - 5) % 250
        if pressed & self.display.BTN_DOWN:
            self.bestiary_index = (self.bestiary_index + 5) % 250
        if pressed & (self.display.BTN_A | self.display.BTN_B | self.display.BTN_POWER):
            self.screen = "home"
        return True

    def _handle_help(self, pressed):
        if pressed & (self.display.BTN_A | self.display.BTN_B | self.display.BTN_POWER):
            self.screen = "home"
        return True

    def render(self, frame_index):
        message = self.message if time.monotonic() < self.message_until else ""
        if self.screen == "home":
            self.ui.home(
                self.state,
                self.selected,
                self._current_pose(),
                frame_index,
                message,
            )
        elif self.screen == "bestiary":
            self.ui.bestiary(self.state, self.bestiary_index, frame_index)
        elif self.screen in ("network", "upload_confirm"):
            self.ui.network(self.state, self.network_selected, self.network_message,
                            self.worker is not None, self.screen == "upload_confirm")
        elif self.screen in ("visit", "visit_report"):
            self.ui.visit(self.state, self.visit_networks, self.visit_selected,
                          self.visit_message, self.worker is not None,
                          self.visit_report if self.screen == "visit_report" else None)
        elif self.screen in ("wdgwars", "wdgwars_confirm", "wdgwars_history"):
            self.ui.wdgwars(self.state, self.sync_history_offset if self.screen == "wdgwars_history" else self.sync_selected,
                           self.sync_mode, self.sync_status,
                           self.worker is not None, self.screen)
        elif self.screen == "expedition":
            self.ui.expedition(self.state, self.journal.summary if self.journal else None,
                               self.expedition_message, frame_index, self._current_pose())
        else:
            self.ui.help(self.state)

    def run(self, max_frames=None):
        running = True
        frame = 0
        try:
            while running:
                self._drain_sync_progress()
                self._finish_network_job()
                self._tick_expedition()
                _current, pressed, _released = self.display.poll_input()
                if self.screen == "home":
                    running = self._handle_home(pressed)
                elif self.screen == "bestiary":
                    running = self._handle_bestiary(pressed)
                elif self.screen in ("network", "upload_confirm"):
                    running = self._handle_network(pressed)
                elif self.screen in ("visit", "visit_report"):
                    running = self._handle_visit(pressed)
                elif self.screen in ("wdgwars", "wdgwars_confirm", "wdgwars_history"):
                    running = self._handle_wdgwars(pressed)
                elif self.screen == "expedition":
                    running = self._handle_expedition(pressed)
                else:
                    running = self._handle_help(pressed)
                if self.screen != "expedition" or frame % 2 == 0:
                    self.render(frame // 2 if self.screen == "expedition" else frame)
                frame += 1
                if max_frames is not None and frame >= max_frames:
                    break
                self.display.delay(125)
        finally:
            self.sync_cancel.set()
            if self.pump is not None:
                self.pump.stop()
            if self.worker is not None:
                self.worker.join()
                self._finish_network_job()
            if self.pump is not None:
                self.pump.stop(wait=True)
                self._tick_expedition()
                if self.journal is not None and self.journal.summary["status"] != "ended":
                    self.journal.status("paused")
            self.state.apply_elapsed_time(int(self.clock()))
            self.store.save(self.state)


def run_on_pager(library_path=None, data_dir=None):
    catalog = CreatureCatalog.load_default()
    data_dir = data_dir or os.environ.get("HACKOMON_DATA_DIR", "/mmc/root/hackomon")
    store = StateStore(data_dir)
    with PagerDisplay(library_path) as display:
        HackomonApp(display, catalog, store).run()

