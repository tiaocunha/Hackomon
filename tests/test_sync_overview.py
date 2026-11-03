import io
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from tests import support
from tests.test_networks import observation
from tests.test_sync import Client, KEY, NOW, manager, source
from hackomon.app import HackomonApp
from hackomon.catalog import CreatureCatalog
from hackomon.exploration import export_csv, record_observations
from hackomon.pager_backend import MemoryDisplay
from hackomon.storage import StateStore
from hackomon.sync import Manager, guidance
from hackomon import wdgwars


class OverviewTests(unittest.TestCase):
    def test_all_sources_and_queue_are_counted_without_duplicate_queue_rows_or_http(self):
        with support.temporary_directory() as directory:
            source(directory, 601)
            source(directory, 2, "2" * 32)
            client = Client()
            instance = manager(directory, client)
            overview = instance.overview([observation(1), observation(900)])
            self.assertEqual((604, 603, 1, 2), tuple(overview[k] for k in (
                "pending", "csv_records", "queue_records", "pending_expeditions")))
            self.assertEqual((0, []), (client.gets, client.posts))
            self.assertFalse(instance.path.exists())

    def test_overview_does_not_silently_use_500_source_upload_limit(self):
        with support.temporary_directory() as directory:
            for index in range(501):
                source(directory, 1, "%032x" % index)
            instance = manager(directory, Client())
            self.assertEqual(500, len(instance.sources()))
            overview = instance.overview()
            self.assertEqual((501, 501), (overview["pending"], overview["scanned"]))

    def test_confirmed_batch_remains_distinct_from_remote_import_counts_and_survives_history_trim(self):
        with support.temporary_directory() as directory:
            source(directory, 1)
            client = Client(lambda *args: {"ok": True, "imported": 0, "bad_rows": 1})
            instance = manager(directory, client)
            report = instance.run("expeditions")
            self.assertEqual("done_with_warnings", report["status"])
            self.assertEqual(0, report["overview"]["pending"])
            self.assertEqual({"at": NOW, "records": 1, "warnings": True}, report["overview"]["last_confirmed"])
            for _ in range(101):
                instance.note("archived_local")
            instance.save()
            self.assertEqual(NOW, manager(directory, client).overview()["last_confirmed"]["at"])

    def test_old_manifest_uses_confirmed_history_but_not_account_checks_or_remote_jobs(self):
        with support.temporary_directory() as directory:
            instance = manager(directory, Client())
            instance.note("confirmed", records=42)
            instance.note("pending_remote", records=200)
            instance.save()
            overview = manager(directory, Client()).overview()
            self.assertEqual({"at": NOW, "records": 42}, overview["last_confirmed"])

    def test_bad_row_and_partial_tail_are_not_ready_to_send(self):
        with support.temporary_directory() as directory:
            path = source(directory, 1)
            with path.open("ab") as handle:
                handle.write(b"not,a,valid,row\npartial")
            overview = manager(directory, Client()).overview()
            self.assertEqual((1, 1, 1), (overview["pending"], overview["skipped"], overview["incomplete"]))

    def test_missing_and_changed_sources_never_claim_zero_pending(self):
        for missing in (False, True):
            with self.subTest(missing=missing), support.temporary_directory() as directory:
                path = source(directory, 1)
                instance = manager(directory, Client())
                instance.run("expeditions")
                if missing:
                    path.unlink()
                else:
                    path.write_bytes(export_csv([observation(900)]))
                overview = manager(directory, Client()).overview()
                self.assertIsNone(overview["pending"])
                self.assertEqual(1, overview["source_errors"])

    def test_missing_csv_of_unsent_expedition_is_detected_from_summary(self):
        with support.temporary_directory() as directory:
            path = source(directory, 1)
            (path.parent / "summary.json").write_text(json.dumps({"located": 1}))
            path.unlink()
            self.assertIsNone(manager(directory, Client()).overview()["pending"])

    def test_cancelled_local_read_keeps_cursors_and_originals(self):
        with support.temporary_directory() as directory:
            path = source(directory, 601)
            before = path.read_bytes()
            cancel = threading.Event()
            cancel.set()
            instance = manager(directory, Client(), cancel=cancel)
            overview = instance.overview()
            self.assertFalse(overview["complete"])
            self.assertIsNone(overview["pending"])
            self.assertEqual({}, instance.state["files"])
            self.assertEqual(before, path.read_bytes())

    def test_account_timeout_is_not_an_uncertain_upload_and_429_delay_is_persisted(self):
        for code in (0, 429, 401):
            with self.subTest(code=code), support.temporary_directory() as directory:
                source(directory, 1)
                client = Client()
                error = urllib.error.URLError("offline") if not code else urllib.error.HTTPError(
                    wdgwars.ACCOUNT_ENDPOINT, code, "test", {"Retry-After": "90"}, io.BytesIO())
                client.open = lambda *args, **kwargs: (_ for _ in ()).throw(error)
                instance = manager(directory, client)
                result = instance.run("expeditions")
                self.assertEqual({0: "connection_error", 429: "rate_limited", 401: "credentials"}[code], result["status"])
                self.assertIsNone(instance.state["inflight"])
                self.assertIsNone(result["overview"]["last_confirmed"])
                self.assertEqual(1, result["overview"]["pending"])
                if code == 429:
                    self.assertEqual(NOW + 90, manager(directory, Client()).state["retry_at"])
                self.assertNotIn(KEY, json.dumps(result))

    def test_ui_local_overview_does_not_lock_radios_or_upload_and_preserves_queue(self):
        with support.temporary_directory() as directory:
            source(directory, 2)
            app = HackomonApp(MemoryDisplay(), CreatureCatalog.load_default(), StateStore(directory), clock=lambda: NOW)
            record_observations(app.state, [observation(1), observation(9)], NOW)
            app.screen = "wdgwars"
            client = Client()
            def factory(*args, **kwargs):
                return manager(directory, client)
            app.radio_lock.acquire()
            try:
                with patch("hackomon.app.load_config", return_value={"wdgwars_api_key": KEY}), \
                        patch("hackomon.app.wdg_sync.Manager", side_effect=factory):
                    app._handle_wdgwars(app.display.BTN_RIGHT)
                    app.worker.join(timeout=2)
                    self.assertFalse(app.worker.is_alive())
            finally:
                app.radio_lock.release()
            app._finish_network_job()
            self.assertEqual("wdgwars_overview", app.screen)
            self.assertEqual(3, app.sync_status["overview"]["pending"])
            self.assertEqual(2, len(app.state.network_queue))
            self.assertEqual((0, []), (client.gets, client.posts))
            app.render(0)
            for op in app.display.operations:
                if op[0] == "text":
                    self.assertLessEqual(op[1] + app.display.text_width(op[3], op[5]), 480, op)
                elif op[0] == "center":
                    self.assertLessEqual(app.display.text_width(op[2], op[4]), 480, op)
            app._handle_wdgwars(app.display.BTN_A)
            self.assertEqual("wdgwars_confirm", app.screen)
            self.assertIsNone(app.worker)

    def test_recovery_actions_fit_screen_and_distinguish_credentials_connection_and_post(self):
        for status in ("rate_limited", "credentials", "connection_error", "uncertain", "sending",
                       "pending_remote", "needs_confirmation", "rejected", "error", "cancelled"):
            for tip in guidance(status, 604800):
                self.assertLessEqual(len(tip), 72)
        self.assertNotIn("Repetir", " ".join(guidance("connection_error")))
        self.assertIn("duplicar", " ".join(guidance("uncertain")))

    def test_missing_key_has_credentials_guidance_and_unknown_counts(self):
        with support.temporary_directory() as directory:
            app = HackomonApp(MemoryDisplay(), CreatureCatalog.load_default(), StateStore(directory), clock=lambda: NOW)
            app.screen = "wdgwars"
            with patch("hackomon.app.load_config", return_value={}):
                app._handle_wdgwars(app.display.BTN_RIGHT)
                app.worker.join(timeout=2)
            app._finish_network_job()
            self.assertEqual("credentials", app.sync_status["status"])
            app.render(0)
            texts = [op[3] for op in app.display.operations if op[0] == "text"]
            self.assertIn("Prontos para enviar: desconhecido", texts)
            self.assertIn("Confira a chave e a permissao da conta.", texts)

    def test_late_progress_cannot_replace_final_receipt_and_overview(self):
        with support.temporary_directory() as directory:
            app = HackomonApp(MemoryDisplay(), CreatureCatalog.load_default(), StateStore(directory), clock=lambda: NOW)
            app.worker = MagicMock()
            app.sync_events.put(dict(status="ready", message="Enviando..."))
            final = dict(status="done", sent=1, overview={"pending": 0})
            app.results.put(("sync", final, None))
            app._finish_network_job()
            app._drain_sync_progress()
            self.assertEqual("done", app.sync_status["status"])
            self.assertEqual(0, app.sync_status["overview"]["pending"])


if __name__ == "__main__":
    unittest.main()
