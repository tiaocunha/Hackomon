import json
import unittest
from pathlib import Path

from tests import support
from tools.install_theme import install, prepare, OVERLAY


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def fixture(root):
    base = root / "wargames"
    layout = (("pagerportal", 227, 116), ("ALERTS", 263, 79), ("PAYLOADS", 299, 116),
              ("RECON", 335, 80), ("PINEAP", 373, 115), ("SETTINGS", 410, 80))
    write(base / "theme.json", {"theme_version": "2.0.0", "theme_framework_version": "0.9",
          "generic_menus": {"dashboard_path": "components/home.json"},
          "lock_screen_path": "components/lock.json", "color_palette": {"custom": {"r": 1, "g": 2, "b": 3}}})
    write(base / "components/home.json", {"screen_name": "main_dashboard", "status_bar": "default",
          "button_map": {"a": "select"}, "background": {"layers": []},
          "menu_items": [{"id": name, "x": x, "y": y, "target": name + "_target", "variable": "$_TEST"} for name, x, y in layout]})
    write(base / "components/lock.json", {"screen_name": "lock_screen", "background": {"layers": []},
          "button_map": {"a": "select"}, "pages": [{"menu_items": [{"id": "lock_screen", "selected_layers": []}]}]})
    return base


class ThemeInstallTests(unittest.TestCase):
    def test_theme_preserves_base_and_menu_actions_and_all_references_resolve(self):
        with support.temporary_directory() as directory:
            root = Path(directory)
            base = fixture(root)
            before = {str(p.relative_to(base)): p.read_bytes() for p in base.rglob("*") if p.is_file()}
            install(base, root / "themes")
            target = root / "themes/hackomon-field"
            self.assertEqual(before, {str(p.relative_to(base)): p.read_bytes() for p in base.rglob("*") if p.is_file()})
            old = json.loads((base / "components/home.json").read_text())
            new = json.loads((target / "components/home.json").read_text())
            for key in ("menu_items", "button_map", "status_bar"):
                self.assertEqual(old[key], new[key])
            theme = json.loads((target / "theme.json").read_text())
            self.assertEqual(theme["theme_version"], "2.0.0")
            self.assertIn("custom", theme["color_palette"])
            self.assertEqual((target / "assets/hackomon/field.png").read_bytes(), (OVERLAY / "assets/field.png").read_bytes())

    def test_existing_theme_is_not_overwritten(self):
        with support.temporary_directory() as directory:
            root = Path(directory)
            base = fixture(root)
            install(base, root / "themes")
            marker = root / "themes/hackomon-field/local.txt"
            marker.write_text("keep")
            with self.assertRaisesRegex(ValueError, "ja existe"):
                install(base, root / "themes")
            self.assertEqual(marker.read_text(), "keep")

    def test_dry_run_does_not_create_destination(self):
        with support.temporary_directory() as directory:
            root = Path(directory)
            result = install(fixture(root), root / "themes", dry_run=True)
            self.assertTrue(result["dry_run"])
            self.assertFalse((root / "themes").exists())

    def test_unknown_schema_and_changed_layout_fail_before_writes(self):
        with support.temporary_directory() as directory:
            root = Path(directory)
            base = fixture(root)
            theme = json.loads((base / "theme.json").read_text())
            theme["theme_framework_version"] = "1.0"
            write(base / "theme.json", theme)
            with self.assertRaisesRegex(ValueError, "formato"):
                install(base, root / "themes")
            theme["theme_framework_version"] = "0.9"
            write(base / "theme.json", theme)
            home = json.loads((base / "components/home.json").read_text())
            home["menu_items"][0]["x"] = 0
            write(base / "components/home.json", home)
            with self.assertRaisesRegex(ValueError, "Layout"):
                install(base, root / "themes")
            self.assertFalse((root / "themes").exists())

    def test_missing_and_escape_references_rejected(self):
        for reference in ("assets/missing.png", "../outside.json"):
            with self.subTest(reference=reference), support.temporary_directory() as directory:
                root = Path(directory)
                base = fixture(root)
                if reference.startswith("assets"):
                    write(base / "components/extra.json", {"image_path": reference})
                else:
                    theme = json.loads((base / "theme.json").read_text())
                    theme["lock_screen_path"] = reference
                    write(base / "theme.json", theme)
                with self.assertRaises(ValueError):
                    install(base, root / "themes")
                self.assertFalse((root / "themes").exists())

    def test_name_and_destination_cannot_escape_or_use_base(self):
        with support.temporary_directory() as directory:
            root = Path(directory)
            base = fixture(root)
            for name in ("../escape", "Hackomon", "a/b"):
                with self.assertRaises(ValueError):
                    install(base, root / "themes", name=name)
            with self.assertRaises(ValueError):
                install(base, root, name="wargames")


if __name__ == "__main__":
    unittest.main()
