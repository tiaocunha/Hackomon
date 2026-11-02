"""Interactive Pager application loop."""

import os
import time

from .catalog import CreatureCatalog
from .evolution import advance_one_if_ready
from .pager_backend import PagerDisplay
from .storage import StateStore
from .ui import TamaFiUI


ACTION_KEYS = ("feed", "play", "rest")


class TamaFiApp:
    def __init__(self, display, catalog, store, clock=None):
        self.display = display
        self.catalog = catalog
        self.store = store
        self.clock = clock or time.time
        self.state, self.warning = store.load_or_create(catalog, now=int(self.clock()))
        self.ui = TamaFiUI(display, catalog)
        self.selected = 0
        self.screen = "home"
        self.bestiary_index = catalog.creature(self.state.creature_id)["index"]
        self.message = self.warning or ""
        self.message_until = time.monotonic() + (5.0 if self.warning else 0.0)
        self.pose = "idle"
        self.pose_until = 0.0

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
            self.selected = (self.selected - 1) % 5
        if pressed & self.display.BTN_DOWN:
            self.selected = (self.selected + 1) % 5
        if pressed & self.display.BTN_A:
            if self.selected < 3:
                self._care(ACTION_KEYS[self.selected])
            elif self.selected == 3:
                self.bestiary_index = self.catalog.creature(self.state.creature_id)["index"]
                self.screen = "bestiary"
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
        else:
            self.ui.help(self.state)

    def run(self, max_frames=None):
        running = True
        frame = 0
        try:
            while running:
                _current, pressed, _released = self.display.poll_input()
                if self.screen == "home":
                    running = self._handle_home(pressed)
                elif self.screen == "bestiary":
                    running = self._handle_bestiary(pressed)
                else:
                    running = self._handle_help(pressed)
                self.render(frame)
                frame += 1
                if max_frames is not None and frame >= max_frames:
                    break
                self.display.delay(125)
        finally:
            self.state.apply_elapsed_time(int(self.clock()))
            self.store.save(self.state)


def run_on_pager(library_path=None, data_dir=None):
    catalog = CreatureCatalog.load_default()
    data_dir = data_dir or os.environ.get("TAMAFI_DATA_DIR", "/mmc/root/tamafi-reborn")
    store = StateStore(data_dir)
    with PagerDisplay(library_path) as display:
        TamaFiApp(display, catalog, store).run()

