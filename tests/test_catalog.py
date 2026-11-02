import unittest

from tests import support  # noqa: F401
from hackomon.catalog import CreatureCatalog


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = CreatureCatalog.load_default()

    def test_required_counts_and_uniqueness(self):
        self.assertEqual(10, len(self.catalog.families))
        self.assertEqual(50, len(self.catalog.lines))
        self.assertEqual(250, len(self.catalog.creatures))
        self.assertEqual(250, len({item["id"] for item in self.catalog.creatures}))
        self.assertEqual(250, len({item["name"] for item in self.catalog.creatures}))

    def test_every_family_has_five_lines_and_every_line_five_stages(self):
        for family in self.catalog.families:
            self.assertEqual(5, len(self.catalog.family_lines(family["id"])))
        for evolution_line in self.catalog.lines:
            stages = [self.catalog.creature(item)["stage"] for item in evolution_line["creature_ids"]]
            self.assertEqual([0, 1, 2, 3, 4], stages)


if __name__ == "__main__":
    unittest.main()

