import csv
import io
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
import urllib.error

from tests import support
from tests.test_networks import observation
from hackomon import wdgwars
from hackomon.app import HackomonApp
from hackomon.catalog import CreatureCatalog
from hackomon.exploration import export_csv, record_observations
from hackomon.pager_backend import MemoryDisplay
from hackomon.storage import StateStore
from hackomon.sync import Manager, token


KEY = "a" * 64
ID = "1" * 32
NOW = 1700000000


class Response(io.BytesIO):
    def __init__(self, value, status=200):
        super().__init__(json.dumps(value).encode() if not isinstance(value, bytes) else value)
        self.status = status


class Client:
    def __init__(self, behavior=None):
        self.posts = []
        self.gets = 0
        self.behavior = behavior

    def open(self, request, timeout):
        if request.get_method() == "GET":
            self.gets += 1
            return Response(dict(ok=True, username="test-account", wifi=10, ble=2, total=12))
        data = request.data.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n--", 1)[0]
        rows = list(csv.DictReader(io.StringIO(data.decode().split("\n", 1)[1])))
        self.posts.append((data, rows))
        value = self.behavior(len(self.posts), data, rows) if self.behavior else {"ok": True, "imported": len(rows)}
        if isinstance(value, Exception):
            raise value
        if isinstance(value, tuple):
            return Response(value[1], value[0])
        return Response(value)


def source(directory, count, identity=ID):
    folder = Path(directory) / "expeditions" / identity
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "discoveries.csv"
    path.write_bytes(export_csv([observation(index) for index in range(1, count + 1)]))
    return path


def manager(directory, client, **kwargs):
    return Manager(directory, KEY, opener=client, wait=lambda seconds: False, clock=lambda: NOW, **kwargs)


