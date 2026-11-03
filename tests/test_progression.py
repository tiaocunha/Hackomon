import datetime
import queue
import unittest
from unittest.mock import MagicMock, patch

from tests import support
from tests.test_networks import observation
from hackomon import progression
from hackomon.app import HackomonApp
from hackomon.catalog import CreatureCatalog
from hackomon.evolution import advance_one_if_ready, gate_status
from hackomon.expedition import Journal
from hackomon.exploration import reward_discoveries
from hackomon.model import GameState
from hackomon.pager_backend import MemoryDisplay
from hackomon.storage import StateStore

NOW = 1700000000


def sample(stamp=NOW, index=1, kind="WIFI"):
    return dict(observation(index, kind), timestamp=stamp)


def session(distance=0):
    summary = dict(id="1" * 32, status="running", distance_m=distance)
    progression.reset_activity(summary)
    return summary


class ProgressionTests(unittest.TestCase):
    def setUp(self):
        self.catalog = CreatureCatalog.load_default()
        self.state = GameState.new(self.catalog, now=NOW)

    def test_revisit_boundary_duplicate_samples_and_type_separation(self):
        values = [sample(kind=kind) for kind in ("WIFI", "BLE")]
        self.assertEqual(3, reward_discoveries(self.state, values, NOW)["xp"])
        early = NOW + progression.REVISIT_SECONDS - 1
        self.assertEqual(0, reward_discoveries(self.state, [sample(early, kind=kind) for kind in ("WIFI", "BLE")], early)["xp"])
        ready = early + 1
        values = [sample(ready, kind=kind) for kind in ("WIFI", "BLE")]
        reward = reward_discoveries(self.state, values * 3, ready)
        self.assertEqual((2, 2, 0), (reward["xp"], reward["revisited"], reward["new"]))
        self.assertEqual({"WIFI": 0, "BLE": 0}, reward["new_by_type"])
        self.assertEqual(5, self.state.xp)

    def test_revisit_receipts_survive_restart_and_rollback_does_not_pay(self):
        reward_discoveries(self.state, [sample()], NOW)
        ready = NOW + progression.REVISIT_SECONDS
        reward_discoveries(self.state, [sample(ready)], ready)
        with support.temporary_directory() as directory:
            store = StateStore(directory)
            store.save(self.state)
            restored, warning = store.load_or_create(self.catalog, now=ready)
            self.assertIsNone(warning)
            self.assertEqual(0, reward_discoveries(restored, [sample(ready)], ready)["xp"])
            self.assertEqual(0, reward_discoveries(restored, [sample(NOW + 1)], NOW + 1)["xp"])
            self.assertEqual(3, restored.xp)

    def test_day_change_does_not_bypass_six_hours_and_there_is_no_daily_total_ceiling(self):
        start = int(datetime.datetime(2026, 11, 3, 23, 59, tzinfo=datetime.timezone.utc).timestamp())
        reward_discoveries(self.state, [sample(start)], start)
        self.assertEqual(0, reward_discoveries(self.state, [sample(start + 120)], start + 120)["xp"])
        values = [sample(start + 120, i) for i in range(2, 502)]
        self.assertEqual(1000, reward_discoveries(self.state, values, start + 120)["xp"])

    def test_legacy_award_day_is_not_paid_again_today_and_older_awards_can_revisit(self):
        reward_discoveries(self.state, [sample()], NOW)
        self.state.revisit_rewarded_at = {}
        self.assertEqual(0, reward_discoveries(self.state, [sample()], NOW)["xp"])
        ready = NOW + progression.REVISIT_SECONDS
        self.assertEqual(1, reward_discoveries(self.state, [sample(ready)], ready)["xp"])
        self.state.revisit_rewarded_at = {}
        tomorrow = NOW + 86400
        self.assertEqual(1, reward_discoveries(self.state, [sample(tomorrow)], tomorrow)["xp"])

    def test_invalid_optout_and_stale_samples_do_not_touch_revisit_receipts(self):
        reward_discoveries(self.state, [sample()], NOW)
        before = dict(self.state.revisit_rewarded_at)
        ready = NOW + progression.REVISIT_SECONDS
        values = [dict(sample(ready), rssi=127), dict(sample(ready), name="home_optout"), sample(NOW)]
        self.assertEqual(0, reward_discoveries(self.state, values, ready)["xp"])
        self.assertEqual(before, self.state.revisit_rewarded_at)

    def test_full_ledger_still_pays_existing_revisits_without_growing_memory(self):
        with patch("hackomon.exploration.MAX_KNOWN", 2):
            reward_discoveries(self.state, [sample(index=1), sample(index=2)], NOW)
            ready = NOW + progression.REVISIT_SECONDS
            reward = reward_discoveries(self.state, [sample(ready), sample(ready, 3)], ready)
        self.assertEqual((1, 1), (reward["xp"], reward["blocked"]))
        self.assertEqual(2, len(self.state.revisit_rewarded_at))

    def test_level_curve_boundaries_grow_and_max_level_does_not_cap_xp(self):
        previous_cost = 0
        for level in range(1, progression.MAX_LEVEL):
            boundary = progression.threshold(level + 1)
            self.assertEqual(level, progression.level_for(boundary - 1))
            self.assertEqual(level + 1, progression.level_for(boundary))
            cost = boundary - progression.threshold(level)
            self.assertGreater(cost, previous_cost)
            previous_cost = cost
        progression.grant(self.state, 100000)
        self.assertEqual(100, self.state.level)
        progression.grant(self.state, 10)
        self.assertEqual(100010, self.state.xp)

    def legacy(self, level, xp):
        raw = self.state.to_dict()
        for key in ("progression_revision", "level_credit", "field_bond", "revisit_rewarded_at", "field_bonus_receipt"):
            raw.pop(key)
        raw.update(level=level, xp=xp)
        return raw

    def test_real_level_42_save_retains_xp_stage_medals_and_reaches_next_level_normally(self):
        raw = self.legacy(42, 1230)
        raw.update(stage=1, creature_id=self.catalog.creature_for_stage(self.state.line_id, 1)["id"],
                   care_points=6, field_badges=["first_look", "two_worlds", "explorer"])
        state = GameState.from_dict(raw, self.catalog)
        self.assertEqual((1230, 42, 1, 6, 3), (state.xp, state.level, state.stage, state.care_points, len(state.field_badges)))
        self.assertEqual((0, 245), progression.level_progress(state))
        again = GameState.from_dict(state.to_dict(), self.catalog)
        self.assertEqual(state.level_credit, again.level_credit)
        progression.grant(again, 244)
        self.assertEqual(42, again.level)
        progression.grant(again, 1)
        self.assertEqual((1475, 43), (again.xp, again.level))

    def test_all_legacy_levels_keep_earned_level_and_fractional_progress(self):
        for level in range(1, 100):
            for fraction in (0, 15, 29):
                xp = 30 * (level - 1) + fraction
                state = GameState.from_dict(self.legacy(level, xp), self.catalog)
                self.assertEqual((xp, level), (state.xp, state.level))
                current, needed = progression.level_progress(state)
                self.assertLess(abs(current / needed - fraction / 30), .025)

    def test_fresh_radio_activity_rewards_ten_minutes_once_without_gps(self):
        summary = session()
        total = 0
        for elapsed in range(0, 601, 10):
            total += progression.field_rewards(self.state, summary, NOW + elapsed, observed=True)["xp"]
        self.assertEqual((10, 1, 600), (total, self.state.field_bond, summary["field_progress"]["activity_seconds"]))
        self.assertEqual(0, progression.field_rewards(self.state, summary, NOW + 601)["xp"])
        self.assertEqual(0, self.state.care_points)

    def test_empty_radio_pause_long_gaps_and_restarting_do_not_count_idle_time(self):
        summary = session()
        progression.field_rewards(self.state, summary, NOW, observed=True)
        progression.field_rewards(self.state, summary, NOW + 10, observed=True)
        progression.field_rewards(self.state, summary, NOW + 20, observed=False)
        progression.field_rewards(self.state, summary, NOW + 30, observed=True)
        progression.field_rewards(self.state, summary, NOW + 1000, observed=True)
        summary["status"] = "paused"
        self.assertEqual(0, progression.field_rewards(self.state, summary, NOW + 2000, observed=True)["xp"])
        summary["status"] = "running"
        progression.reset_activity(summary)
        progression.field_rewards(self.state, summary, NOW + 3000, observed=True)
        self.assertEqual(10, summary["field_progress"]["activity_seconds"])

    def test_distance_and_activity_receipts_persist_atomically_with_xp_and_bond(self):
        summary = session()
        summary["distance_m"] = 1000
        summary["field_progress"]["activity_seconds"] = 600
        reward = progression.field_rewards(self.state, summary, NOW)
        self.assertEqual((20, 1), (reward["xp"], reward["bond"]))
        with support.temporary_directory() as directory:
            store = StateStore(directory)
            store.save(self.state)
            restored, warning = store.load_or_create(self.catalog, now=NOW)
            self.assertIsNone(warning)
            self.assertEqual(0, progression.field_rewards(restored, summary, NOW + 1)["xp"])
            self.assertEqual((20, 1), (restored.xp, restored.field_bond))
            summary["distance_m"] = 500
            self.assertEqual(0, progression.field_rewards(restored, summary, NOW + 2)["xp"])
            summary["distance_m"] = 1500
            self.assertEqual(5, progression.field_rewards(restored, summary, NOW + 3)["xp"])

    def test_old_route_is_not_retroactively_paid_and_repeated_positions_pay_nothing(self):
        summary = session(distance=9634)
        for elapsed in range(0, 100, 5):
            self.assertEqual(0, progression.field_rewards(self.state, summary, NOW + elapsed)["xp"])
        summary["distance_m"] = 10100
        self.assertEqual(5, progression.field_rewards(self.state, summary, NOW + 101)["distance_xp"])

    def test_bond_and_care_combine_for_evolution_without_demoting_existing_forms(self):
        state = GameState.from_dict(self.legacy(42, 1230), self.catalog)
        state.care_points = 0
        state.field_bond = 4
        self.assertTrue(advance_one_if_ready(state, self.catalog).evolved)
        state.care_points = 6
        state.field_bond = 3
        self.assertFalse(advance_one_if_ready(state, self.catalog).evolved)
        state.field_bond = 4
        self.assertEqual((10, 10), gate_status(state)["care"])
        self.assertFalse(advance_one_if_ready(state, self.catalog).evolved)
        self.assertTrue(state.branch_pending)
        self.assertTrue(advance_one_if_ready(state, self.catalog, selected_line=state.line_id).evolved)

    def test_invalid_progression_metadata_is_rejected(self):
        for field, value in (("level_credit", -1), ("progression_revision", 999), ("field_bond", "3"),
                             ("revisit_rewarded_at", {"not-a-hash": 1}),
                             ("field_bonus_receipt", {"id": "bad", "activity": 0, "distance": 0})):
            with self.subTest(field=field):
                raw = self.state.to_dict()
                raw[field] = value
                with self.assertRaises(ValueError):
                    GameState.from_dict(raw, self.catalog)
        for field, value in (("revisit_awards", -1), ("xp_breakdown", {"activity": "bad"}),
                             ("field_progress", {"activity_seconds": -1, "distance_baseline": 0})):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    progression.field_progress({field: value})

    def test_app_familiar_route_pays_activity_and_later_revisit_with_clear_breakdown(self):
        with support.temporary_directory() as directory:
            clock = [NOW]
            app = HackomonApp(MemoryDisplay(), self.catalog, StateStore(directory), clock=lambda: clock[0])
            pump = MagicMock()
            pump.events = queue.Queue()
            pump.alive.return_value = True
            with patch("hackomon.app.expedition.Pump", return_value=pump):
                app._start_expedition()
            for elapsed in range(0, 601, 10):
                clock[0] = NOW + elapsed
                item = sample(clock[0])
                for key in ("lat", "lon", "accuracy", "altitude"):
                    item.pop(key)
                pump.events.put(("observations", [item]))
                app._tick_expedition()
            self.assertEqual((12, 1), (app.state.xp, app.state.field_bond))
            clock[0] = NOW + progression.REVISIT_SECONDS
            pump.events.put(("observations", [sample(clock[0])]))
            app._tick_expedition()
            self.assertEqual((13, 13), (app.state.xp, app.journal.summary["xp"]))
            self.assertEqual({"discoveries": 2, "revisits": 1, "activity": 10, "distance": 0}, app.journal.summary["xp_breakdown"])
            self.assertIn("1 revisitas", app.expedition_message)
            self.assertEqual([], app.state.network_queue)


if __name__ == "__main__":
    unittest.main()
