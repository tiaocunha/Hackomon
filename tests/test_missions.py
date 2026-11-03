import queue
import unittest
from unittest.mock import MagicMock, patch

from tests import support
from tests.test_networks import observation
from tests.test_expedition import fix
from hackomon import missions
from hackomon.app import HackomonApp
from hackomon.catalog import CreatureCatalog
from hackomon.expedition import Journal
from hackomon.exploration import reward_discoveries
from hackomon.model import GameState
from hackomon.pager_backend import MemoryDisplay
from hackomon.storage import StateStore


NOW = 1700000000


class MissionTests(unittest.TestCase):
    def setUp(self):
        self.catalog = CreatureCatalog.load_default()
        self.state = GameState.new(self.catalog, now=NOW)

    def test_only_new_valid_discoveries_advance_and_medals_do_not_repay_xp(self):
        summary = {"distance_m": 0}
        values = [observation(i, kind) for kind in ("WIFI", "BLE") for i in range(5)]
        reward = reward_discoveries(self.state, values, NOW)
        self.assertEqual({"WIFI": 5, "BLE": 5}, reward["new_by_type"])
        self.assertEqual(["Primeiro olhar", "Dois mundos"], missions.record(self.state, summary, reward))
        self.assertEqual(15, self.state.xp)
        self.assertEqual(0, self.state.care_points)
        before = dict(summary["mission_progress"])
        again = reward_discoveries(self.state, values, NOW)
        self.assertEqual([], missions.record(self.state, summary, again))
        self.assertEqual(before, summary["mission_progress"])
        self.assertEqual(15, self.state.xp)

    def test_invalid_stale_excluded_and_multicast_do_not_progress(self):
        summary = {}
        values = [dict(observation(), timestamp=NOW - 61), dict(observation(2), rssi=127),
                  dict(observation(3), name="private_optout"), dict(observation(4), mac="01:00:00:00:00:01")]
        reward = reward_discoveries(self.state, values, NOW)
        self.assertEqual([], missions.record(self.state, summary, reward))
        self.assertEqual({"discoveries": 0, "wifi": 0, "ble": 0}, summary["mission_progress"])

    def test_validated_distance_awards_once_while_jumps_and_stationary_fixes_do_not(self):
        with support.temporary_directory() as directory:
            journal = Journal(directory, now=NOW)
            journal.gps(fix())
            journal.gps(fix(NOW + 1, lon=40))
            self.assertEqual([], missions.record(self.state, journal.summary))
            journal.status("paused")
            journal.status("running")
            for index in range(22):
                journal.gps(fix(NOW + 100 + index * 10, lat=-23.5 + index * .0005))
            self.assertGreater(journal.summary["distance_m"], 1000)
            self.assertEqual(["Passo explorador"], missions.record(self.state, journal.summary))
            self.assertEqual([], missions.record(self.state, journal.summary))
            self.assertEqual(0, self.state.xp)
            journal.status("ended")
            self.assertIn("Passo explorador", (journal.folder / "summary.txt").read_text(encoding="utf-8"))

    def test_progress_and_medals_survive_restart_without_repeating_on_a_new_outing(self):
        with support.temporary_directory() as directory:
            journal = Journal(directory, now=NOW)
            reward = reward_discoveries(self.state, [observation(i) for i in range(10)], NOW)
            missions.record(self.state, journal.summary, reward)
            journal.checkpoint()
            store = StateStore(directory)
            store.save(self.state)
            restored, warning = store.load_or_create(self.catalog, now=NOW)
            self.assertIsNone(warning)
            summary = Journal.restore(directory).summary
            self.assertEqual(10, summary["mission_progress"]["discoveries"])
            self.assertEqual(["first_look"], restored.field_badges)
            self.assertEqual([], missions.record(restored, summary))
            self.assertTrue(missions.cards(restored, {"distance_m": 0})[0]["earned"])

    def test_old_save_migrates_without_inventing_medals_or_new_discoveries(self):
        raw = self.state.to_dict()
        raw.pop("field_badges")
        restored = GameState.from_dict(raw, self.catalog)
        self.assertEqual([], restored.field_badges)
        summary = dict(wifi=999, ble=999, rewarded_discoveries=2000, distance_m=0)
        self.assertEqual([], missions.record(restored, summary))
        self.assertEqual(0, summary["mission_progress"]["discoveries"])

    def test_corrupt_medals_and_progress_are_rejected(self):
        for value in ("first_look", ["unknown"], ["first_look", "first_look"], [None]):
            with self.subTest(value=value):
                raw = self.state.to_dict()
                raw["field_badges"] = value
                with self.assertRaises(ValueError):
                    GameState.from_dict(raw, self.catalog)
        with support.temporary_directory() as directory:
            journal = Journal(directory, now=NOW)
            journal.summary["mission_progress"] = {"wifi": -1}
            journal.checkpoint()
            with self.assertRaises(ValueError):
                Journal.restore(directory)

    def test_every_family_has_a_short_distinct_discovery_voice(self):
        lines = set()
        for family in self.catalog.families:
            line = missions.speech({"family_id": family["id"]}, "discovery")
            self.assertLessEqual(len(line), 27)
            lines.add(line)
        self.assertEqual(10, len(lines))
        self.assertIn("Sem GPS", missions.speech(self.catalog.creatures[0], "gps_lost"))

    def test_mission_page_and_event_reactions_do_not_start_any_extra_job(self):
        with support.temporary_directory() as directory:
            app = HackomonApp(MemoryDisplay(), self.catalog, StateStore(directory), clock=lambda: NOW)
            pump = MagicMock()
            pump.events = queue.Queue()
            pump.alive.return_value = True
            with patch("hackomon.app.expedition.Pump", return_value=pump):
                app._start_expedition()
            pump.events.put(("observations", [observation(i) for i in range(10)]))
            app._tick_expedition()
            self.assertEqual(["first_look"], app.state.field_badges)
            self.assertIn("medalha", app.companion_line)
            app.screen = "expedition"
            app._handle_expedition(app.display.BTN_DOWN)
            app._handle_expedition(app.display.BTN_DOWN)
            self.assertEqual(2, app.expedition_page)
            app.render(0)
            self.assertIsNone(app.worker)
            pump.pause.assert_not_called()
            texts = [op[3] for op in app.display.operations if op[0] == "text"]
            self.assertIn("MISSOES DE EXPLORACAO", texts)
            self.assertIn("MEDALHA CONQUISTADA", texts)
            for op in app.display.operations:
                if op[0] == "text":
                    self.assertLessEqual(op[1] + app.display.text_width(op[3], op[5]), 480, op)
                    self.assertLessEqual(op[2] + 8 * op[5], 222, op)


if __name__ == "__main__":
    unittest.main()
