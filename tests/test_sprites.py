import unittest

from tests import support  # noqa: F401
from hackomon.catalog import CreatureCatalog
from hackomon.sprites import POSE_LENGTHS, iter_color_runs, palette_rgb, sprite_frame


class SpriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = CreatureCatalog.load_default()

    def test_every_creature_renders_inside_24_pixel_canvas(self):
        for creature in self.catalog.creatures:
            frame = sprite_frame(creature)
            self.assertEqual(24, len(frame))
            self.assertTrue(all(len(row) == 24 for row in frame))
            self.assertGreater(sum(1 for row in frame for value in row if value), 10)
            self.assertTrue(all(0 <= value <= 5 for row in frame for value in row))

    def test_all_animation_poses_change(self):
        creature = self.catalog.creatures[-1]
        for pose, length in POSE_LENGTHS.items():
            signatures = {tuple(map(tuple, sprite_frame(creature, pose, index))) for index in range(length)}
            self.assertGreaterEqual(len(signatures), 2, pose)

    def test_all_250_visual_identities_are_distinct(self):
        signatures = {
            (tuple(map(tuple, sprite_frame(creature))), palette_rgb(creature))
            for creature in self.catalog.creatures
        }
        self.assertEqual(250, len(signatures))

    def test_run_compaction_preserves_nontransparent_pixel_count(self):
        frame = sprite_frame(self.catalog.creatures[100])
        pixels = sum(1 for row in frame for value in row if value)
        compacted = sum(width for _x, _y, width, _color in iter_color_runs(frame))
        self.assertEqual(pixels, compacted)


if __name__ == "__main__":
    unittest.main()

