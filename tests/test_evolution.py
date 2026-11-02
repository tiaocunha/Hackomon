import unittest

from tests import support  # noqa: F401
from hackomon.catalog import CreatureCatalog
from hackomon.evolution import GATES, advance_one_if_ready
from hackomon.model import GameState


class EvolutionTests(unittest.TestCase):
    def setUp(self):
        self.catalog = CreatureCatalog.load_default()
        self.line_id = self.catalog.lines[0]["id"]
        self.state = GameState.new(self.catalog, line_id=self.line_id, now=100)

    def test_all_five_stages_are_reachable_without_skipping(self):
        for target_stage in range(1, 5):
            gate = GATES[target_stage]
            self.state.level = gate["level"]
            self.state.care_points = gate["care"]
            self.state.hunger = self.state.happiness = self.state.energy = max(70, gate["wellness"])
            result = advance_one_if_ready(self.state, self.catalog)
            self.assertTrue(result.evolved)
            self.assertEqual(target_stage, self.state.stage)
        self.assertEqual(5, len(self.state.discovered))
        self.assertFalse(advance_one_if_ready(self.state, self.catalog).evolved)

    def test_gate_rejects_insufficient_care(self):
        self.state.level = 99
        self.state.care_points = 0
        self.state.hunger = self.state.happiness = self.state.energy = 100
        result = advance_one_if_ready(self.state, self.catalog)
        self.assertFalse(result.evolved)
        self.assertEqual(0, self.state.stage)


if __name__ == "__main__":
    unittest.main()

