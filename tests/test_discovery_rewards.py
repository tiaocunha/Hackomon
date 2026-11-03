import queue
import unittest
from unittest.mock import MagicMock, patch

from tests import support
from tests.test_networks import observation
from hackomon.app import HackomonApp
from hackomon.catalog import CreatureCatalog
from hackomon.exploration import record_observations, reward_discoveries
from hackomon.model import GameState
from hackomon.pager_backend import MemoryDisplay
from hackomon.storage import StateStore


NOW = 1700000000


def unlocated(index=1, kind="WIFI", stamp=NOW):
    item = observation(index, kind)
    for key in ("lat", "lon", "accuracy", "altitude"):
        item.pop(key)
    item["timestamp"] = stamp
    return item


class DiscoveryRewardTests(unittest.TestCase):
    def setUp(self):
        self.catalog = CreatureCatalog.load_default()
        self.state = GameState.new(self.catalog, now=NOW)

    def test_without_gps_wifi_and_ble_earn_once_without_map_points_or_care(self):
        values = [unlocated(), unlocated(2, "BLE")]
        result = reward_discoveries(self.state, values, NOW)
        self.assertEqual((3, 2), (result["xp"], result["new"]))
        self.assertEqual(3, self.state.xp)
        self.assertEqual(0, self.state.care_points)
        self.assertEqual([], self.state.network_queue)
        self.assertEqual({}, self.state.exploration_known)
        self.assertTrue(all(len(key) == 64 for key in self.state.discovery_rewarded))
        self.assertEqual(0, reward_discoveries(self.state, values, NOW + 1)["xp"])

    def test_later_gps_can_queue_same_device_without_paying_twice(self):
        reward_discoveries(self.state, [unlocated()], NOW)
        result = record_observations(self.state, [observation()], NOW)
        self.assertEqual((1, 0), (result["added"], result["xp"]))
        self.assertEqual(2, self.state.xp)
        self.assertEqual(1, len(self.state.network_queue))

    def test_rewards_survive_atomic_save_and_old_save_migration_does_not_repay(self):
        reward_discoveries(self.state, [unlocated()], NOW)
        with support.temporary_directory() as directory:
            store = StateStore(directory)
            store.save(self.state)
            restored, warning = store.load_or_create(self.catalog, now=NOW)
            self.assertIsNone(warning)
            self.assertEqual(0, reward_discoveries(restored, [unlocated()], NOW)["xp"])
        old = GameState.new(self.catalog, now=NOW)
        record_observations(old, [observation(5)], NOW)
        raw = old.to_dict()
        raw.pop("discovery_rewarded")
        migrated = GameState.from_dict(raw, self.catalog)
        self.assertEqual(0, reward_discoveries(migrated, [unlocated(5)], NOW)["xp"])
        self.assertEqual(2, reward_discoveries(migrated, [unlocated(6)], NOW)["xp"])

    def test_no_daily_cap_and_next_day_does_not_farm_existing_addresses(self):
        result = reward_discoveries(self.state, [unlocated(i) for i in range(100)], NOW)
        self.assertEqual(200, result["xp"])
        self.assertEqual(2, reward_discoveries(self.state, [unlocated(200)], NOW)["xp"])
        self.assertEqual(202, self.state.exploration_daily_xp)
        tomorrow = NOW + 86400
        self.assertEqual(0, reward_discoveries(self.state, [unlocated(1, stamp=tomorrow)], tomorrow)["xp"])
        self.assertEqual(2, reward_discoveries(self.state, [unlocated(300, stamp=tomorrow)], tomorrow)["xp"])

    def test_an_old_save_at_120_can_earn_more_today_without_resetting_progress(self):
        reward_discoveries(self.state, [], NOW)
        self.state.xp = 147
        self.state.exploration_daily_xp = 120
        self.state.exploration_xp = 120
        restored = GameState.from_dict(self.state.to_dict(), self.catalog)
        result = reward_discoveries(restored, [unlocated(), unlocated(2, "BLE")], NOW)
        self.assertEqual(3, result["xp"])
        self.assertEqual((150, 123, 123), (restored.xp, restored.exploration_daily_xp, restored.exploration_xp))
        self.assertEqual(0, reward_discoveries(restored, [unlocated(), unlocated(2, "BLE")], NOW)["xp"])

    def test_stale_future_invalid_signal_and_optout_never_earn(self):
        values = [unlocated(stamp=NOW - 61), unlocated(2, stamp=NOW + 10),
                  dict(unlocated(3), mac="00:00:00:00:00:00"),
                  dict(unlocated(4), rssi=127), dict(unlocated(5), name="Private_optout")]
        result = reward_discoveries(self.state, values, NOW)
        self.assertEqual((0, 4, 1), (result["xp"], result["invalid"], result["excluded"]))
        self.assertFalse(self.state.discovery_rewarded)

    def test_full_map_queue_does_not_block_new_offline_xp(self):
        record_observations(self.state, [observation(i) for i in range(500)], NOW)
        tomorrow = NOW + 86400
        result = reward_discoveries(self.state, [unlocated(1000, stamp=tomorrow)], tomorrow)
        self.assertEqual(2, result["xp"])
        self.assertEqual(500, len(self.state.network_queue))

    def test_corrupt_reward_ledger_is_rejected(self):
        raw = self.state.to_dict()
        raw["discovery_rewarded"] = {"not a hash": "2026-11-03"}
        with self.assertRaises(ValueError):
            GameState.from_dict(raw, self.catalog)

    def test_expedition_updates_visible_xp_without_creating_csv_or_upload_queue(self):
        with support.temporary_directory() as directory:
            app = HackomonApp(MemoryDisplay(), self.catalog, StateStore(directory), clock=lambda: NOW)
            pump = MagicMock()
            pump.events = queue.Queue()
            with patch("hackomon.app.expedition.Pump", return_value=pump):
                app._start_expedition()
            values = [unlocated(), unlocated(2, "BLE")]
            pump.events.put(("observations", values))
            app._tick_expedition()
            self.assertEqual((3, 3), (app.state.xp, app.journal.summary["xp"]))
            self.assertEqual(2, app.journal.summary["unlocated"])
            self.assertFalse((app.journal.folder / "discoveries.csv").exists())
            self.assertFalse(app.state.network_queue)
            pump.events.put(("observations", values))
            app._tick_expedition()
            self.assertEqual((3, 3), (app.state.xp, app.journal.summary["xp"]))
