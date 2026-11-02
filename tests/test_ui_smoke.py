import unittest

from tests import support
from tamafi.app import TamaFiApp
from tamafi.catalog import CreatureCatalog
from tamafi.pager_backend import MemoryDisplay
from tamafi.storage import StateStore


class UISmokeTests(unittest.TestCase):
    def test_two_frames_render_and_save_without_hardware(self):
        catalog = CreatureCatalog.load_default()
        display = MemoryDisplay()
        with support.temporary_directory() as directory:
            app = TamaFiApp(display, catalog, StateStore(directory), clock=lambda: 100)
            app.run(max_frames=2)
            self.assertTrue(any(operation[0] == "flip" for operation in display.operations))
            self.assertTrue(StateStore(directory).path.exists())


if __name__ == "__main__":
    unittest.main()

