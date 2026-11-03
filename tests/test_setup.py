import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import support
from tools.setup_pager import deploy
from hackomon import doctor


class SetupTests(unittest.TestCase):
    def files(self, root):
        source = root / "bundle/payload/hackomon"
        source.mkdir(parents=True)
        (source / "payload.sh").write_text("new")
        (source / "run_hackomon.py").write_text("new")
        library = root / "lib.so"
        library.write_bytes(b"\x7fELF\x01\x01" + bytes(12) + b"\x08\x00" + bytes(30))
        manifest = root / "dependency.json"
        manifest.write_text(json.dumps({"sha256": hashlib.sha256(library.read_bytes()).hexdigest()}))
        return source, library, manifest

    def test_upgrade_backs_up_old_payload_and_preserves_save(self):
        with support.temporary_directory() as directory:
            root = Path(directory)
            source, library, manifest = self.files(root)
            parent = root / "user/games"
            target = parent / "hackomon"
            target.mkdir(parents=True)
            (target / "payload.sh").write_text("old")
            save = root / "save/state.json"
            save.parent.mkdir()
            save.write_text("progress")
            installed, backup = deploy(source, parent, root / "backups", library, manifest)
            self.assertEqual((installed / "payload.sh").read_text(), "new")
            self.assertEqual((backup / "payload.sh").read_text(), "old")
            self.assertEqual(save.read_text(), "progress")
            self.assertEqual((installed / "lib/libpagerctl.so").read_bytes(), library.read_bytes())

    def test_bad_download_never_deploys(self):
        with support.temporary_directory() as directory:
            root = Path(directory)
            source, library, manifest = self.files(root)
            library.write_bytes(b"bad")
            with self.assertRaisesRegex(ValueError, "revisao"):
                deploy(source, root / "user/games", root / "backups", library, manifest)
            self.assertFalse((root / "user").exists())

    def test_rename_failure_restores_previous_payload(self):
        import os
        with support.temporary_directory() as directory:
            root = Path(directory)
            source, library, manifest = self.files(root)
            parent = root / "user/games"
            target = parent / "hackomon"
            target.mkdir(parents=True)
            (target / "payload.sh").write_text("old")
            rename = os.rename
            calls = []
            def fail_new(src, dst):
                calls.append((src, dst))
                if len(calls) == 2:
                    raise OSError("simulated full disk")
                return rename(src, dst)
            with patch("tools.setup_pager.os.rename", side_effect=fail_new):
                with self.assertRaises(OSError):
                    deploy(source, parent, root / "backups", library, manifest)
            self.assertEqual((target / "payload.sh").read_text(), "old")

    def test_doctor_has_no_hardware_init_and_optional_missing_does_not_block_pet(self):
        class API:
            def __getattr__(self, name):
                if name in doctor.SYMBOLS:
                    return lambda *args: self.fail("hardware call")
                raise AttributeError(name)
        with patch("ctypes.CDLL", return_value=API()), patch("hackomon.pager_backend.find_library", return_value="fake"), patch("hackomon.doctor.shutil.which", return_value=None), patch("hackomon.doctor.socket.create_connection", side_effect=OSError("offline")):
            ok, rows = doctor.check()
        self.assertTrue(ok)
        self.assertTrue(any(status == "OPCIONAL AUSENTE" for status, _ in rows))

    def test_doctor_rejects_library_missing_api(self):
        with patch("ctypes.CDLL", return_value=object()), patch("hackomon.pager_backend.find_library", return_value="fake"), patch("hackomon.doctor.socket.create_connection", side_effect=OSError("offline")):
            ok, rows = doctor.check()
        self.assertFalse(ok)
        self.assertTrue(any("API incompleta" in description for _, description in rows))


if __name__ == "__main__":
    unittest.main()
