"""Run the actual Bash launcher with fake Python and the Hak5 temp/home layout."""

import os
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import support
from tools.setup_pager import verify_launcher


def bash_executable():
    if os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
        return str(candidate) if candidate.exists() else None
    return shutil.which("bash")


def bash_path(path):
    value = Path(path).resolve().as_posix()
    if os.name == "nt":
        return "/" + value[0].lower() + value[2:]
    return value


@unittest.skipUnless(bash_executable(), "Bash launcher regression tests")
class LauncherTests(unittest.TestCase):
    def run_launcher(self, mode="runner", library=True, valid_home=True, doctor=True, app_code=0):
        with support.temporary_directory() as directory:
            root = Path(directory)
            installed = root / "installed game with spaces"
            installed.mkdir()
            (installed / "run_hackomon.py").write_text("# fake app; never executed")
            (installed / "lib").mkdir()
            if library:
                (installed / "lib/libpagerctl.so").write_bytes(b"fixture")
            launcher = installed / "payload.sh"
            shutil.copyfile(support.PAYLOAD / "payload.sh", launcher)
            temp_script = root / "temporary runner.sh"
            shutil.copyfile(launcher, temp_script)
            driver = root / "driver.sh"
            driver.write_text('''#!/bin/bash
python3() {
    if [ "$1" = "-c" ]; then return 0; fi
    printf '%s\\n' "$@" > "$HACKOMON_TEST_PY_ARGS"
    return "$HACKOMON_TEST_APP_CODE"
}
START_SPINNER() { printf fixture; }
STOP_SPINNER() { :; }
WAIT_FOR_INPUT() { :; }
export -f python3 START_SPINNER STOP_SPINNER WAIT_FOR_INPUT
export HACKOMON_CHECK_INSTALL="$HACKOMON_TEST_DOCTOR"
case "$1" in
  runner) export _PAYLOAD_HOME="$3"; bash "$2" ;;
  direct) unset _PAYLOAD_HOME; bash "$2" ;;
  source) unset _PAYLOAD_HOME; source "$2" ;;
esac
''', encoding="ascii")
            record = root / "python-args.txt"
            environment = os.environ.copy()
            environment["HACKOMON_TEST_PY_ARGS"] = bash_path(record)
            environment["HACKOMON_TEST_DOCTOR"] = "1" if doctor else "0"
            environment["HACKOMON_TEST_APP_CODE"] = str(app_code)
            environment["HACKOMON_DATA_DIR"] = bash_path(root / "save")
            environment["HACKOMON_LOG_FILE"] = bash_path(root / "app.log")
            environment.pop("BASH_ENV", None)
            script = temp_script if mode == "runner" else launcher
            home = installed if valid_home else root / "missing"
            result = subprocess.run([bash_executable(), bash_path(driver), mode, bash_path(script), bash_path(home)],
                                    cwd=str(root), env=environment, capture_output=True, text=True, timeout=10)
            args = record.read_text().splitlines() if record.exists() else []
            return result, args, bash_path(installed)

    def test_hak5_temp_runner_uses_real_payload_home_for_entry_and_library(self):
        result, args, installed = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(args, [installed + "/run_hackomon.py", "--doctor", "--pagerctl-lib", installed + "/lib/libpagerctl.so"])

    def test_direct_execution_without_hak5_environment(self):
        result, args, installed = self.run_launcher(mode="direct")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(args[0], installed + "/run_hackomon.py")

    def test_sourced_execution_uses_bash_source_instead_of_driver_zero(self):
        result, args, installed = self.run_launcher(mode="source")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(args[0], installed + "/run_hackomon.py")

    def test_missing_library_reports_repair_not_manual_pagerctl_install(self):
        result, args, _ = self.run_launcher(library=False)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(args)
        self.assertIn("INSTALAR.cmd", result.stdout)
        self.assertNotIn("Instale o payload PAGERCTL", result.stdout)

    def test_invalid_home_fails_before_screen_handoff(self):
        result, args, _ = self.run_launcher(valid_home=False)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(args)
        self.assertIn("pasta instalada nao encontrada", result.stdout)

    def test_normal_launch_uses_guard_and_never_stops_a_native_service(self):
        result, args, installed = self.run_launcher(doctor=False)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(["-m", "hackomon.stock_ui", "--", "python3", installed + "/run_hackomon.py"], args[:5])
        self.assertNotIn("--doctor", args)

    def test_normal_launch_preserves_app_failure_code(self):
        result, _args, _installed = self.run_launcher(doctor=False, app_code=7)
        self.assertEqual(7, result.returncode, result.stdout + result.stderr)


class InstalledLauncherCheckTests(unittest.TestCase):
    def test_setup_checks_a_temp_copy_with_real_home_and_diagnostic_mode(self):
        with support.temporary_directory() as directory:
            root = Path(directory)
            target = root / "installed"
            target.mkdir()
            (target / "payload.sh").write_text("fixture launcher")
            def run(command, **kwargs):
                self.assertEqual(command[0], "/bin/bash")
                self.assertNotEqual(Path(command[1]), target / "payload.sh")
                self.assertEqual(Path(command[1]).read_text(), "fixture launcher")
                self.assertEqual(kwargs["env"]["_PAYLOAD_HOME"], str(target.resolve()))
                self.assertEqual(kwargs["env"]["HACKOMON_CHECK_INSTALL"], "1")
                self.assertEqual(kwargs["timeout"], 30)
                return subprocess.CompletedProcess(command, 0)
            with patch("tools.setup_pager.subprocess.run", side_effect=run):
                verify_launcher(target, temp_parent=root)
            self.assertFalse(list(root.glob("hackomon-launch-check-*")))

    def test_failed_launcher_check_cannot_report_success(self):
        with support.temporary_directory() as directory:
            root = Path(directory)
            (root / "payload.sh").write_text("fixture")
            with patch("tools.setup_pager.subprocess.run", return_value=subprocess.CompletedProcess([], 2)):
                with self.assertRaisesRegex(ValueError, "iniciador falhou"):
                    verify_launcher(root, temp_parent=root)
