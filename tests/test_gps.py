"""GPSd variants, rejection evidence and bounded, private health history."""

import datetime
import json
import queue
import threading
import unittest
from unittest.mock import MagicMock, patch

from tests import support
from hackomon import doctor, expedition, radio
from hackomon.app import HackomonApp
from hackomon.catalog import CreatureCatalog
from hackomon.pager_backend import MemoryDisplay
from hackomon.storage import StateStore
from tools import diagnose_radios


NOW = 1700000000
STAMP = datetime.datetime.fromtimestamp(NOW, datetime.timezone.utc).isoformat()


def tpv(**fields):
    return dict(
        {"class": "TPV", "device": "/dev/private", "mode": 3, "time": STAMP,
         "lat": -20.0, "lon": -40.0, "epx": 6, "epy": 8}, **fields)


class GPSProtocolTests(unittest.TestCase):
    def test_horizontal_error_alone_and_conservative_combination(self):
        report = tpv()
        del report["epx"], report["epy"]
        fix, health = radio.evaluate_gps_report(dict(report, eph=12), NOW)
        self.assertEqual(12, fix["accuracy"])
        self.assertEqual("eph", health["accuracy_source"])
        self.assertEqual(18, radio.parse_gps_report(tpv(eph=18), NOW)["accuracy"])
        self.assertIsNone(radio.parse_gps_report(tpv(eph=101), NOW))
        self.assertIsNone(radio.parse_gps_report(dict(report, hdop=1, satellites=8), NOW))

    def test_same_device_epoch_merges_partial_reports_only(self):
        reports = radio.GPSReports()
        first = tpv()
        del first["epx"], first["epy"]
        self.assertIsNone(reports.consume(first, NOW))
        second = {"class": "TPV", "device": first["device"], "time": STAMP,
                  "mode": 3, "epx": 6, "epy": 8}
        self.assertEqual(8, reports.consume(second, NOW)["accuracy"])
        for change in ({"time": STAMP.replace("20+", "21+")}, {"device": "/dev/other"}):
            separate = radio.GPSReports()
            separate.consume(first, NOW)
            self.assertIsNone(separate.consume(dict(second, **change), NOW))

    def test_no_time_or_device_cannot_borrow_a_previous_position(self):
        for missing in ("time", "device"):
            reports = radio.GPSReports()
            first = tpv()
            del first["epx"], first["epy"], first[missing]
            reports.consume(first, NOW)
            second = tpv()
            del second["lat"], second["lon"], second[missing]
            self.assertIsNone(reports.consume(second, NOW))

    def test_loss_of_fix_and_usb_disconnect_clear_partial_epoch(self):
        for loss in ({"class": "TPV", "mode": 1}, {"class": "DEVICES", "devices": []}):
            reports = radio.GPSReports()
            first = tpv()
            del first["epx"], first["epy"]
            reports.consume(first, NOW)
            reports.consume(loss, NOW)
            second = tpv()
            del second["lat"], second["lon"]
            self.assertIsNone(reports.consume(second, NOW))

    def test_epochs_are_bounded_and_data_cannot_be_reused_at_a_new_time(self):
        reports = radio.GPSReports()
        for offset in range(50):
            stamp = datetime.datetime.fromtimestamp(NOW + offset, datetime.timezone.utc).isoformat()
            reports.consume(tpv(time=stamp), NOW + offset)
        self.assertEqual(8, len(reports.epochs))
        report = tpv(time=STAMP)
        del report["epx"], report["epy"]
        self.assertIsNone(reports.consume(report, NOW))

    def test_rejection_reason_and_limits_remain_explicit(self):
        for fields, code in (({"mode": 1}, "no_fix"), ({"time": "bad"}, "invalid_time"),
                             ({"time": None}, "missing_time"),
                             ({"time": "2023-11-14T22:13:20"}, "invalid_time"),
                             ({"epx": 101}, "bad_accuracy"), ({"lat": 91}, "bad_position"),
                             ({"epy": float("nan")}, "bad_accuracy"),
                             ({"eph": -1}, "bad_accuracy"), ({"epx": True}, "bad_accuracy"),
                             ({"lon": "-40"}, "bad_position"),
                             ({"epx": 10 ** 400}, "bad_accuracy"),
                             ({"altMSL": float("inf")}, "bad_altitude")):
            with self.subTest(code=code, fields=fields):
                fix, health = radio.evaluate_gps_report(tpv(**fields), NOW)
                self.assertIsNone(fix)
                self.assertEqual(code, health["code"])
        for offset in (-16, 16):
            fix, health = radio.evaluate_gps_report(tpv(), NOW + offset)
            self.assertIsNone(fix)
            self.assertEqual("stale_time", health["code"])
            self.assertEqual(-offset, health["time_offset_s"])
        self.assertIsNotNone(radio.parse_gps_report(tpv(mode=2, epx=100, epy=100), NOW + 15))

    def test_fragmented_socket_stream_uses_current_pager_time_and_recovers(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        raw = (json.dumps(tpv()) + "\n").encode()
        connection.recv.side_effect = [b"invalid json\n", raw[:30], raw[30:70], raw[70:]]
        with patch("hackomon.radio.socket.create_connection", return_value=connection), \
                patch("hackomon.radio.time.time", return_value=NOW) as clock:
            fix = radio.gps_fix()
        self.assertEqual(NOW, fix["fix_time"])
        self.assertEqual("valid", fix["gps_health"]["code"])
        self.assertTrue(clock.called)

    def test_empty_device_list_and_unreachable_service_are_distinct(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.recv.side_effect = [b'{"class":"DEVICES","devices":[]}\n', b""]
        with patch("hackomon.radio.socket.create_connection", return_value=connection):
            with self.assertRaises(radio.GPSFixError) as error:
                radio.gps_fix(now=NOW)
        self.assertEqual("no_receiver", error.exception.health["code"])
        with patch("hackomon.radio.socket.create_connection", side_effect=OSError("private path")):
            with self.assertRaises(radio.GPSFixError) as error:
                radio.gps_fix(now=NOW)
        self.assertEqual("unavailable", error.exception.health["code"])
        self.assertNotIn("private", str(error.exception))

    def test_timeout_and_oversized_line_do_not_prevent_next_valid_report(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.recv.side_effect = [radio.socket.timeout(), b"x" * 8192,
                                      b"x" * 3000 + b"\n" + (json.dumps(tpv()) + "\n").encode()]
        with patch("hackomon.radio.socket.create_connection", return_value=connection):
            self.assertEqual(NOW, radio.gps_fix(now=NOW)["fix_time"])


class GPSHealthTests(unittest.TestCase):
    def test_sensor_and_reader_agree_on_both_sides_of_the_fifteen_second_window(self):
        for offset in (-15.01, -15, -0.8, 0, 1.01, 15, 15.01):
            with self.subTest(offset=offset):
                stamp = datetime.datetime.fromtimestamp(NOW + offset, datetime.timezone.utc).isoformat()
                fix = radio.parse_gps_report(tpv(time=stamp), NOW)
                summary = dict(status="running", gps_at=NOW + offset)
                status, text = expedition.sensor_status(summary, "gps", NOW)
                self.assertEqual(fix is not None, status == "ok")
                if 0 < offset <= 15:
                    self.assertIn("GPS +", text)

    def test_ahead_fix_reaches_app_ui_and_does_not_hide_a_real_rejection(self):
        with support.temporary_directory() as directory:
            app = HackomonApp(MemoryDisplay(), CreatureCatalog.load_default(), StateStore(directory), clock=lambda: NOW)
            pump = MagicMock()
            pump.events = queue.Queue()
            with patch("hackomon.app.expedition.Pump", return_value=pump):
                app._start_expedition()
            stamp = datetime.datetime.fromtimestamp(NOW + 1.01, datetime.timezone.utc).isoformat()
            fix, health = radio.evaluate_gps_report(tpv(time=stamp, eph=34.77), NOW)
            pump.events.put(("gps_health", health))
            pump.events.put(("gps", fix))
            app._tick_expedition()
            self.assertEqual("ok", expedition.sensor_status(app.journal.summary, "gps", NOW)[0])
            app.screen = "expedition"
            app.render(0)
            texts = [op[3] for op in app.display.operations if op[0] == "text"]
            self.assertTrue(any("GPS +2s" in text for text in texts))
            app.journal.gps_health(dict(code="no_receiver"), NOW)
            status, text = expedition.sensor_status(app.journal.summary, "gps", NOW)
            self.assertEqual("waiting", status)
            self.assertEqual("GPSd sem receptor", text)

    def test_installer_check_reports_accepted_accuracy_and_clock_without_positions(self):
        with patch("hackomon.radio.gps_fix", return_value=dict(
                lat=-20, lon=-40, gps_health=dict(code="valid", accuracy_m=34.77, time_offset_s=1.01))):
            status, text = doctor.gps_check()
        self.assertEqual("OK", status)
        self.assertIn("34.8m", text)
        self.assertIn("+1.01s", text)
        self.assertNotIn("-20", text)
        self.assertNotIn("-40", text)

    def test_installer_check_keeps_gps_optional_and_filters_raw_failures(self):
        for error in (radio.GPSFixError(dict(code="no_receiver", message="PRIVATE")), OSError("PRIVATE")):
            with patch("hackomon.radio.gps_fix", side_effect=error):
                status, text = doctor.gps_check()
            self.assertEqual("OPCIONAL INDISPONIVEL", status)
            self.assertNotIn("PRIVATE", text)

    def test_diagnostic_uses_app_decision_without_coordinates_or_raw_errors(self):
        for result in (dict(gps_health=dict(code="valid", accuracy_m=8, lat=-20)),
                       radio.GPSFixError(dict(code="missing_accuracy", device="PRIVATE"))):
            with patch("tools.diagnose_radios.Path.is_dir", return_value=True), \
                    patch("hackomon.radio.gps_fix", side_effect=[result]):
                text = diagnose_radios.gps_status()
            self.assertNotIn("PRIVATE", text)
            self.assertNotIn("lat", text)
            self.assertIn("code", json.loads(text))

    def test_health_allowlist_removes_identifiers_and_malformed_values(self):
        value = dict(code="bad_accuracy", accuracy_m=120, lat=-20, lon=-40,
                     device="/dev/private", message="PRIVATE", ssid="PRIVATE")
        health = radio.sanitize_gps_health(value)
        self.assertEqual({"code", "message", "accuracy_m"}, set(health))
        for invalid in (None, [], {"code": []}, {"code": "PRIVATE"}):
            self.assertEqual("invalid_report", radio.sanitize_gps_health(invalid)["code"])

    def test_pump_preserves_specific_rejection_and_recovers_next_read(self):
        pump = expedition.Pump({}, threading.Lock())
        pump.active.set()
        def wait(_seconds):
            if reads.call_count >= 2:
                pump.stop_event.set()
        with patch("hackomon.expedition.radio.gps_fix", side_effect=[
                radio.GPSFixError(dict(code="missing_accuracy")),
                dict(lat=-20, lon=-40, accuracy=8, altitude=0, fix_time=NOW)]) as reads, \
                patch.object(pump.stop_event, "wait", side_effect=wait):
            pump._gps()
        values = []
        while not pump.events.empty():
            values.append(pump.events.get_nowait())
        self.assertEqual(["missing_accuracy", "valid"],
                         [value["code"] for kind, value in values if kind == "gps_health"])
        self.assertEqual(1, len([1 for kind, _ in values if kind == "gps"]))

    def test_recent_failure_overrides_last_fix_and_persists_bounded_history(self):
        with support.temporary_directory() as directory:
            app = HackomonApp(MemoryDisplay(), CreatureCatalog.load_default(), StateStore(directory), clock=lambda: NOW)
            pump = MagicMock()
            pump.events = queue.Queue()
            with patch("hackomon.app.expedition.Pump", return_value=pump):
                app._start_expedition()
            app.journal.summary["gps_at"] = NOW
            pump.events.put(("gps_health", dict(code="bad_accuracy", accuracy_m=150, lat=-20)))
            app._tick_expedition()
            state, text = expedition.sensor_status(app.journal.summary, "gps", NOW)
            self.assertEqual("waiting", state)
            self.assertIn("precisao insuficiente", text)
            self.assertEqual("bad_accuracy", expedition.Journal.restore(directory).summary["gps_health"]["code"])
            self.assertNotIn("lat", app.journal.summary["gps_health"])
            for index in range(20):
                app.journal.gps_health(dict(code="no_fix" if index % 2 else "valid"), NOW)
            self.assertEqual(8, len(app.journal.summary["gps_recent"]))
            self.assertEqual("waiting", expedition.sensor_status(app.journal.summary, "gps", NOW + 16)[0])
            app.journal.gps_health(dict(code="valid"), NOW)
            self.assertEqual("ok", expedition.sensor_status(app.journal.summary, "gps", NOW)[0])
            app.screen = "expedition"
            app.render(0)

    def test_unchanged_health_is_saved_at_most_every_thirty_seconds(self):
        with support.temporary_directory() as directory:
            journal = expedition.Journal(directory, now=NOW)
            with patch.object(journal, "checkpoint") as save:
                for offset in range(61):
                    journal.gps_health(dict(code="no_fix"), NOW + offset)
            self.assertEqual(3, save.call_count)
            self.assertEqual(1, len(journal.summary["gps_recent"]))


if __name__ == "__main__":
    unittest.main()
