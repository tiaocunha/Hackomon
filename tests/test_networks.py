import datetime
import io
import json
import unittest
from unittest.mock import patch

from tests import support
from hackomon.app import HackomonApp
from hackomon.catalog import CreatureCatalog
from hackomon.exploration import export_csv, record_observations
from hackomon.lab import authorized_target
from hackomon import lab
from hackomon.model import GameState
from hackomon.pager_backend import MemoryDisplay
from hackomon.radio import ble_observations, parse_gps_report, wifi_observations
from hackomon.storage import StateStore
from hackomon.wdgwars import NoRedirect, upload


def observation(index=1, kind="WIFI"):
    return dict(type=kind, mac="02:00:00:00:%02X:%02X" % (index // 256, index % 256),
                name='Lab, "teste"', auth="[WPA2]", timestamp=1700000000, channel=6,
                frequency=2437, rssi=-45, lat=-23.5, lon=-46.6, altitude=700, accuracy=8)


class Response(io.BytesIO):
    status = 200


class NetworksTests(unittest.TestCase):
    def setUp(self):
        self.catalog = CreatureCatalog.load_default()
        self.state = GameState.new(self.catalog, now=1700000000)

    def test_unique_rewards_survive_restart_and_daily_cap(self):
        result = record_observations(self.state, [observation(i) for i in range(100)], 1700000000)
        self.assertEqual(120, result["xp"])
        self.assertEqual(100, result["added"])
        state = GameState.from_dict(self.state.to_dict(), self.catalog)
        self.assertEqual(0, record_observations(state, [observation()], 1700000000)["xp"])
        state.network_queue = []
        later = observation()
        later["timestamp"] += 86400
        self.assertEqual(0, record_observations(state, [later], later["timestamp"])["xp"])
        self.assertEqual(1, len(state.network_queue))

    def test_ble_reward_invalid_gps_optout_and_stale_are_handled(self):
        values = [observation(1, "BLE"), dict(observation(2), lat=float("nan")),
                  dict(observation(3), name="Home_nomap"),
                  dict(observation(4), timestamp=1)]
        result = record_observations(self.state, values, 1700000000)
        self.assertEqual((1, 1, 2, 1), tuple(result[key] for key in ("added", "xp", "invalid", "excluded")))

    def test_queue_is_bounded_and_save_keeps_pending(self):
        record_observations(self.state, [observation(i) for i in range(600)], 1700000000)
        self.assertEqual(500, len(self.state.network_queue))
        with support.temporary_directory() as directory:
            store = StateStore(directory)
            store.save(self.state)
            restored, warning = store.load_or_create(self.catalog, now=1700000000)
            self.assertIsNone(warning)
            self.assertEqual(500, len(restored.network_queue))

    def test_csv_escapes_names_and_excludes_unrelated_secrets(self):
        value = dict(observation(), password="MUST-NOT-UPLOAD", handshake="SECRET-PCAP")
        encoded = export_csv([value])
        self.assertIn(b'"Lab, ""teste"""', encoded)
        self.assertNotIn(b"MUST-NOT-UPLOAD", encoded)
        self.assertNotIn(b"SECRET-PCAP", encoded)

    def test_wifi_parser(self):
        text = "BSS 02:00:00:00:00:01(on wlan0)\n\tfreq: 2437\n\tsignal: -42.50 dBm\n\tSSID: lab\n\tRSN:\n"
        found = wifi_observations(text, 1700000000)
        self.assertEqual(("lab", -42, "[WPA2]"), (found[0]["name"], found[0]["rssi"], found[0]["auth"]))

    def test_ble_parser_ignores_devices_without_signal(self):
        text = ("[NEW] Device 02:00:00:00:00:01 Test\n"
                "[CHG] Device 02:00:00:00:00:01 RSSI: -57\n"
                "[NEW] Device 02:00:00:00:00:02 Stale\n")
        found = ble_observations(text, 1700000000)
        self.assertEqual(1, len(found))
        self.assertEqual(-57, found[0]["rssi"])
        hexadecimal = ble_observations(text.replace("RSSI: -57", "RSSI: 0xffffffc9 (-55)"), 1700000000)
        self.assertEqual(-55, hexadecimal[0]["rssi"])

    def test_gps_requires_fresh_fix_and_accuracy(self):
        stamp = datetime.datetime.fromtimestamp(1700000000, datetime.timezone.utc).isoformat()
        report = dict(class_="TPV", mode=3, time=stamp, lat=-23.5, lon=-46.6, epx=6, epy=8)
        report["class"] = report.pop("class_")
        self.assertIsNotNone(parse_gps_report(report, 1700000000))
        self.assertIsNone(parse_gps_report(report, 1700000100))
        self.assertIsNone(parse_gps_report(dict(report, mode=1), 1700000000))
        self.assertIsNone(parse_gps_report(dict(report, epx=200), 1700000000))

    def test_lab_scope_uses_exact_bssid_and_expires(self):
        config = {"lab": {"bssid": "02:00:00:00:00:01", "authorized_until": 1700000060}}
        self.assertEqual("02:00:00:00:00:01", authorized_target(config, 1700000000))
        with self.assertRaises(RuntimeError):
            authorized_target(config, 1700000061)
        with self.assertRaises(RuntimeError):
            authorized_target({"lab": {"bssid": "*", "authorized_until": 1700000060}}, 1700000000)

    def test_lab_rejects_non_monitor_interface_before_capture(self):
        config = {"lab": {"bssid": "02:00:00:00:00:01", "authorized_until": 1700000300,
                          "monitor_interface": "wlan0"}}
        with support.temporary_directory() as directory:
            with patch("hackomon.lab.time.time", return_value=1700000000), \
                    patch("hackomon.lab.command", return_value="type managed"), \
                    patch("hackomon.lab.subprocess.Popen") as process:
                with self.assertRaises(RuntimeError):
                    lab.capture(config, directory)
                process.assert_not_called()

    def test_lab_offline_timeout_kills_process_and_does_not_claim_recovery(self):
        from pathlib import Path
        import subprocess
        from unittest.mock import MagicMock
        config = {"lab": {"bssid": "02:00:00:00:00:01", "authorized_until": 1700000300}}
        with support.temporary_directory() as directory:
            root = Path(directory) / "lab"
            root.mkdir()
            (root / "capture-test.json").write_text(json.dumps(
                {"bssid": "02:00:00:00:00:01", "created_at": 1700000000}))
            (root / "capture-test.pcap").write_bytes(b"fixture")
            (root / "dictionary.txt").write_text("test-password\n")
            process = MagicMock()
            process.__enter__.return_value = process
            process.wait.side_effect = [subprocess.TimeoutExpired("aircrack-ng", 30), 0]
            with patch("hackomon.lab.time.time", return_value=1700000000), \
                    patch("hackomon.lab.subprocess.Popen", return_value=process):
                verdict = lab.test_dictionary(config, directory)
            process.kill.assert_called_once()
            self.assertFalse(verdict["found"])
            self.assertIsNone(verdict["reward_id"])
            self.assertFalse((root / "capture-test.key").exists())

    def test_lab_capture_filter_and_dictionary_use_authorized_bssid(self):
        from pathlib import Path
        config = {"lab": {"bssid": "02:00:00:00:00:01", "authorized_until": 1700000300,
                          "monitor_interface": "mon0"}}
        with support.temporary_directory() as directory:
            def capture_process(args, **kwargs):
                self.assertIn("wlan addr3 02:00:00:00:00:01", args[-1])
                self.assertIn("ether proto 0x888e", args[-1])
                Path(args[args.index("-w") + 1]).write_bytes(b"PCAP-FIXTURE" * 8)
                from unittest.mock import MagicMock
                process = MagicMock()
                process.__enter__.return_value = process
                process.returncode = 0
                return process
            with patch("hackomon.lab.time.time", return_value=1700000000), \
                    patch("hackomon.lab.command", return_value="type monitor"), \
                    patch("hackomon.lab.subprocess.Popen", side_effect=capture_process):
                result = lab.capture(config, directory)
            self.assertIn("handshake ainda nao validado", result["message"])
            (Path(directory) / "lab" / "dictionary.txt").write_text("lab-test-password\n")
            def dictionary_process(args, **kwargs):
                self.assertEqual("02:00:00:00:00:01", args[args.index("-b") + 1])
                self.assertEqual(result["path"], args[-1])
                Path(args[args.index("-l") + 1]).write_text("LAB-SECRET")
                from unittest.mock import MagicMock
                process = MagicMock()
                process.__enter__.return_value = process
                process.wait.return_value = 0
                return process
            with patch("hackomon.lab.time.time", return_value=1700000000), \
                    patch("hackomon.lab.subprocess.Popen", side_effect=dictionary_process):
                verdict = lab.test_dictionary(config, directory)
            self.assertTrue(verdict["found"])
            self.assertNotIn("LAB-SECRET", str(verdict))

    def test_upload_is_multipart_and_requires_explicit_success(self):
        class Client:
            def open(client, request, timeout):
                self.assertEqual("https://wdgwars.pl/api/upload-csv", request.full_url)
                self.assertIn(b'name="file"', request.data)
                self.assertEqual(15, timeout)
                return Response(b'{"ok":true}')
        self.assertEqual(1, upload([observation()], "a" * 64, Client()))
        class BadClient:
            def open(client, request, timeout):
                return Response(b'{"ok":false}')
        with self.assertRaises(RuntimeError):
            upload([observation()], "a" * 64, BadClient())
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.test"))

    def test_ui_upload_requires_confirmation_and_failure_keeps_queue(self):
        with support.temporary_directory() as directory:
            app = HackomonApp(MemoryDisplay(), self.catalog, StateStore(directory), clock=lambda: 1700000000)
            record_observations(app.state, [observation()], 1700000000)
            app.screen = "network"
            app.network_selected = 3
            app._handle_network(app.display.BTN_A)
            self.assertEqual("upload_confirm", app.screen)
            self.assertIsNone(app.worker)
            app.results.put(("upload", None, "offline"))
            with patch.object(app, "worker") as worker:
                app._finish_network_job()
                worker.join.assert_called_once()
            self.assertEqual(1, len(app.state.network_queue))
            app.render(0)

    def test_worker_scan_updates_xp_and_persists_without_radio(self):
        with support.temporary_directory() as directory:
            app = HackomonApp(MemoryDisplay(), self.catalog, StateStore(directory), clock=lambda: 1700000000)
            with patch("hackomon.app.radio.discover", return_value=[observation()]):
                app._network_job("WIFI")
                app.worker.join()
            app._finish_network_job()
            self.assertEqual(2, app.state.xp)
            saved, warning = app.store.load_or_create(self.catalog, now=1700000000)
            self.assertIsNone(warning)
            self.assertEqual(1, len(saved.network_queue))


if __name__ == "__main__":
    unittest.main()
