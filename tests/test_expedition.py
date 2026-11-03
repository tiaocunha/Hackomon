import json
import queue
import threading
import unittest
from unittest.mock import MagicMock, patch

from tests import support
from tests.test_networks import observation
from tests.test_visit import target, NOW
from hackomon import expedition, radio
from hackomon.app import HackomonApp
from hackomon.catalog import CreatureCatalog
from hackomon.exploration import record_observations
from hackomon.pager_backend import MemoryDisplay
from hackomon.storage import StateStore


def fix(stamp=NOW, lat=-23.5, lon=-46.6):
    return dict(fix_time=stamp, lat=lat, lon=lon, accuracy=8, altitude=700)


class ExpeditionTests(unittest.TestCase):
    def test_journal_survives_restart_without_restoring_active_scope(self):
        with support.temporary_directory() as directory:
            journal = expedition.Journal(directory, now=NOW)
            journal.status("running")
            journal.observations([observation()])
            restored = expedition.Journal.restore(directory)
            self.assertEqual("paused", restored.summary["status"])
            self.assertEqual(1, restored.summary["wifi"])
            self.assertEqual([], restored.observations([observation()]))
            self.assertEqual(journal.summary["id"], restored.summary["id"])

    def test_unlocated_and_optout_records_do_not_enter_csv(self):
        with support.temporary_directory() as directory:
            journal = expedition.Journal(directory, now=NOW)
            raw = target()
            journal.observations([raw, dict(raw, mac="02:00:00:00:00:02", name="Private_nomap")])
            self.assertEqual(1, journal.summary["unlocated"])
            self.assertEqual(1, journal.summary["wifi"])
            self.assertFalse((journal.folder / "discoveries.csv").exists())
            self.assertNotIn("Private_nomap", (journal.folder / "observations.jsonl").read_text())

    def test_location_match_uses_time_and_handles_movement(self):
        pump = expedition.Pump({}, threading.Lock())
        pump.fixes.extend([fix(NOW - 10, lon=-46.61), fix(NOW, lon=-46.60)])
        first = dict(target(), timestamp=NOW - 10, time_source="iw_age")
        second = dict(target(), timestamp=NOW, time_source="iw_age")
        self.assertEqual(-46.61, pump.locate(first)["lon"])
        self.assertEqual(-46.60, pump.locate(second)["lon"])
        self.assertNotIn("lat", pump.locate(dict(first, timestamp=NOW - 100)))
        self.assertNotIn("lat", pump.locate(dict(first, time_source="unknown")))

    def test_iw_age_is_distinct_from_scan_end_and_missing_age_stays_unlocated(self):
        text = "BSS 02:00:00:00:00:01\n signal: -40 dBm\n last seen: 10000 ms ago\n"
        item = radio.wifi_observations(text, NOW)[0]
        self.assertEqual(NOW - 10, item["timestamp"])
        self.assertEqual("iw_age", item["time_source"])
        self.assertNotIn("time_source", target())

    def test_distance_rejects_large_jumps_and_does_not_bridge_pause(self):
        with support.temporary_directory() as directory:
            journal = expedition.Journal(directory, now=NOW)
            journal.gps(fix())
            journal.gps(fix(NOW + 5, lon=-46.599))
            measured = journal.summary["distance_m"]
            self.assertGreater(measured, 50)
            journal.gps(fix(NOW + 6, lon=40))
            self.assertEqual(measured, journal.summary["distance_m"])
            self.assertEqual(1, journal.summary["gps_gaps"])
            journal.status("paused")
            journal.status("running")
            journal.gps(fix(NOW + 100, lon=-46.5))
            self.assertEqual(measured, journal.summary["distance_m"])

    def test_full_map_queue_does_not_lose_expedition_csv(self):
        with support.temporary_directory() as directory:
            app = HackomonApp(MemoryDisplay(), CreatureCatalog.load_default(), StateStore(directory), clock=lambda: NOW)
            record_observations(app.state, [observation(i) for i in range(500)], NOW)
            journal = expedition.Journal(directory, now=NOW)
            values = journal.observations([dict(observation(600), password="NEVER-EXPORT")])
            result = record_observations(app.state, values, NOW)
            self.assertTrue(result["full"])
            csv = (journal.folder / "discoveries.csv").read_text()
            self.assertIn("02:00:00:00:02:58", csv)
            self.assertNotIn("NEVER-EXPORT", csv)

    def test_stationary_fixes_do_not_invent_gps_gaps_or_distance(self):
        with support.temporary_directory() as directory:
            journal = expedition.Journal(directory, now=NOW)
            for seconds in range(35):
                journal.gps(fix(NOW + seconds))
            self.assertEqual(0, journal.summary["gps_gaps"])
            self.assertEqual(0, journal.summary["distance_m"])

    def test_confirmed_audits_are_separate_from_discovery_export(self):
        with support.temporary_directory() as directory:
            journal = expedition.Journal(directory, now=NOW)
            journal.observations([observation()])
            journal.audit({"report": {"target": {"mac": observation()["mac"]},
                                      "capture": {"status": "eapol_observed"},
                                      "dictionary": {"status": "inconclusive"}, "password": "SECRET"}})
            self.assertEqual(0, journal.summary["recoveries"])
            journal.status("ended")
            self.assertTrue((journal.folder / "summary.txt").exists())
            self.assertNotIn("SECRET", (journal.folder / "audits.jsonl").read_text())
            self.assertNotIn("inconclusive", (journal.folder / "discoveries.csv").read_text())

    def test_scheduler_releases_radio_lock_and_uses_only_discovery(self):
        lock = threading.Lock()
        pump = expedition.Pump({"expedition_ble": False}, lock)
        pump.active.set()
        pump.fixes.append(fix())
        value = dict(target(), time_source="iw_age")
        def scan(config, limit):
            self.assertEqual(500, limit)
            self.assertFalse(lock.acquire(blocking=False))
            pump.stop_event.set()
            return [value]
        with patch("hackomon.expedition.visit.find_networks", side_effect=scan), \
                patch("hackomon.visit.lab.capture") as capture:
            pump._scan()
        capture.assert_not_called()
        self.assertTrue(lock.acquire(blocking=False))
        lock.release()
        self.assertEqual("targets", pump.events.get_nowait()[0])
        kind, values = pump.events.get_nowait()
        self.assertEqual("observations", kind)
        self.assertIn("lat", values[0])

    def test_ble_receive_times_and_late_optout_names(self):
        pump = expedition.Pump({}, threading.Lock())
        pump.fixes.append(fix())
        process = MagicMock()
        process.__enter__.return_value = process
        process.stdout = ["[CHG] Device C3:00:00:00:00:01 RSSI: -55\n",
                          "[CHG] Device C3:00:00:00:00:01 Name: Private_optout\n"]
        process.poll.return_value = 0
        process.returncode = 0
        with patch("hackomon.expedition.time.time", return_value=NOW), \
                patch("hackomon.expedition.radio.bluetooth_ready"), \
                patch("hackomon.expedition.subprocess.Popen", return_value=process):
            values = pump._ble()
        self.assertEqual("Private_optout", values[0]["name"])
        self.assertEqual("ble_receipt", values[0]["time_source"])
        self.assertIn("lat", values[0])

    def test_upload_snapshot_preserves_discoveries_arriving_during_send(self):
        with support.temporary_directory() as directory:
            app = HackomonApp(MemoryDisplay(), CreatureCatalog.load_default(), StateStore(directory), clock=lambda: NOW)
            record_observations(app.state, [observation(1)], NOW)
            def send(snapshot, key):
                return len(snapshot)
            with patch("hackomon.app.wdgwars.upload", side_effect=send):
                app._network_job("upload")
                app.worker.join()
            record_observations(app.state, [observation(2)], NOW)
            app._finish_network_job()
            self.assertEqual([observation(2)["mac"]], [item["mac"] for item in app.state.network_queue])

    def test_ui_pause_resume_scoped_audit_and_resume_no_real_radio(self):
        with support.temporary_directory() as directory:
            app = HackomonApp(MemoryDisplay(), CreatureCatalog.load_default(), StateStore(directory), clock=lambda: NOW)
            pump = MagicMock()
            pump.events = queue.Queue()
            pump.alive.return_value = False
            pump.dropped = 0
            with patch("hackomon.app.expedition.Pump", return_value=pump):
                app.screen = "expedition"
                app._handle_expedition(app.display.BTN_A)
            self.assertEqual("running", app.journal.summary["status"])
            pump.events.put(("targets", [target()]))
            pump.events.put(("observations", [observation()]))
            app._tick_expedition()
            self.assertEqual(2, app.journal.summary["xp"])
            app._handle_expedition(app.display.BTN_RIGHT)
            self.assertEqual("visit", app.screen)
            report = dict(target=target(), findings=[], capture={"status": "inconclusive"},
                          dictionary={"status": "not_run"})
            result = dict(report=report, completed=True, reward_id="visit:" + target()["mac"], message="Saved")
            with patch("hackomon.app.visit.assess", return_value=result) as assess:
                app._handle_visit(app.display.BTN_A)
                app.worker.join()
            app._finish_network_job()
            self.assertEqual(target()["mac"], assess.call_args.args[1]["mac"])
            self.assertEqual("running", app.journal.summary["status"])
            self.assertEqual(1, app.journal.summary["audits"])
            self.assertEqual(1, len(app.state.network_queue))
            app._handle_visit(app.display.BTN_B)
            self.assertEqual("expedition", app.screen)
            app.render(0)
            app._handle_expedition(app.display.BTN_LEFT)
            app._tick_expedition()
            self.assertEqual("ended", app.journal.summary["status"])
            self.assertEqual([], app.expedition_targets)

    def test_failed_start_remains_paused_and_can_be_retried(self):
        with support.temporary_directory() as directory:
            app = HackomonApp(MemoryDisplay(), CreatureCatalog.load_default(), StateStore(directory), clock=lambda: NOW)
            broken = MagicMock()
            broken.start.side_effect = RuntimeError("thread unavailable")
            with patch("hackomon.app.expedition.Pump", return_value=broken):
                app._handle_expedition(app.display.BTN_A)
            self.assertIsNone(app.pump)
            self.assertEqual("paused", app.journal.summary["status"])
            healthy = MagicMock()
            with patch("hackomon.app.expedition.Pump", return_value=healthy):
                app._handle_expedition(app.display.BTN_A)
            self.assertEqual("running", app.journal.summary["status"])
            healthy.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
