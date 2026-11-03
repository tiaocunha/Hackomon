import json
import unittest
from pathlib import Path

from tests import support
from tests.test_theme_install import fixture
from tools import install_theme
from tools.setup_pager import ensure_theme


class ReinstallThemeTests(unittest.TestCase):
    def test_first_install_and_repeat_preserve_all_files(self):
        with support.temporary_directory() as directory:
            root = Path(directory)
            base = fixture(root)
            parent = root / "themes"
            self.assertEqual(ensure_theme(install_theme, base, parent), "created")
            target = parent / "hackomon-field"
            before = {str(p.relative_to(target)): p.read_bytes() for p in target.rglob("*") if p.is_file()}
            self.assertEqual(ensure_theme(install_theme, base, parent), "preserved")
            self.assertEqual(before, {str(p.relative_to(target)): p.read_bytes() for p in target.rglob("*") if p.is_file()})

    def test_unmanaged_folder_is_never_replaced(self):
        with support.temporary_directory() as directory:
            root = Path(directory)
            target = root / "themes/hackomon-field"
            target.mkdir(parents=True)
            original = target / "custom.txt"
            original.write_text("preserve")
            with self.assertRaises(OSError):
                ensure_theme(install_theme, themes_root=root / "themes")
            self.assertEqual(original.read_text(), "preserve")

    def test_broken_theme_does_not_report_success(self):
        with support.temporary_directory() as directory:
            root = Path(directory)
            base = fixture(root)
            parent = root / "themes"
            ensure_theme(install_theme, base, parent)
            image = parent / "hackomon-field/assets/hackomon/field.png"
            image.unlink()
            with self.assertRaises(ValueError):
                ensure_theme(install_theme, base, parent)
            self.assertFalse(image.exists())

    def test_unknown_overlay_version_is_preserved_and_reported(self):
        with support.temporary_directory() as directory:
            root = Path(directory)
            base = fixture(root)
            parent = root / "themes"
            ensure_theme(install_theme, base, parent)
            marker = parent / "hackomon-field/hackomon-overlay.json"
            data = json.loads(marker.read_text())
            data["overlay_version"] = "future"
            marker.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "nao reconhecido"):
                ensure_theme(install_theme, base, parent)
            self.assertEqual(json.loads(marker.read_text())["overlay_version"], "future")
