import copy
import json
import queue
import random
import unittest
from unittest.mock import MagicMock, patch

from tests import support
from hackomon import generations as life, progression
from hackomon.app import HackomonApp
from hackomon.catalog import CreatureCatalog
from hackomon.evolution import GATES, advance_one_if_ready
from hackomon.missions import cards, record
from hackomon.model import GameState
from hackomon.pager_backend import MemoryDisplay
from hackomon.storage import StateStore

NOW = 1700000000


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.catalog = CreatureCatalog.load_default()
        self.state = GameState.new(self.catalog, line_id="slime-lumen", now=NOW)
        self.summary = dict(id="1" * 32, status="running", distance_m=0)
        progression.reset_activity(self.summary)
        life.begin_field(self.state, self.summary)

    def tick(self, seconds, distance=0):
        self.summary["field_progress"]["activity_seconds"] += seconds
        self.summary["distance_m"] += distance
        return progression.field_rewards(self.state, self.summary, NOW + self.summary["field_progress"]["activity_seconds"])

    def adult(self):
        self.state.stage = 3
        self.state.creature_id = self.catalog.creature_for_stage(self.state.line_id, 3)["id"]
        self.state.branch_locked = True
        self.state.care_points = 20
        progression.grant(self.state, progression.threshold(16))

    def successor(self):
        self.tick(life.EGG_PREPARATION)
        life.ensure_egg_offers(self.state, self.catalog, random.Random(1))
        life.select_egg(self.state, self.state.egg_offers[0])
        self.tick(life.EGG_INCUBATION)

    def test_old_save_migration_preserves_pet_and_creates_permanent_career_without_age(self):
        raw = self.state.to_dict()
        for field in list(raw):
            if field in {"generations_revision", "trainer_xp", "trainer_level", "trainer_level_credit", "generation",
                         "life_status", "life_active_seconds", "adult_active_seconds", "pet_contacts", "pet_distance_m",
                         "life_field_receipt", "birth_line_id", "hatched_lines", "pet_badges", "affinities", "heritage_trait",
                         "branch_locked", "branch_pending", "branch_offers", "egg_activity_seconds", "egg_incubation_seconds",
                         "egg_offers", "egg_line_id", "memorial_total", "memorial"}:
                raw.pop(field)
        raw.update(xp=1230, level=42, level_credit=4510, care_points=6,
                   stage=1, creature_id=self.catalog.creature_for_stage("slime-lumen", 1)["id"],
                   field_badges=["first_look", "two_worlds", "explorer"])
        state = GameState.from_dict(raw, self.catalog)
        self.assertEqual((1230, 42, 1230, 42), (state.xp, state.level, state.trainer_xp, state.trainer_level))
        self.assertEqual((1, 0, 0), (state.generation, state.life_active_seconds, state.adult_active_seconds))
        self.assertEqual(raw["field_badges"], state.pet_badges)
        self.assertFalse(state.branch_locked)
        state.apply_elapsed_time(NOW + 86400)
        self.assertEqual(0, state.life_active_seconds)
        restored = GameState.from_dict(state.to_dict(), self.catalog)
        self.assertEqual(state.trainer_level_credit, restored.trainer_level_credit)

    def test_existing_later_forms_are_not_forced_to_choose_a_new_branch(self):
        raw = self.state.to_dict()
        raw.pop("generations_revision")
        raw.update(stage=2, creature_id=self.catalog.creature_for_stage("slime-lumen", 2)["id"])
        restored = GameState.from_dict(raw, self.catalog)
        self.assertTrue(restored.branch_locked)
        self.assertEqual("slime-lumen", restored.line_id)

    def test_juvenile_age_does_not_consume_adult_life_and_pause_offline_do_not_age(self):
        self.tick(10000)
        self.assertEqual((10000, 0), (self.state.life_active_seconds, self.state.adult_active_seconds))
        self.summary["status"] = "paused"
        before = self.state.life_active_seconds
        progression.field_rewards(self.state, self.summary, NOW + 99999, observed=True)
        self.state.apply_elapsed_time(NOW + 99999)
        self.assertEqual(before, self.state.life_active_seconds)

    def test_veteran_death_and_memorial_happen_once_and_only_trainer_keeps_earning(self):
        self.adult()
        self.assertEqual("veteran", self.tick(life.VETERAN_AT)["life_event"])
        self.assertEqual("Veterano", life.age_label(self.state))
        self.assertEqual("", self.tick(life.ADULT_LIFETIME - life.VETERAN_AT - 1)["life_event"])
        self.assertEqual("ended", self.tick(1)["life_event"])
        self.assertEqual(("memorial", 1, 1), (self.state.life_status, self.state.memorial_total, len(self.state.memorial)))
        final_xp = self.state.xp
        trainer_xp = self.state.trainer_xp
        self.tick(600, 500)
        self.assertEqual(final_xp, self.state.xp)
        self.assertGreater(self.state.trainer_xp, trainer_xp)
        self.assertEqual(1, len(self.state.memorial))
        self.assertFalse(self.state.perform_care("play", NOW + 99999).accepted)
        self.assertFalse(advance_one_if_ready(self.state, self.catalog).evolved)

    def test_egg_offers_persist_prioritize_unhatched_lines_and_do_not_reroll(self):
        self.assertFalse(life.ensure_egg_offers(self.state, self.catalog))
        self.tick(life.EGG_PREPARATION)
        self.assertTrue(life.ensure_egg_offers(self.state, self.catalog, random.Random(1)))
        original = list(self.state.egg_offers)
        self.assertEqual(3, len(set(original)))
        self.assertNotIn(self.state.birth_line_id, original)
        restored = GameState.from_dict(self.state.to_dict(), self.catalog)
        self.assertFalse(life.ensure_egg_offers(restored, self.catalog, random.Random(99)))
        self.assertEqual(original, restored.egg_offers)
        with self.assertRaises(ValueError):
            life.select_egg(restored, "slime-lumen")

    def test_last_unhatched_line_is_offered_and_completed_collection_can_repeat(self):
        self.state.egg_activity_seconds = life.EGG_PREPARATION
        self.state.hatched_lines = [line["id"] for line in self.catalog.lines[:-1]]
        life.ensure_egg_offers(self.state, self.catalog)
        self.assertEqual([self.catalog.lines[-1]["id"]], self.state.egg_offers)
        self.state.hatched_lines.append(self.catalog.lines[-1]["id"])
        self.state.egg_offers = []
        life.ensure_egg_offers(self.state, self.catalog)
        self.assertEqual(3, len(self.state.egg_offers))

    def test_ready_egg_cannot_replace_living_pet_and_birth_preserves_career_and_cooldowns(self):
        self.adult()
        self.successor()
        self.assertFalse(life.birth_ready(self.state))
        with self.assertRaises(ValueError):
            life.birth(self.state, self.catalog, NOW, self.summary)
        self.tick(life.ADULT_LIFETIME - self.state.adult_active_seconds)
        self.assertTrue(life.birth_ready(self.state))
        self.state.revisit_rewarded_at = {"a" * 64: NOW}
        career = self.state.trainer_xp, self.state.trainer_level
        receipts = copy.deepcopy(self.state.field_bonus_receipt)
        former = self.state.creature_id
        self.state.discovered.append(former)
        new_line = self.state.egg_line_id
        life.birth(self.state, self.catalog, NOW + 99999, self.summary)
        self.assertEqual(career, (self.state.trainer_xp, self.state.trainer_level))
        self.assertEqual((2, 0, 1, 0, 0), (self.state.generation, self.state.stage, self.state.level, self.state.xp, self.state.field_bond))
        self.assertEqual(new_line, self.state.birth_line_id)
        self.assertEqual(receipts, self.state.field_bonus_receipt)
        self.assertEqual({"a" * 64: NOW}, self.state.revisit_rewarded_at)
        self.assertIn(former, self.state.discovered)
        self.assertEqual(1, len(self.state.memorial))
        self.assertEqual(0, self.state.life_active_seconds)
        self.assertEqual(0, progression.field_rewards(self.state, self.summary, NOW + 99999)["xp"])
        restored = GameState.from_dict(self.state.to_dict(), self.catalog)
        self.assertEqual(2, restored.generation)

    def test_branch_choice_is_explicit_stays_in_family_and_locks_future_forms(self):
        progression.grant(self.state, progression.threshold(25))
        self.state.care_points = 35
        self.assertTrue(advance_one_if_ready(self.state, self.catalog).evolved)
        self.assertFalse(advance_one_if_ready(self.state, self.catalog).evolved)
        self.assertTrue(self.state.branch_pending)
        self.assertIn(self.state.line_id, self.state.branch_offers)
        self.assertEqual(3, len(self.state.branch_offers))
        self.assertTrue(all(self.catalog.evolution_line(key)["family_id"] == "slime" for key in self.state.branch_offers))
        old = self.state.creature_id
        chosen = self.state.branch_offers[1]
        with self.assertRaises(ValueError):
            advance_one_if_ready(self.state, self.catalog, selected_line="mammal-fox")
        result = advance_one_if_ready(self.state, self.catalog, selected_line=chosen)
        self.assertTrue(result.evolved)
        self.assertEqual((chosen, 2, True), (self.state.line_id, self.state.stage, self.state.branch_locked))
        self.assertEqual("slime-lumen", self.state.birth_line_id)
        self.assertIn(old, self.state.discovered)
        for stage in (3, 4):
            self.assertTrue(advance_one_if_ready(self.state, self.catalog).evolved)
            self.assertEqual(self.catalog.creature_for_stage(chosen, stage)["id"], self.state.creature_id)

    def test_affinities_influence_suggestions_but_current_path_remains_accessible(self):
        life.add_affinity(self.state, "companionship", 30)
        life.prepare_branch(self.state, self.catalog)
        self.assertEqual("slime-lumen", self.state.branch_offers[0])
        self.assertEqual("companionship", life.LINE_PROFILES[self.catalog.evolution_line(self.state.branch_offers[1])["family_line_index"]])

    def test_parent_mission_progress_cannot_be_claimed_by_newborn_after_partial_checkpoint(self):
        self.adult()
        self.successor()
        self.tick(life.ADULT_LIFETIME - self.state.adult_active_seconds)
        stale = dict(mission_progress=dict(discoveries=50, wifi=25, ble=25), distance_m=10000, mission_generation=1)
        life.birth(self.state, self.catalog, NOW)
        self.assertEqual(0, cards(self.state, stale)[0]["value"])
        # Distance medal must use the new pet's distance, not the parent's route.
        earned = record(self.state, stale)
        self.assertNotIn("Primeiro olhar", earned)
        self.assertNotIn("Dois mundos", earned)
        self.assertNotIn("Passo explorador", earned)

    def test_confirm_birth_disk_failure_keeps_old_pet_and_ready_egg(self):
        self.adult()
        self.successor()
        self.tick(life.ADULT_LIFETIME - self.state.adult_active_seconds)
        with support.temporary_directory() as directory:
            store = StateStore(directory)
            store.save(self.state)
            app = HackomonApp(MemoryDisplay(), self.catalog, store, clock=lambda: NOW)
            app.generation_confirm = "birth"
            with patch.object(store, "save", side_effect=OSError("full")):
                app._handle_generations(app.display.BTN_A)
            self.assertEqual((1, "memorial"), (app.state.generation, app.state.life_status))
            restored, warning = store.load_or_create(self.catalog, now=NOW)
            self.assertIsNone(warning)
            self.assertTrue(life.birth_ready(restored))

    def test_all_new_screens_and_confirmations_fit_the_pager(self):
        self.state.egg_activity_seconds = life.EGG_PREPARATION
        life.ensure_egg_offers(self.state, self.catalog, random.Random(1))
        progression.grant(self.state, progression.threshold(8))
        self.state.care_points = 10
        advance_one_if_ready(self.state, self.catalog)
        advance_one_if_ready(self.state, self.catalog)
        with support.temporary_directory() as directory:
            app = HackomonApp(MemoryDisplay(), self.catalog, StateStore(directory), clock=lambda: NOW)
            app.state = self.state
            app.screen = "generations"
            for tab in range(4):
                app.generation_tab = tab
                app.display.operations.clear()
                app.render(0)
                for op in app.display.operations:
                    if op[0] == "text":
                        self.assertLessEqual(op[1] + app.display.text_width(op[3], op[5]), 480, op)
                        self.assertLessEqual(op[2] + 8 * op[5], 222, op)
            app.generation_tab = 3
            app._handle_generations(app.display.BTN_A)
            self.assertEqual("branch", app.generation_confirm)
            app._handle_generations(app.display.BTN_B)
            self.assertTrue(app.state.branch_pending)
            self.assertEqual("", app.generation_confirm)

    def test_first_load_creates_one_pre_generation_backup_without_overwriting_it(self):
        with support.temporary_directory() as directory:
            store = StateStore(directory)
            raw = self.state.to_dict()
            raw.pop("generations_revision")
            raw.update(xp=1230, level=42, level_credit=4510)
            store.path.write_text(json.dumps(raw), encoding="utf-8")
            state, warning = store.load_or_create(self.catalog, now=NOW)
            self.assertIsNone(warning)
            backup = store.data_dir / "state.json.before-generations-v1"
            original = backup.read_bytes()
            self.assertEqual(1230, json.loads(original)["xp"])
            progression.grant(state, 50)
            store.save(state)
            store.load_or_create(self.catalog, now=NOW)
            self.assertEqual(original, backup.read_bytes())
            self.assertEqual(1280, state.trainer_xp)

    def test_egg_and_memorial_resume_after_restart_then_ui_birth_commits_new_life(self):
        self.adult()
        self.successor()
        self.tick(life.ADULT_LIFETIME - self.state.adult_active_seconds)
        with support.temporary_directory() as directory:
            store = StateStore(directory)
            store.save(self.state)
            app = HackomonApp(MemoryDisplay(), self.catalog, store, clock=lambda: NOW)
            original_career = app.state.trainer_xp
            app.screen = "generations"
            app.generation_tab = 1
            app._handle_generations(app.display.BTN_A)
            self.assertEqual("birth", app.generation_confirm)
            app.render(0)
            app._handle_generations(app.display.BTN_A)
            self.assertEqual((2, "alive", 1), (app.state.generation, app.state.life_status, app.state.level))
            self.assertEqual(original_career, app.state.trainer_xp)
            restored, warning = store.load_or_create(self.catalog, now=NOW)
            self.assertIsNone(warning)
            self.assertEqual(2, restored.generation)
            self.assertEqual(1, len(restored.memorial))

    def test_egg_selection_write_failure_does_not_create_an_uncommitted_choice(self):
        self.state.egg_activity_seconds = life.EGG_PREPARATION
        life.ensure_egg_offers(self.state, self.catalog)
        with support.temporary_directory() as directory:
            app = HackomonApp(MemoryDisplay(), self.catalog, StateStore(directory), clock=lambda: NOW)
            app.state = self.state
            app.generation_tab = 1
            with patch.object(app.store, "save", side_effect=OSError("full")):
                app._handle_generations(app.display.BTN_A)
            self.assertEqual("", app.state.egg_line_id)

    def test_corrupted_lifecycle_fields_are_rejected(self):
        for key, value in (("life_status", "unknown"), ("adult_active_seconds", -1),
                           ("egg_activity_seconds", life.EGG_PREPARATION + 1),
                           ("egg_line_id", "not-an-offer"), ("heritage_trait", "superpower"),
                           ("branch_pending", True), ("memorial_total", 4),
                           ("pet_badges", [["bad"]])):
            with self.subTest(key=key):
                raw = self.state.to_dict()
                raw[key] = value
                with self.assertRaises(ValueError):
                    GameState.from_dict(raw, self.catalog)

    def test_all_250_existing_forms_remain_reachable_through_base_choices(self):
        seen = set()
        for line in self.catalog.lines:
            state = GameState.new(self.catalog, line_id=line["id"], now=NOW)
            progression.grant(state, progression.threshold(25))
            state.care_points = 35
            seen.add(state.creature_id)
            for stage in range(1, 5):
                result = advance_one_if_ready(state, self.catalog)
                if state.branch_pending:
                    self.assertIn(line["id"], state.branch_offers)
                    result = advance_one_if_ready(state, self.catalog, selected_line=line["id"])
                self.assertTrue(result.evolved)
                self.assertEqual(line["creature_ids"][stage], state.creature_id)
                seen.add(state.creature_id)
        self.assertEqual(250, len(seen))

    def test_long_career_retains_bestiary_and_bounded_memorial_details(self):
        for _ in range(life.MEMORIAL_LIMIT + 1):
            self.adult()
            self.tick(life.ADULT_LIFETIME)
            life.ensure_egg_offers(self.state, self.catalog)
            life.select_egg(self.state, self.state.egg_offers[0])
            self.tick(life.EGG_INCUBATION)
            life.birth(self.state, self.catalog, NOW, self.summary)
        self.assertEqual(life.MEMORIAL_LIMIT, len(self.state.memorial))
        self.assertEqual(life.MEMORIAL_LIMIT + 1, self.state.memorial_total)
        self.assertEqual(life.MEMORIAL_LIMIT + 2, self.state.generation)
        self.assertEqual(50, len(self.state.hatched_lines))
        self.assertEqual(50, len(set(self.state.discovered)))
        restored = GameState.from_dict(self.state.to_dict(), self.catalog)
        self.assertEqual(50, len(restored.hatched_lines))

    def test_medal_from_last_live_observations_is_included_in_memorial(self):
        from tests.test_networks import observation

        self.adult()
        with support.temporary_directory() as directory:
            app = HackomonApp(MemoryDisplay(), self.catalog, StateStore(directory), clock=lambda: NOW)
            app.state = self.state
            pump = MagicMock()
            pump.events = queue.Queue()
            pump.alive.return_value = True
            with patch("hackomon.app.expedition.Pump", return_value=pump):
                app._start_expedition()
            value = app.journal.summary["field_progress"]
            value.update(activity_seconds=life.ADULT_LIFETIME - 10, last_activity_at=NOW - 10)
            app.state.life_active_seconds = app.state.adult_active_seconds = life.ADULT_LIFETIME - 10
            app.state.life_field_receipt["seconds"] = life.ADULT_LIFETIME - 10
            app.state.field_bonus_receipt = dict(id=app.journal.summary["id"], activity=59, distance=0)
            pump.events.put(("observations", [observation(i) for i in range(10)]))
            app._tick_expedition()
            self.assertEqual("memorial", app.state.life_status)
            self.assertIn("first_look", app.state.memorial[-1]["medals"])


if __name__ == "__main__":
    unittest.main()