class SyncTests(unittest.TestCase):
    def test_all_expedition_rows_upload_in_small_batches_and_resume_without_duplicates(self):
        with support.temporary_directory() as directory:
            path = source(directory, 1001)
            original = path.read_bytes()
            queue = [observation(i) for i in range(1, 501)]
            client = Client()
            first = manager(directory, client).run("expeditions", queue)
            self.assertEqual("done", first["status"])
            self.assertEqual([500, 500, 1], [len(rows) for _, rows in client.posts])
            self.assertEqual(500, len(first["cleared_tokens"]))
            self.assertEqual(1001, first["counters"]["imported"])
            second = manager(directory, client).run("expeditions", queue)
            self.assertEqual(0, second["sent"])
            self.assertEqual(3, len(client.posts))
            self.assertEqual(original, path.read_bytes())

    def test_timeout_preserves_exact_batch_and_requires_confirmation_before_repeat(self):
        def behavior(number, data, rows):
            return urllib.error.URLError("network lost") if number == 2 else {"ok": True}
        with support.temporary_directory() as directory:
            source(directory, 1001)
            client = Client(behavior)
            failed = manager(directory, client).run("expeditions")
            self.assertEqual("uncertain", failed["status"])
            self.assertEqual(500, failed["sent"])
            blocked = manager(directory, client).run("expeditions")
            self.assertEqual("needs_confirmation", blocked["status"])
            self.assertEqual(2, len(client.posts))
            retry = manager(directory, client).run("retry", retry_uncertain=True)
            self.assertEqual(client.posts[1][0], client.posts[2][0])
            self.assertEqual(500, retry["sent"])
            done = manager(directory, client).run("expeditions")
            self.assertEqual(1, done["sent"])
            self.assertEqual([500, 500, 500, 1], [len(rows) for _, rows in client.posts])

    def test_retry_after_is_persisted_and_blocks_early_requests(self):
        error = urllib.error.HTTPError(wdgwars.ENDPOINT, 429, "rate", {"Retry-After": "90"}, io.BytesIO(b"private error"))
        client = Client(lambda number, data, rows: error if number == 1 else {"ok": True})
        with support.temporary_directory() as directory:
            source(directory, 1)
            first = manager(directory, client).run("expeditions")
            self.assertEqual("rate_limited", first["status"])
            gets = client.gets
            second = manager(directory, client).run("expeditions")
            self.assertEqual("rate_limited", second["status"])
            self.assertEqual(gets, client.gets)
            later = Manager(directory, KEY, opener=client, wait=lambda _: False, clock=lambda: NOW + 91)
            self.assertEqual("done", later.run("expeditions")["status"])
            self.assertEqual(client.posts[0][0], client.posts[1][0])

    def test_async_acceptance_does_not_advance_import_cursor(self):
        client = Client(lambda number, data, rows: (202, {"job_id": "job-123"}))
        with support.temporary_directory() as directory:
            source(directory, 1)
            instance = manager(directory, client)
            result = instance.run("expeditions")
            self.assertEqual("pending_remote", result["status"])
            self.assertNotIn(ID, instance.state["files"])
            self.assertEqual("job-123", instance.state["inflight"]["job_id"])
            self.assertEqual("needs_confirmation", manager(directory, client).run("expeditions")["status"])
            self.assertEqual(1, len(client.posts))

    def test_unknown_response_and_explicit_rejection_are_not_acknowledged(self):
        for reply, expected in (({"message": "unknown"}, "uncertain"),
                                ({"ok": False, "imported": 10}, "rejected"),
                                (b"not JSON", "uncertain")):
            with self.subTest(reply=reply), support.temporary_directory() as directory:
                source(directory, 1)
                instance = manager(directory, Client(lambda *args: reply))
                result = instance.run("expeditions")
                self.assertEqual(expected, result["status"])
                self.assertEqual(0, result["sent"])
                self.assertNotIn(ID, instance.state["files"])

    def test_counter_only_response_and_server_discards_remain_distinct(self):
        with support.temporary_directory() as directory:
            source(directory, 1)
            client = Client(lambda *args: {"imported": 0, "merged_samples": 0, "bad_rows": 1})
            result = manager(directory, client).run("expeditions")
            self.assertEqual("done_with_warnings", result["status"])
            self.assertEqual(1, result["sent"])
            self.assertEqual(0, result["counters"]["imported"])

    def test_append_during_sync_is_sent_on_next_run_and_partial_line_is_not_checkpointed(self):
        with support.temporary_directory() as directory:
            path = source(directory, 1)
            original = path.read_bytes()
            path.write_bytes(original + b"02:00:")
            client = Client()
            first = manager(directory, client).run("expeditions")
            self.assertEqual("partial", first["status"])
            self.assertEqual(1, first["sent"])
            row2 = export_csv([observation(2)]).split(b"\n", 2)[2]
            path.write_bytes(original + row2)
            second = manager(directory, client).run("expeditions")
            self.assertEqual("done", second["status"])
            self.assertEqual(1, second["sent"])
            self.assertEqual(observation(2)["mac"], client.posts[-1][1][0]["MAC"])

    def test_corrupted_prefix_or_truncated_original_blocks_retry(self):
        with support.temporary_directory() as directory:
            path = source(directory, 2)
            client = Client(lambda *args: urllib.error.URLError("offline"))
            manager(directory, client).run("expeditions")
            path.write_bytes(export_csv([observation(99)]))
            result = manager(directory, client).run("retry", retry_uncertain=True)
            self.assertEqual("error", result["status"])
            self.assertEqual(1, len(client.posts))

    def test_bad_gps_optout_and_unrelated_private_files_are_not_uploaded(self):
        with support.temporary_directory() as directory:
            path = source(directory, 1)
            lines = path.read_bytes().splitlines(keepends=True)
            row = next(csv.reader([lines[2].decode()]))
            row[7] = "nan"
            stream = io.StringIO(newline="")
            csv.writer(stream, lineterminator="\n").writerow(row)
            optout = export_csv([dict(observation(2), name="Private_nomap")]).split(b"\n", 2)[2]
            path.write_bytes(lines[0] + lines[1] + stream.getvalue().encode() + optout)
            private = Path(directory) / "lab"
            private.mkdir()
            (private / "password.key").write_text("NEVER-SEND")
            (private / "capture.pcap").write_bytes(b"SECRET-CAPTURE")
            client = Client()
            result = manager(directory, client).run("expeditions")
            self.assertEqual(0, len(client.posts))
            self.assertEqual(2, result["skipped"])
            self.assertTrue(path.exists())

    def test_cancellation_checkpoints_confirmed_batches_and_resumes_remainder(self):
        cancel = threading.Event()
        def behavior(number, data, rows):
            cancel.set()
            return {"ok": True}
        with support.temporary_directory() as directory:
            source(directory, 1001)
            client = Client(behavior)
            result = manager(directory, client, cancel=cancel).run("expeditions")
            self.assertEqual("cancelled", result["status"])
            self.assertEqual(500, result["sent"])
            client.behavior = None
            remaining = manager(directory, client).run("expeditions")
            self.assertEqual(501, remaining["sent"])

    def test_receipt_write_failure_does_not_clear_queue_and_requires_review_after_restart(self):
        with support.temporary_directory() as directory:
            source(directory, 1)
            client = Client()
            instance = manager(directory, client)
            original_save = instance.save
            def save():
                if instance.state["files"] and instance.state["inflight"] is None:
                    raise OSError("disk full")
                original_save()
            with patch.object(instance, "save", side_effect=save):
                result = instance.run("expeditions", [observation(1)])
            self.assertEqual("error", result["status"])
            self.assertEqual([], result["cleared_tokens"])
            restarted = manager(directory, client)
            self.assertEqual("sending", restarted.state["inflight"]["kind"])
            self.assertEqual("needs_confirmation", restarted.run("expeditions", [observation(1)])["status"])
            self.assertEqual(1, len(client.posts))

    def test_credentials_stay_out_of_history_and_keys_have_separate_cursors(self):
        with support.temporary_directory() as directory:
            source(directory, 1)
            client = Client()
            first = manager(directory, client)
            first.run("expeditions")
            self.assertNotIn(KEY, first.path.read_text())
            self.assertNotIn("Lab,", first.path.read_text())
            other = Manager(directory, "b" * 64, opener=client, wait=lambda _: False)
            self.assertNotEqual(first.path, other.path)
            self.assertEqual(1, other.run("expeditions")["sent"])

    def test_prepared_payload_path_cannot_escape_outbox(self):
        with support.temporary_directory() as directory:
            client = Client()
            instance = manager(directory, client)
            instance.state["inflight"] = dict(kind="prepared", payload="../lab/private.key")
            instance.save()
            result = manager(directory, client).run("queue")
            self.assertEqual("error", result["status"])
            self.assertEqual([], client.posts)

    def test_account_validation_is_get_only_and_cancel_ui_keeps_records(self):
        with support.temporary_directory() as directory:
            client = Client()
            report = manager(directory, client).run("account")
            self.assertEqual("account_ok", report["status"])
            self.assertEqual([], client.posts)
            self.assertEqual("test-account", report["account"]["username"])
            app = HackomonApp(MemoryDisplay(), CreatureCatalog.load_default(), StateStore(directory), clock=lambda: NOW)
            record_observations(app.state, [observation()], NOW)
            app.screen = "wdgwars"
            app.worker = object()
            app.worker_action = "sync"
            app._handle_wdgwars(app.display.BTN_B)
            self.assertTrue(app.sync_cancel.is_set())
            self.assertEqual(1, len(app.state.network_queue))
            app.render(0)

    def test_queue_only_does_not_resume_an_expedition_payload_and_archive_preserves_data(self):
        with support.temporary_directory() as directory:
            source(directory, 1)
            error = urllib.error.HTTPError(wdgwars.ENDPOINT, 429, "rate", {"Retry-After": "2"}, io.BytesIO())
            client = Client(lambda *args: error)
            first = manager(directory, client)
            first.run("expeditions")
            payload = first.outbox / first.state["inflight"]["payload"]
            later = Manager(directory, KEY, opener=client, wait=lambda _: False, clock=lambda: NOW + 3)
            self.assertEqual("pending_source", later.run("queue")["status"])
            self.assertEqual(1, len(client.posts))
            gets = client.gets
            archived = manager(directory, client).run("archive")
            self.assertEqual("archived", archived["status"])
            self.assertEqual(gets, client.gets)
            self.assertTrue(payload.exists())
            self.assertNotIn(ID, manager(directory, client).state["files"])

    def test_invalid_manifest_is_preserved_instead_of_resetting_receipts(self):
        with support.temporary_directory() as directory:
            instance = manager(directory, Client())
            original = dict(version=1, files={}, history=[], queue_receipts=[], account="broken")
            instance.path.write_text(json.dumps(original))
            with self.assertRaises(RuntimeError):
                manager(directory, Client())
            self.assertEqual(original, json.loads(instance.path.read_text()))

    def test_full_ui_sync_reaches_expedition_files_without_locking_radios(self):
        with support.temporary_directory() as directory:
            source(directory, 600)
            app = HackomonApp(MemoryDisplay(), CreatureCatalog.load_default(), StateStore(directory), clock=lambda: NOW)
            record_observations(app.state, [observation(index) for index in range(1, 501)], NOW)
            client = Client()
            def factory(data_dir, key, **kwargs):
                return Manager(data_dir, key, opener=client, wait=lambda _: False, **kwargs)
            app.screen = "network"
            app.network_selected = 4
            app._handle_network(app.display.BTN_A)
            app._handle_wdgwars(app.display.BTN_A)
            self.assertEqual("wdgwars_confirm", app.screen)
            self.assertIsNone(app.worker)
            app.radio_lock.acquire()
            try:
                with patch("hackomon.app.load_config", return_value={"wdgwars_api_key": KEY}), \
                        patch("hackomon.app.wdg_sync.Manager", side_effect=factory):
                    app._handle_wdgwars(app.display.BTN_A)
                    app.worker.join(timeout=2)
                    finished = not app.worker.is_alive()
            finally:
                app.radio_lock.release()
            self.assertTrue(finished)
            app._drain_sync_progress()
            app._finish_network_job()
            self.assertEqual(600, app.sync_status["sent"])
            self.assertEqual(600, app.sync_status["counters"]["imported"])
            self.assertEqual([], app.state.network_queue)
            restored, warning = app.store.load_or_create(app.catalog, now=NOW)
            self.assertIsNone(warning)
            self.assertEqual([], restored.network_queue)
            app.render(0)

    def test_cancelled_before_start_makes_no_network_request(self):
        with support.temporary_directory() as directory:
            client = Client()
            cancel = threading.Event()
            cancel.set()
            result = manager(directory, client, cancel=cancel).run("expeditions")
            self.assertEqual("cancelled", result["status"])
            self.assertEqual(0, client.gets)
            self.assertEqual([], client.posts)


if __name__ == "__main__":
    unittest.main()
