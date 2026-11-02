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
from .ui import HackomonUI
from .exploration import export_csv, record_observations
from .network_config import load_config
from . import lab, radio, wdgwars


ACTION_KEYS = ("feed", "play", "rest")


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

    def _network_job(self, action):
        if self.worker is not None:
            return
        snapshot = list(self.state.network_queue)
        def work():
            try:
                config = load_config(self.store.data_dir)
                if action in ("WIFI", "BLE"):
                    result = radio.discover(action, config.get("wifi_interface", ""))
                elif action == "upload":
                    result = wdgwars.upload(snapshot, config.get("wdgwars_api_key", ""))
                elif action == "export":
                    path = Path(self.store.data_dir) / "discoveries.csv"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open("wb") as handle:
                        handle.write(export_csv(snapshot))
                    result = "CSV salvo em discoveries.csv"
                elif action == "capture":
                    result = lab.capture(config, self.store.data_dir)
                else:
                    result = lab.test_dictionary(config, self.store.data_dir)
                self.results.put((action, result, None))
            except Exception as error:
                # Never put credentials, tool output or server response bodies on screen/log.
                safe = str(error) if isinstance(error, RuntimeError) else "Falha local; confira configuracao"
                self.results.put((action, None, safe))
        self.network_message = "Trabalhando... aguarde (max. 35s)"
        self.worker = threading.Thread(target=work, daemon=False)
        self.worker.start()

    def _finish_network_job(self):
        try:
            action, result, error = self.results.get_nowait()
        except queue.Empty:
            return
        self.worker.join()
        self.worker = None
        if error:
            self.network_message = error
            return
        if action in ("WIFI", "BLE"):
            summary = record_observations(self.state, result, int(self.clock()))
            self.network_message = "%d registros, +%d XP%s" % (
                summary["added"], summary["xp"], " (fila cheia)" if summary["full"] else "")
        elif action == "upload":
            self.state.network_queue = []
            self.network_message = "WDGWars confirmou o recebimento de %d registros" % result
        elif action == "export":
            self.network_message = result
        else:
            self.network_message = result["message"]
            reward = result.get("reward_id")
            if result.get("found") and reward not in self.state.lab_rewards:
                self.state.lab_rewards.append(reward)
                self.state.xp += 10
                self.state.level = min(99, 1 + self.state.xp // 30)
        evolution = advance_one_if_ready(self.state, self.catalog)
        if evolution.evolved:
            self.network_message = "EVOLUCAO! " + self.network_message
            self.display.vibrate(180)
        self.store.save(self.state)

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
            self.network_selected = (self.network_selected - 1) % 6
        if pressed & self.display.BTN_DOWN:
            self.network_selected = (self.network_selected + 1) % 6
        if pressed & self.display.BTN_A:
            action = ("WIFI", "BLE", "export", "upload", "capture", "test")[self.network_selected]
            if action == "upload":
                self.screen = "upload_confirm"
            else:
                self._network_job(action)
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
            self.selected = (self.selected - 1) % 6
        if pressed & self.display.BTN_DOWN:
            self.selected = (self.selected + 1) % 6
        if pressed & self.display.BTN_A:
            if self.selected < 3:
                self._care(ACTION_KEYS[self.selected])
            elif self.selected == 3:
                self.bestiary_index = self.catalog.creature(self.state.creature_id)["index"]
                self.screen = "bestiary"
            elif self.selected == 4:
                self.screen = "network"
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
        else:
            self.ui.help(self.state)

    def run(self, max_frames=None):
        running = True
        frame = 0
        try:
            while running:
                self._finish_network_job()
                _current, pressed, _released = self.display.poll_input()
                if self.screen == "home":
                    running = self._handle_home(pressed)
                elif self.screen == "bestiary":
                    running = self._handle_bestiary(pressed)
                elif self.screen in ("network", "upload_confirm"):
                    running = self._handle_network(pressed)
                else:
                    running = self._handle_help(pressed)
                self.render(frame)
                frame += 1
                if max_frames is not None and frame >= max_frames:
                    break
                self.display.delay(125)
        finally:
            if self.worker is not None:
                self.worker.join()
                self._finish_network_job()
            self.state.apply_elapsed_time(int(self.clock()))
            self.store.save(self.state)


def run_on_pager(library_path=None, data_dir=None):
    catalog = CreatureCatalog.load_default()
    data_dir = data_dir or os.environ.get("HACKOMON_DATA_DIR", "/mmc/root/hackomon")
    store = StateStore(data_dir)
    with PagerDisplay(library_path) as display:
        HackomonApp(display, catalog, store).run()

