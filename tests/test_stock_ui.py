"""Screen handover must keep native backends alive and return the original UI."""

import contextlib
from pathlib import Path
import signal
import unittest
from unittest.mock import MagicMock, patch

from tests import support
from hackomon import stock_ui


class StockUITests(unittest.TestCase):
    @contextlib.contextmanager
    def machine(self):
        with support.temporary_directory() as directory:
            root = Path(directory)
            targets = {101: stock_ui.STOCK_EXE, 202: "/usr/sbin/pineapd", 303: "/usr/sbin/gpsd"}
            calls = []

            def state(pid, status="R", born=123):
                (root / str(pid)).mkdir(exist_ok=True)
                fields = [status] + ["0"] * 18 + [str(born)]
                (root / str(pid) / "stat").write_text("%s (name with ) spaces) %s" % (pid, " ".join(fields)))

            for pid in targets:
                state(pid)

            def send(pid, signum):
                calls.append((pid, signum))
                state(pid, "T" if signum == 23 else "R")

            with patch.object(signal, "SIGSTOP", 23, create=True), \
                    patch.object(signal, "SIGCONT", 25, create=True), \
                    patch.object(signal, "SIGHUP", 1, create=True), \
                    patch("hackomon.stock_ui.os.readlink", side_effect=lambda path: targets.get(int(Path(path).parent.name), "other")), \
                    patch("hackomon.stock_ui.os.kill", side_effect=send), \
                    patch("hackomon.stock_ui.signal.signal"):
                yield root, targets, calls, state

    def test_suspend_and_return_only_visual_process_not_pineap_or_gpsd(self):
        with self.machine() as (root, _targets, calls, _state):
            with stock_ui.StockUI(root) as session:
                self.assertEqual("T", session.read(101)[1])
                self.assertIsNone(session.read(202))
                self.assertIsNone(session.read(303))
            self.assertEqual([(101, 23), (101, 25)], calls)
            self.assertEqual("R", session.read(101)[1])

    def test_restore_after_exception_and_close_is_idempotent(self):
        with self.machine() as (root, _targets, calls, _state):
            session = stock_ui.StockUI(root)
            with self.assertRaisesRegex(ValueError, "app failed"):
                with session:
                    raise ValueError("app failed")
            session.close()
            self.assertEqual([(101, 23), (101, 25)], calls)

    def test_do_not_take_over_an_interface_already_paused_by_someone_else(self):
        with self.machine() as (root, _targets, calls, state):
            state(101, "T")
            with self.assertRaisesRegex(RuntimeError, "ja esta suspensa"):
                with stock_ui.StockUI(root):
                    self.fail("must not run")
            self.assertEqual([], calls)

    def test_reused_pid_must_not_receive_continue(self):
        with self.machine() as (root, _targets, calls, state):
            with stock_ui.StockUI(root):
                state(101, "T", born=456)
            self.assertEqual([(101, 23)], calls)

    def test_changed_executable_must_not_receive_continue(self):
        with self.machine() as (root, targets, calls, _state):
            with stock_ui.StockUI(root):
                targets[101] = "/usr/sbin/gpsd"
            self.assertEqual([(101, 23)], calls)

    def test_partial_failure_resumes_the_first_interface(self):
        with self.machine() as (root, targets, calls, state):
            targets[404] = stock_ui.STOCK_EXE
            state(404)
            def send(pid, signum):
                calls.append((pid, signum))
                if pid == 404:
                    raise PermissionError()
                state(pid, "T" if signum == 23 else "R")
            with patch("hackomon.stock_ui.os.kill", side_effect=send):
                with self.assertRaises(PermissionError):
                    with stock_ui.StockUI(root):
                        self.fail("must not run")
            self.assertIn((101, 25), calls)

    def test_without_stock_ui_nothing_is_signalled(self):
        with self.machine() as (root, targets, calls, _state):
            targets.pop(101)
            with stock_ui.StockUI(root):
                pass
            self.assertEqual([], calls)

    def test_app_killed_by_signal_still_resumes_ui_from_guard(self):
        with self.machine() as (root, _targets, calls, _state):
            child = MagicMock()
            child.wait.return_value = child.poll.return_value = -9
            with patch("hackomon.stock_ui.subprocess.Popen", return_value=child) as spawn:
                code = stock_ui.run(["python3", "app.py"], root)
            self.assertEqual(137, code)
            spawn.assert_called_once_with(["python3", "app.py"], start_new_session=True)
            self.assertEqual([(101, 23), (101, 25)], calls)

    def test_app_start_failure_still_resumes_ui(self):
        with self.machine() as (root, _targets, calls, _state):
            with patch("hackomon.stock_ui.subprocess.Popen", side_effect=OSError("cannot start")):
                with self.assertRaises(OSError):
                    stock_ui.run(["python3", "app.py"], root)
            self.assertEqual([(101, 23), (101, 25)], calls)

    def test_termination_requests_app_cleanup_and_restores_original_handlers(self):
        with self.machine() as (root, _targets, calls, _state):
            handlers, restored = {}, []
            def install(signum, handler):
                if callable(handler):
                    handlers[signum] = handler
                    return "original-%s" % signum
                restored.append((signum, handler))
            child = MagicMock()
            def wait():
                handlers[signal.SIGTERM](signal.SIGTERM, None)
                return 130
            child.wait.side_effect = wait
            child.poll.return_value = 130
            with patch("hackomon.stock_ui.signal.signal", side_effect=install), \
                    patch("hackomon.stock_ui.subprocess.Popen", return_value=child):
                code = stock_ui.run(["python3", "app.py"], root)
            self.assertEqual(143, code)
            child.send_signal.assert_called_once_with(signal.SIGINT)
            self.assertEqual(3, len(restored))
            self.assertEqual([(101, 23), (101, 25)], calls)

    def test_empty_command_does_not_borrow_screen(self):
        with patch("hackomon.stock_ui.StockUI") as screen:
            self.assertEqual(2, stock_ui.main([]))
            screen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
