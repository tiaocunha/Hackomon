import json
import unittest
from pathlib import Path

from tests import support
from hackomon.catalog import CreatureCatalog
from hackomon.storage import StateStore


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.catalog = CreatureCatalog.load_default()

    def test_round_trip(self):
        with support.temporary_directory() as directory:
            store = StateStore(directory)
            state, warning = store.load_or_create(self.catalog, line_id=self.catalog.lines[0]["id"], now=100)
            self.assertIsNone(warning)
            state.xp = 77
            store.save(state)
            restored, warning = store.load_or_create(self.catalog, now=100)
            self.assertIsNone(warning)
            self.assertEqual(77, restored.xp)

    def test_invalid_save_is_quarantined(self):
        with support.temporary_directory() as directory:
            path = Path(directory) / "state.json"
            path.write_text("{broken", encoding="utf-8")
            state, warning = StateStore(directory).load_or_create(
                self.catalog, line_id=self.catalog.lines[0]["id"], now=100
            )
            self.assertTrue(warning)
            self.assertEqual(0, state.stage)
            self.assertFalse(path.exists())
            self.assertEqual(1, len(list(Path(directory).glob("state.json.corrupt-*"))))

    def test_saved_json_is_valid_utf8(self):
        with support.temporary_directory() as directory:
            store = StateStore(directory)
            state, _ = store.load_or_create(self.catalog, line_id=self.catalog.lines[0]["id"], now=100)
            store.save(state)
            self.assertEqual(state.creature_id, json.loads(store.path.read_text(encoding="utf-8"))["creature_id"])


if __name__ == "__main__":
    unittest.main()

