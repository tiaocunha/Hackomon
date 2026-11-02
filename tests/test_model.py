import unittest

from tests import support  # noqa: F401
from tamafi.catalog import CreatureCatalog
from tamafi.model import GameState


class ModelTests(unittest.TestCase):
    def setUp(self):
        catalog = CreatureCatalog.load_default()
        self.state = GameState.new(catalog, line_id=catalog.lines[0]["id"], now=0)

    def test_elapsed_decay_keeps_fractional_time(self):
        self.state.apply_elapsed_time(900)
        self.assertEqual(72, self.state.hunger)
        self.state.apply_elapsed_time(1800)
        self.assertEqual(71, self.state.hunger)
        self.state.apply_elapsed_time(3600)
        self.assertEqual(70, self.state.hunger)
        self.assertEqual(67, self.state.happiness)

    def test_successful_care_awards_xp_and_obeys_cooldown(self):
        first = self.state.perform_care("feed", now=20)
        second = self.state.perform_care("feed", now=21)
        self.assertTrue(first.accepted)
        self.assertFalse(second.accepted)
        self.assertEqual(12, self.state.xp)
        self.assertEqual(1, self.state.care_points)


if __name__ == "__main__":
    unittest.main()

