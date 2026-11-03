"""Field regressions: long outings, readable feedback and local upload recovery."""

import queue
import unittest
from unittest.mock import MagicMock, patch

from tests import support
from tests.test_networks import observation
from tests.test_sync import Client, KEY, manager, source
from hackomon.app import HackomonApp
from hackomon.catalog import CreatureCatalog
from hackomon.expedition import Journal, sensor_status
from hackomon.exploration import record_observations, reward_discoveries
from hackomon.pager_backend import MemoryDisplay
from hackomon.storage import StateStore


NOW = 1700000000


class CompanionTests(unittest.TestCase):
    def app(self, directory):
        app = HackomonApp(MemoryDisplay(), CreatureCatalog.load_default(), StateStore(directory), clock=lambda: NOW)
        pump = MagicMock()
        pump.events = queue.Queue()
        pump.dropped = 0
        pump.alive.return_value = True
        with patch("hackomon.app.expedition.Pump", return_value=pump):
            app._start_expedition()
        return app, pump

    def test_long_outing_bypasses_full_legacy_queue_and_survives_restart(self):
        with support.temporary_directory() as directory:
            app, pump = self.app(directory)
            record_observations(app.state, [observation(i) for i in range(500)], NOW)
            previous_queue = list(app.state.network_queue)
            values = [observation(i) for i in range(1000, 1601)]
            pump.events.put(("observations", values))
            app._tick_expedition()
            self.assertEqual(previous_queue, app.state.network_queue)
            self.assertEqual(601, app.journal.summary["located"])
            self.assertEqual(1202, app.journal.summary["xp"])
            self.assertEqual(601, app.journal.summary["rewarded_discoveries"])
            self.assertNotIn("cheia", app.expedition_message)
            csv = app.journal.folder / "discoveries.csv"
            self.assertEqual(603, len(csv.read_bytes().splitlines()))
            restored = Journal.restore(directory)
            self.assertEqual(601, restored.summary["wifi"])
            loaded, warning = app.store.load_or_create(app.catalog, now=NOW)
            self.assertIsNone(warning)
            self.assertEqual(0, reward_discoveries(loaded, values, NOW)["xp"])
            client = Client()
            result = manager(directory, client).run("expeditions", previous_queue)
            self.assertEqual(1101, result["sent"])
            self.assertEqual([500, 101, 500], [len(rows) for _, rows in client.posts])
            self.assertEqual(0, manager(directory, client).expedition_pending(restored.summary["id"])["pending"])

    def test_feedback_distinguishes_new_known_empty_and_invalid_observations(self):
        with support.temporary_directory() as directory:
            app, pump = self.app(directory)
            samples = [([observation()], "+2 XP"),
                       ([observation()], "XP ja concedido"),
                       ([], "sem descobertas recentes"),
                       ([dict(observation(2), rssi=127)], "invalidos/antigos")]
            for values, expected in samples:
                pump.events.put(("observations", values))
                app._tick_expedition()
                self.assertIn(expected, app.expedition_message)
            self.assertEqual(2, app.journal.summary["xp"])
            self.assertEqual(1, app.journal.summary["rewarded_discoveries"])
            self.assertEqual([], app.state.network_queue)

    def test_summary_counts_current_expedition_and_does_not_contact_service(self):
        with support.temporary_directory() as directory:
            app, pump = self.app(directory)
            pump.events.put(("observations", [observation(), observation(2, "BLE")]))
            app._tick_expedition()
            client = Client()
            def factory(data_dir, key, **kwargs):
                return manager(data_dir, client)
            with patch("hackomon.app.load_config", return_value={"wdgwars_api_key": KEY}), \
                    patch("hackomon.app.wdg_sync.Manager", side_effect=factory):
                app._handle_expedition(app.display.BTN_DOWN)
            self.assertTrue(app.expedition_details)
            self.assertEqual(2, app.journal.summary["upload"]["pending"])
            self.assertEqual((0, []), (client.gets, client.posts))
            app.screen = "expedition"
            app.render(0)
            texts = [op[3] for op in app.display.operations if op[0] == "text"]
            self.assertIn("WDG pendentes: 2", texts)
            self.assertIn("Wi-Fi 1  BLE 1", texts)

    def test_finalization_writes_one_summary_and_restores_it(self):
        with support.temporary_directory() as directory:
            app, pump = self.app(directory)
            pump.events.put(("observations", [observation()]))
            app._tick_expedition()
            app._handle_expedition(app.display.BTN_LEFT)
            pump.alive.return_value = False
            with patch("hackomon.app.load_config", return_value={}):
                app._tick_expedition()
            self.assertEqual("ended", app.journal.summary["status"])
            self.assertTrue(app.expedition_details)
            self.assertIsNone(app.pump)
            self.assertIsNone(app.journal.summary["upload"]["pending"])
            app.journal.write_summary()
            text = (app.journal.folder / "summary.txt").read_text(encoding="utf-8")
            self.assertEqual(1, text.count("HACKOMON - RESUMO"))
            self.assertIn("aguardando envio: desconhecido", text)
            self.assertEqual("ended", Journal.restore(directory).summary["status"])

    def test_config_missing_and_corrupt_receipt_never_claim_zero_pending(self):
        with support.temporary_directory() as directory:
            app, pump = self.app(directory)
            pump.events.put(("observations", [observation()]))
            app._tick_expedition()
            with patch("hackomon.app.load_config", return_value={}):
                app._refresh_expedition_upload()
            self.assertIsNone(app.journal.summary["upload"]["pending"])
            instance = manager(directory, Client())
            instance.path.write_text("broken", encoding="utf-8")
            with patch("hackomon.app.load_config", return_value={"wdgwars_api_key": KEY}):
                app._refresh_expedition_upload()
            self.assertIsNone(app.journal.summary["upload"]["pending"])
            self.assertIn("preservado", app.journal.summary["upload"]["message"])

    def test_no_located_records_is_zero_without_key(self):
        with support.temporary_directory() as directory:
            app, pump = self.app(directory)
            with patch("hackomon.app.load_config", return_value={}):
                app._refresh_expedition_upload()
            self.assertEqual(0, app.journal.summary["upload"]["pending"])

    def test_missing_original_csv_is_unknown_instead_of_zero(self):
        with support.temporary_directory() as directory:
            app, pump = self.app(directory)
            pump.events.put(("observations", [observation()]))
            app._tick_expedition()
            (app.journal.folder / "discoveries.csv").unlink()
            with patch("hackomon.app.load_config", return_value={"wdgwars_api_key": KEY}):
                app._refresh_expedition_upload()
            self.assertIsNone(app.journal.summary["upload"]["pending"])
            self.assertIn("CSV ausente", app.journal.summary["upload"]["message"])

    def test_older_expedition_keeps_totals_and_marks_new_counter_partial(self):
        with support.temporary_directory() as directory:
            journal = Journal(directory, now=NOW)
            journal.summary.update(wifi=100, ble=50, xp=200)
            journal.summary.pop("rewarded_discoveries")
            journal.checkpoint()
            restored = Journal.restore(directory)
            self.assertTrue(restored.summary["reward_count_partial"])
            self.assertEqual((100, 50, 200), tuple(restored.summary[k] for k in ("wifi", "ble", "xp")))

    def test_summary_layout_fits_screen_and_live_pending_grows_without_disk_rescan(self):
        with support.temporary_directory() as directory:
            app, pump = self.app(directory)
            app.journal.summary["upload"] = dict(pending=0, message="Sincronize no menu WDGWars")
            pump.events.put(("observations", [observation()]))
            app._tick_expedition()
            self.assertEqual(1, app.journal.summary["upload"]["pending"])
            app.journal.summary.update(wifi=10000, ble=10000, distance_m=10000000, xp=20000)
            for details in (False, True):
                app.display.operations.clear()
                app.ui.expedition(app.state, app.journal.summary, app.expedition_message,
                                  details=details, now=NOW)
                for op in app.display.operations:
                    if op[0] == "text":
                        self.assertLessEqual(op[1] + app.display.text_width(op[3], op[5]), 480, op)
                        self.assertLessEqual(op[2] + 8 * op[5], 222, op)
                    elif op[0] == "center":
                        self.assertLessEqual(app.display.text_width(op[2], op[4]), 480, op)

    def test_radio_success_error_and_gps_recovery_have_independent_states(self):
        with support.temporary_directory() as directory:
            app, pump = self.app(directory)
            pump.events.put(("radio_status", dict(radio="wifi", ok=True, count=0)))
            pump.events.put(("radio_status", dict(radio="ble", ok=False, message="Bluetooth desligado")))
            pump.events.put(("gps_error", "Sem fix"))
            app._tick_expedition()
            summary = app.journal.summary
            self.assertEqual("empty", sensor_status(summary, "wifi", NOW)[0])
            self.assertEqual("error", sensor_status(summary, "ble", NOW)[0])
            self.assertEqual("waiting", sensor_status(summary, "gps", NOW)[0])
            pump.events.put(("gps", dict(fix_time=NOW, lat=-23.5, lon=-46.6, accuracy=8, altitude=700)))
            app._tick_expedition()
            self.assertEqual("ok", sensor_status(summary, "gps", NOW)[0])
            self.assertNotIn("gps_error", summary)
            self.assertEqual("waiting", sensor_status(summary, "wifi", NOW + 46)[0])
            self.assertEqual("waiting", sensor_status(summary, "gps", NOW + 16)[0])
            app.journal.status("paused")
            self.assertEqual("pausado", sensor_status(summary, "wifi", NOW)[0])

    def test_sensor_disabled_searching_future_timestamp_and_resume(self):
        summary = dict(status="running", radios={"ble": {"state": "disabled"}}, gps_at=NOW + 10)
        self.assertEqual("disabled", sensor_status(summary, "ble", NOW)[0])
        self.assertEqual("waiting", sensor_status(summary, "wifi", NOW)[0])
        self.assertEqual("ok", sensor_status(summary, "gps", NOW)[0])
        with support.temporary_directory() as directory:
            app, pump = self.app(directory)
            app.journal.summary["gps_at"] = NOW
            app.journal.status("paused")
            app._start_expedition()
            self.assertNotIn("gps_at", app.journal.summary)

    def test_pending_count_uses_persisted_receipts_and_unconfirmed_lot_remains_pending(self):
        import urllib.error

        with support.temporary_directory() as directory:
            path = source(directory, 601)
            client = Client(lambda n, *args: {"ok": True} if n == 1 else urllib.error.URLError("offline"))
            first = manager(directory, client)
            first.run("expeditions")
            restarted = manager(directory, client)
            overview = restarted.expedition_pending(path.parent.name)
            self.assertEqual(101, overview["pending"])
            self.assertIn("incerto", overview["message"])
            requests = (client.gets, len(client.posts))
            self.assertEqual("needs_confirmation", restarted.run("expeditions")["status"])
            self.assertEqual(requests, (client.gets, len(client.posts)))
            client.behavior = None
            manager(directory, client).run("retry", retry_uncertain=True)
            self.assertEqual(0, manager(directory, client).expedition_pending(path.parent.name)["pending"])

    def test_partial_upload_resumes_after_restart_without_replaying_confirmed_rows(self):
        import io
        import urllib.error
        from hackomon import wdgwars

        with support.temporary_directory() as directory:
            path = source(directory, 601)
            before = path.read_bytes()
            error = urllib.error.HTTPError(wdgwars.ENDPOINT, 429, "rate", {"Retry-After": "2"}, io.BytesIO())
            client = Client(lambda n, *args: {"ok": True} if n == 1 else error)
            manager(directory, client).run("expeditions")
            overview = manager(directory, client).expedition_pending(path.parent.name)
            self.assertEqual(101, overview["pending"])
            self.assertIn("Retomar", overview["message"])
            client.behavior = None
            instance = manager(directory, client)
            instance.clock = lambda: NOW + 3
            result = instance.run("expeditions")
            self.assertEqual(("done", 101), (result["status"], result["sent"]))
            self.assertEqual([500, 101, 101], [len(rows) for _, rows in client.posts])
            self.assertEqual(before, path.read_bytes())


if __name__ == "__main__":
    unittest.main()
