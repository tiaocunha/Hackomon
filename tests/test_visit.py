import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tests import support
from hackomon import radio, visit
from hackomon.app import HackomonApp
from hackomon.catalog import CreatureCatalog
from hackomon.pager_backend import MemoryDisplay
from hackomon.storage import StateStore


NOW = 1700000000
IW = ("phy#0\n\tInterface management\n\t\ttype AP\n"
      "\tInterface busy0\n\t\ttype managed\n"
      "phy#1\n\tInterface scan0\n\t\ttype managed\n"
      "\tInterface mon0\n\t\ttype monitor\n\t\tchannel 6 (2437 MHz), width: 20 MHz\n")
SCAN = ("BSS 02:00:00:00:00:01(on scan0)\n\tfreq: 2437\n\tsignal: -45.00 dBm\n"
        "\tcapability: ESS Privacy (0x0011)\n\tSSID: Client\n\tRSN:\n"
        "\t\t* Authentication suites: PSK\n\t\t* Pairwise ciphers: CCMP TKIP\n"
        "\t\t* Capabilities: MFP-capable (0x0080)\n\tWPS:\n\t\t* Version: 1.0\n")


def target():
    return radio.wifi_observations(SCAN, NOW)[0]


class VisitTests(unittest.TestCase):
    def test_auto_discovery_skips_ap_and_connected_interface_without_gps(self):
        calls = []
        def run(args, timeout):
            calls.append(args)
            if args == ["iw", "dev"]:
                return IW
            if args[-1] == "link":
                return "Connected to aa:bb:cc:dd:ee:ff" if args[2] == "busy0" else "Not connected."
            self.assertEqual(["iw", "dev", "scan0", "scan", "passive"], args)
            return SCAN
        with patch("hackomon.visit.radio.command", side_effect=run), \
                patch("hackomon.radio.gps_fix") as gps:
            values = visit.find_networks({})
        self.assertEqual("Client", values[0]["name"])
        self.assertFalse(any("management" in args for args in calls))
        gps.assert_not_called()

    def test_no_free_interface_does_not_scan_or_change_modes(self):
        with patch("hackomon.visit.radio.command", return_value="Interface wlan0\n type AP") as runner:
            with self.assertRaises(RuntimeError):
                visit.find_networks({})
            self.assertEqual(1, runner.call_count)

    def test_selected_target_is_session_only_and_does_not_inherit_static_scope(self):
        config = {"lab": {"bssid": "02:FF:FF:FF:FF:FF", "monitor_interface": "old0"}}
        before = copy.deepcopy(config)
        session = visit.session_config(config, target(), NOW)
        self.assertEqual("02:00:00:00:00:01", session["lab"]["bssid"])
        self.assertEqual("", session["lab"]["monitor_interface"])
        self.assertEqual(NOW + 3600, session["lab"]["authorized_until"])
        self.assertEqual(before, config)
        with self.assertRaises(RuntimeError):
            visit.session_config(config, target(), NOW + 301)

    def test_incomplete_security_is_unknown_and_ht_bits_do_not_set_pmf(self):
        partial = "BSS 02:00:00:00:00:02\n signal: -60 dBm\n SSID: Partial\n"
        self.assertEqual("[UNKNOWN]", radio.wifi_observations(partial, NOW)[0]["auth"])
        text = SCAN.replace("\t\t* Capabilities: MFP-capable (0x0080)",
                            "\tHT capabilities:\n\t\t* Capabilities: (0x0000)")
        self.assertIsNone(radio.wifi_observations(text, NOW)[0]["security"]["pmf"])

    def test_posture_records_advertisements_without_claiming_exploitation(self):
        findings = visit.posture(target())
        self.assertEqual({"tkip", "wps", "pmf"}, {entry["id"] for entry in findings})
        self.assertTrue(all(entry["confirmed_exploit"] is False for entry in findings))
        secure = SCAN.replace("CCMP TKIP", "CCMP").replace("(0x0080)", "(0x00c0)").replace("\tWPS:", "\tOther:")
        self.assertEqual([], visit.posture(radio.wifi_observations(secure, NOW)[0]))

    def test_auto_plan_passes_only_selected_scope_and_saves_private_reports(self):
        with support.temporary_directory() as directory:
            (Path(directory) / "lab").mkdir()
            (Path(directory) / "lab" / "dictionary.txt").write_text("lab-password\n")
            capture_config = []
            def capture(config, data_dir):
                capture_config.append(config)
                return {"path": "local-target.pcap"}
            with patch("hackomon.visit.time.time", return_value=NOW), \
                    patch("hackomon.visit.radio.command", return_value=IW), \
                    patch("hackomon.visit.lab.capture", side_effect=capture), \
                    patch("hackomon.visit.lab.test_dictionary", return_value={"found": True, "message": "Local key file"}) as dictionary:
                result = visit.assess({}, target(), directory)
            self.assertEqual("02:00:00:00:00:01", capture_config[0]["lab"]["bssid"])
            self.assertEqual("mon0", capture_config[0]["lab"]["monitor_interface"])
            self.assertEqual(capture_config[0], dictionary.call_args.args[0])
            self.assertEqual("key_recovered", result["report"]["dictionary"]["status"])
            self.assertTrue(Path(result["text_path"]).is_file())
            self.assertEqual("selected_bssid_only", json.loads(Path(result["report_path"]).read_text())["scope"])
            self.assertFalse((Path(directory) / "config.json").exists())

    def test_missing_matching_monitor_is_inconclusive_and_does_not_capture(self):
        with support.temporary_directory() as directory:
            with patch("hackomon.visit.time.time", return_value=NOW), \
                    patch("hackomon.visit.radio.command", return_value=IW.replace("2437 MHz", "5180 MHz")), \
                    patch("hackomon.visit.lab.capture") as capture:
                result = visit.assess({}, target(), directory)
            capture.assert_not_called()
            self.assertEqual("inconclusive", result["report"]["capture"]["status"])
            self.assertEqual("not_run", result["report"]["dictionary"]["status"])

    def test_free_radio_gets_temporary_monitor_and_cleanup_after_capture_failure(self):
        calls = []
        def runner(args, timeout):
            calls.append(args)
            if args == ["iw", "dev"]:
                return "phy#2\n Interface free0\n type managed\n"
            if args[-1] == "link":
                return "Not connected."
            return ""
        with support.temporary_directory() as directory:
            with patch("hackomon.visit.time.time", return_value=NOW), \
                    patch("hackomon.visit.radio.command", side_effect=runner), \
                    patch("hackomon.visit.lab.capture", side_effect=RuntimeError("No EAPOL")):
                result = visit.assess({}, target(), directory)
            created = next(args[5] for args in calls if args[:5] == ["iw", "phy", "phy2", "interface", "add"])
            self.assertTrue(created.startswith("hkm"))
            self.assertIn(["iw", "dev", created, "set", "freq", "2437"], calls)
            self.assertEqual(["iw", "dev", created, "del"], calls[-1])
            self.assertEqual("temporary_interface_removed", result["report"]["cleanup"]["status"])
            self.assertEqual("inconclusive", result["report"]["capture"]["status"])

    def test_temporary_interface_cleanup_failure_is_reported(self):
        def runner(args, timeout):
            if args == ["iw", "dev"]:
                return "phy#2\n Interface free0\n type managed\n"
            if args[-1] == "link":
                return "Not connected."
            if args[-1] == "del":
                raise RuntimeError("deletion failed")
            return ""
        with support.temporary_directory() as directory:
            with patch("hackomon.visit.time.time", return_value=NOW), \
                    patch("hackomon.visit.radio.command", side_effect=runner), \
                    patch("hackomon.visit.lab.capture", side_effect=RuntimeError("No EAPOL")):
                result = visit.assess({}, target(), directory)
            self.assertEqual("removal_failed", result["report"]["cleanup"]["status"])
            self.assertIn("ATENCAO", result["message"])

    def test_ui_selects_client_dynamically_no_registration_or_map_queue(self):
        with support.temporary_directory() as directory:
            app = HackomonApp(MemoryDisplay(), CreatureCatalog.load_default(), StateStore(directory), clock=lambda: NOW)
            app.screen = "network"
            with patch("hackomon.app.visit.find_networks", return_value=[target()]):
                app._handle_network(app.display.BTN_A)
                app.worker.join()
            app._finish_network_job()
            self.assertEqual("visit", app.screen)
            app.render(0)
            fake_report = dict(target=target(), findings=[], capture={"status": "inconclusive"},
                               dictionary={"status": "not_run"})
            verdict = dict(report=fake_report, completed=True, reward_id="visit:" + target()["mac"], message="Saved locally")
            with patch("hackomon.app.visit.assess", return_value=verdict) as assess:
                app._handle_visit(app.display.BTN_A)
                app.worker.join()
            app._finish_network_job()
            self.assertEqual(target()["mac"], assess.call_args.args[1]["mac"])
            self.assertEqual("visit_report", app.screen)
            self.assertEqual([], app.state.network_queue)
            self.assertEqual(5, app.state.xp)
            app.render(0)
            restarted = HackomonApp(MemoryDisplay(), app.catalog, app.store, clock=lambda: NOW)
            self.assertEqual([], restarted.visit_networks)
            self.assertIsNone(restarted.visit_report)
