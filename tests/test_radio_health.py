import json
from contextlib import closing
import queue
import sqlite3
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests import support
from tests.test_networks import observation
from hackomon import expedition, radio, recon, visit
from hackomon.app import HackomonApp
from hackomon.catalog import CreatureCatalog
from hackomon.pager_backend import MemoryDisplay
from hackomon.storage import StateStore
from tools import diagnose_radios


NOW = 1700000000


def database(root, rows=None):
    path = Path(root) / "recon with spaces.db"
    with closing(sqlite3.connect(path)) as connection:
        with connection:
            connection.execute("CREATE TABLE ssid(type, bssid, ssid, freq, channel, signal, time)")
            for row in rows or [(8, "020000000001", b"Home", 2437, 6, -42, NOW)]:
                connection.execute("INSERT INTO ssid VALUES(?,?,?,?,?,?,?)", row)
    return path


class NativeReconTests(unittest.TestCase):
    def test_readonly_fresh_ap_schema_without_inventing_security(self):
        with support.temporary_directory() as directory:
            path = database(directory)
            before = path.read_bytes()
            found = recon.read_wifi(path, now=NOW)
            self.assertEqual("Recon", found.source)
            self.assertEqual(("02:00:00:00:00:01", "Home", -42, NOW),
                             tuple(found[0][key] for key in ("mac", "name", "rssi", "timestamp")))
            self.assertEqual("[UNKNOWN]", found[0]["auth"])
            self.assertEqual("hak5_recon", found[0]["time_source"])
            self.assertEqual(before, path.read_bytes())

    def test_old_future_client_multicast_and_invalid_records_are_not_discoveries(self):
        rows = [(8, "020000000001", "old", 2437, 6, -42, NOW - 31),
                (8, "020000000002", "future", 2437, 6, -42, NOW + 100),
                (4, "020000000003", "client", 2437, 6, -42, NOW),
                (8, "010000000004", "multicast", 2437, 6, -42, NOW),
                (8, "020000000005", "bad signal", 2437, 6, "bad", NOW)]
        with support.temporary_directory() as directory:
            self.assertEqual([], recon.read_wifi(database(directory, rows), now=NOW))

    def test_unknown_schema_rejected_without_writes(self):
        with support.temporary_directory() as directory:
            path = Path(directory) / "changed.db"
            with closing(sqlite3.connect(path)) as connection:
                connection.execute("CREATE TABLE ssid(name)")
            before = path.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "formato"):
                recon.read_wifi(path, now=NOW)
            self.assertEqual(before, path.read_bytes())

    def test_no_managed_interface_falls_back_without_changing_radio_modes(self):
        found = recon.NetworkScan([observation()], "Recon")
        with patch("hackomon.visit.radio.command", return_value="Interface mon0\n type monitor\n") as command, \
                patch("hackomon.visit.recon.read_wifi", return_value=found) as read:
            self.assertEqual(found, visit.find_networks({}))
            command.assert_called_once_with(["iw", "dev"], timeout=3)
            read.assert_called_once_with(limit=100)

    def test_down_auto_interface_falls_back_but_explicit_choice_remains_explicit(self):
        def command(args, timeout):
            if args == ["iw", "dev"]:
                return "Interface sta0\n type managed\n"
            if args[-1] == "link":
                return "Not connected."
            raise RuntimeError("iw: interface desligada")
        with patch("hackomon.visit.radio.command", side_effect=command), \
                patch("hackomon.visit.recon.read_wifi", return_value=recon.NetworkScan()) as read:
            visit.find_networks({})
            read.assert_called_once()
            with self.assertRaises(RuntimeError):
                visit.find_networks({"wifi_interface": "sta0"})
            self.assertEqual(1, read.call_count)

    def test_native_observations_count_without_gps_and_never_enter_map_queue(self):
        with support.temporary_directory() as directory:
            item = dict(observation(), time_source="hak5_recon")
            for key in ("lat", "lon", "accuracy", "altitude"):
                item.pop(key)
            pump = expedition.Pump({}, threading.Lock())
            located = pump.locate(item)
            self.assertNotIn("lat", located)
            journal = expedition.Journal(directory, now=NOW)
            self.assertEqual([], journal.observations([located]))
            self.assertEqual((1, 1), (journal.summary["wifi"], journal.summary["unlocated"]))


class RadioHealthTests(unittest.TestCase):
    def test_bluetooth_off_or_missing_is_specific_and_does_not_start_scan(self):
        for text, expected in (("Controller 02:00:00:00:00:01\n Powered: no\n", "desligado"),
                               ("No default controller available\n", "controlador")):
            with self.subTest(text=text), patch("hackomon.radio.command", return_value=text) as command:
                with self.assertRaisesRegex(RuntimeError, expected):
                    radio.bluetooth_ready()
                command.assert_called_once_with(["bluetoothctl", "show"], timeout=4)

    def test_bluetooth_zero_exit_failure_text_is_not_an_empty_success(self):
        self.assertIn("nao pronto", radio.bluetooth_scan_error("Failed to start discovery: org.bluez.Error.NotReady"))
        self.assertIn("recusada", radio.bluetooth_scan_error("Failed to start discovery: org.bluez.Error.Failed"))
        self.assertEqual("", radio.bluetooth_scan_error("Discovery started"))

    def test_gps_errors_never_hide_each_radios_last_status(self):
        with support.temporary_directory() as directory:
            app = HackomonApp(MemoryDisplay(), CreatureCatalog.load_default(), StateStore(directory), clock=lambda: NOW)
            pump = MagicMock()
            pump.events = queue.Queue()
            with patch("hackomon.app.expedition.Pump", return_value=pump):
                app._start_expedition()
            pump.events.put(("radio_status", dict(radio="wifi", ok=False, message="Wi-Fi sem interface livre")))
            pump.events.put(("radio_status", dict(radio="ble", ok=False, message="Bluetooth desligado")))
            pump.events.put(("gps_error", "GPS sem posicao recente"))
            app._tick_expedition()
            self.assertIn("sem interface", app.journal.summary["radios"]["wifi"]["message"])
            self.assertIn("desligado", app.journal.summary["radios"]["ble"]["message"])
            app.screen = "expedition"
            app.render(0)

    def test_support_report_never_exposes_identifiers_or_coordinates_and_uses_no_scan(self):
        calls = []
        def run(args):
            calls.append(args)
            if args == ["iw", "dev"]:
                return 0, "Interface sta0\n addr aa:bb:cc:dd:ee:ff\n type managed\n"
            if args[-1] == "link":
                return 0, "Connected to aa:bb:cc:dd:ee:ff\n SSID: PRIVATE_HOME\n"
            if args[-1] == "show":
                return 0, "Controller aa:bb:cc:dd:ee:ff PRIVATE_ALIAS\n Powered: no\n"
            return 0, "Device aa:bb:cc:dd:ee:ff PRIVATE_DEVICE\n"
        with support.temporary_directory() as directory:
            path = database(directory)
            with patch("tools.diagnose_radios.run", side_effect=run), \
                    patch("tools.diagnose_radios.gps_status", return_value="modo=3 idade=1s"), \
                    patch("tools.diagnose_radios.time.time", return_value=NOW):
                report = diagnose_radios.report(path, Path(directory))
        for secret in ("aa:bb:cc:dd:ee:ff", "PRIVATE_HOME", "PRIVATE_ALIAS", "PRIVATE_DEVICE", "Home"):
            self.assertNotIn(secret, report)
        self.assertIn("Powered=no", report)
        self.assertIn("recentes30s=1", report)
        self.assertFalse(any("scan" in args or "power" in args for args in calls))
