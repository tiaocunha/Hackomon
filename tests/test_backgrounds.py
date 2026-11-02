import unittest

from tests import support  # noqa: F401
from hackomon.backgrounds import (
    BACKGROUND_HEIGHT,
    BACKGROUND_WIDTH,
    background_frame,
    background_palette_rgb,
    iter_background_runs,
)
from hackomon.catalog import CreatureCatalog


class BackgroundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = CreatureCatalog.load_default()

    def test_every_creature_has_a_valid_scene(self):
        for creature in self.catalog.creatures:
            frame = background_frame(creature)
            self.assertEqual(BACKGROUND_HEIGHT, len(frame))
            self.assertTrue(all(len(row) == BACKGROUND_WIDTH for row in frame))
            self.assertTrue(all(0 <= value <= 7 for row in frame for value in row))

    def test_all_250_background_identities_are_distinct(self):
        signatures = {
            (tuple(map(tuple, background_frame(creature))), background_palette_rgb(creature))
            for creature in self.catalog.creatures
        }
        self.assertEqual(250, len(signatures))

    def test_only_rare_stage_uses_animated_environment(self):
        adult = self.catalog.creatures[3]
        rare = self.catalog.creatures[4]
        self.assertEqual(background_frame(adult, frame_index=0), background_frame(adult, frame_index=1))
        self.assertNotEqual(background_frame(rare, frame_index=0), background_frame(rare, frame_index=1))

    def test_background_run_count_stays_bounded_for_pager(self):
        maximum = max(
            len(list(iter_background_runs(background_frame(creature))))
            for creature in self.catalog.creatures
        )
        self.assertLessEqual(maximum, 280)


if __name__ == "__main__":
    unittest.main()
