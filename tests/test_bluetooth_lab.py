import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tests import support
from hackomon import bluetooth_lab
from hackomon.app import HackomonApp
from hackomon.catalog import CreatureCatalog
from hackomon.exploration import normalize_observation
from hackomon.pager_backend import MemoryDisplay
from hackomon.storage import StateStore
from tests.test_networks import observation


NOW = 1700000000
ADDRESS = "C3:00:00:00:00:01"
INFO = ("Device " + ADDRESS + " (random)\n\tName: Office Mouse\n"
        "\tConnected: no\n\tPaired: no\n"
        "\tUUID: Human Interface Device (00001812-0000-1000-8000-00805f9b34fb)\n")
SDP = ("Browsing " + ADDRESS + " ...\nService Name: Office HID\n"
       "Service RecHandle: 0x10001\nProtocol Descriptor List:\n  Channel: 7\n\n")


def config(transport="auto"):
    return {"lab": {"bluetooth": dict(address=ADDRESS, kind="mouse", transport=transport,
                                      authorized_until=NOW + 3600)}}


class BluetoothLabTests(unittest.TestCase):
    def test_bluetooth_random_address_is_not_treated_as_ethernet_multicast(self):
        self.assertEqual(ADDRESS, bluetooth_lab.target_scope(config(), NOW)[0])
        value = dict(observation(kind="BLE"), mac=ADDRESS)
        self.assertEqual(ADDRESS, normalize_observation(value)["mac"])
        with self.assertRaises(ValueError):
            normalize_observation(dict(value, type="WIFI"))

    def test_scope_rejects_expiry_wildcards_and_unsupported_kinds(self):
        for replacement in ({"address": "*"}, {"authorized_until": NOW - 1},
                            {"kind": "unknown"}, {"transport": "all"}):
            value = config()
            value["lab"]["bluetooth"].update(replacement)
            with self.assertRaises(RuntimeError):
                bluetooth_lab.target_scope(value, NOW)

    def test_info_parser_excludes_another_devices_metadata(self):
        info = bluetooth_lab.parse_info(INFO + "Device 02:00:00:00:00:02 Other\nName: Not Target\n", ADDRESS)
        self.assertEqual("Office Mouse", info["name"])
        self.assertFalse(info["flags"]["paired"])
        self.assertEqual(1, len(info["uuids"]))
        self.assertFalse(bluetooth_lab.parse_info(INFO, "02:00:00:00:00:02")["available"])

    def test_sdp_parser_requires_real_record_handle_and_preserves_channels(self):
        self.assertEqual([dict(name="Office HID", record_handle="0x10001", channels=[7])],
                         bluetooth_lab.parse_sdp(SDP))
        self.assertEqual([], bluetooth_lab.parse_sdp("Service Name: failed\n"))

    def test_audit_targets_one_device_and_keeps_report_outside_upload_queue(self):
        calls = []
        def runner(args, timeout):
            calls.append(args)
            self.assertEqual(ADDRESS, args[-1])
            return INFO if args[0] == "bluetoothctl" else SDP
        with support.temporary_directory() as directory:
            with patch("hackomon.bluetooth_lab.time.time", return_value=NOW), \
                    patch("hackomon.bluetooth_lab.command", side_effect=runner):
                result = bluetooth_lab.audit(config(), directory)
            self.assertTrue(result["completed"])
            self.assertEqual(2, len(calls))
            self.assertEqual(["sdptool", "browse", ADDRESS], calls[1])
            report = json.loads(Path(result["report_path"]).read_text())
            self.assertEqual([], report["verified_vulnerabilities"])
            self.assertIn("link_encryption", report["not_tested"])
            self.assertEqual("bluez_cache", report["metadata"]["source"])
            self.assertNotIn("network_queue", report)

    def test_ble_only_metadata_and_missing_dependencies_are_inconclusive(self):
        with support.temporary_directory() as directory:
            with patch("hackomon.bluetooth_lab.time.time", return_value=NOW), \
                    patch("hackomon.bluetooth_lab.command", return_value=INFO) as runner:
                result = bluetooth_lab.audit(config("le"), directory)
                self.assertEqual(1, runner.call_count)
                self.assertFalse(result["completed"])
            with patch("hackomon.bluetooth_lab.time.time", return_value=NOW), \
                    patch("hackomon.bluetooth_lab.command", side_effect=RuntimeError("tool missing")):
                result = bluetooth_lab.audit(config(), directory)
                self.assertFalse(result["completed"])
                report = json.loads(Path(result["report_path"]).read_text())
                self.assertEqual("inconclusive", report["result"])

    def test_bluetooth_audit_awards_xp_once_and_never_queues_lab_report(self):
        with support.temporary_directory() as directory:
            app = HackomonApp(MemoryDisplay(), CreatureCatalog.load_default(), StateStore(directory),
                              clock=lambda: NOW)
            verdict = dict(completed=True, reward_id="bluetooth:" + ADDRESS,
                           message="Services observed", report_path="not-for-upload.json")
            for _ in range(2):
                with patch("hackomon.app.bluetooth_lab.audit", return_value=verdict):
                    app._network_job("bluetooth_audit")
                    app.worker.join()
                app._finish_network_job()
            self.assertEqual(5, app.state.xp)
            self.assertEqual([], app.state.network_queue)
            saved, warning = app.store.load_or_create(app.catalog, now=NOW)
            self.assertIsNone(warning)
            self.assertEqual(["bluetooth:" + ADDRESS], saved.lab_rewards)
            app.screen = "network"
            app.network_selected = 6
            app.render(0)


if __name__ == "__main__":
    unittest.main()
