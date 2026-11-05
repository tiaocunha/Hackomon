"""Native screen handover keeps PineAP/GPSd alive and releases input ownership."""
import contextlib
from pathlib import Path
import shutil
import signal
import subprocess
import unittest
from unittest.mock import MagicMock, patch
from tests import support
from hackomon import stock_ui
from hackomon.app import run_on_pager


class StockUITests(unittest.TestCase):
    @contextlib.contextmanager
    def machine(self):
        with support.temporary_directory() as directory:
            root=Path(directory)
            targets={101:stock_ui.STOCK_EXE,202:"/usr/sbin/pineapd",303:"/usr/sbin/gpsd"}
            calls=[]
            def state(pid,status="R",born=123):
                (root/str(pid)).mkdir(exist_ok=True)
                fields=[status]+["0"]*18+[str(born)]
                (root/str(pid)/"stat").write_text("%s (name with ) spaces) %s"%(pid," ".join(fields)))
            for pid in targets:
                state(pid)
            def rpc(args,**kwargs):
                calls.append(args)
                if args[0]=="ubus":
                    for pid,target in list(targets.items()):
                        if target==stock_ui.STOCK_EXE and (root/str(pid)).exists():
                            shutil.rmtree(root/str(pid))
                elif args==["/etc/init.d/pineapplepager","start"]:
                    targets[404]=stock_ui.STOCK_EXE
                    state(404,born=456)
                else:
                    self.fail("unexpected native command")
                return subprocess.CompletedProcess(args,0)
            with patch.object(signal,"SIGHUP",1,create=True), \
                    patch.object(signal,"SIGKILL",9,create=True), \
                    patch("hackomon.stock_ui.os.readlink",side_effect=lambda path:targets.get(int(Path(path).parent.name),"other")), \
                    patch("hackomon.stock_ui.os.kill") as kill, \
                    patch("hackomon.stock_ui.signal.signal"), \
                    patch("hackomon.stock_ui.subprocess.run",side_effect=rpc):
                yield root,targets,calls,state,kill,rpc

    def test_release_visual_instance_without_running_backend_stopping_hook(self):
        with self.machine() as (root,targets,calls,state,kill,rpc):
            with stock_ui.StockUI(root) as screen:
                self.assertEqual([],screen.targets())
                self.assertTrue((root/"202/stat").exists())
                self.assertTrue((root/"303/stat").exists())
            self.assertEqual(["ubus","call","service","delete",'{"name":"pineapplepager"}'],calls[0])
            self.assertEqual(["/etc/init.d/pineapplepager","start"],calls[1])
            self.assertEqual(404,screen.targets()[0][0])
            kill.assert_not_called()

    def test_app_exception_and_repeated_close_restore_once(self):
        with self.machine() as (root,targets,calls,state,kill,rpc):
            screen=stock_ui.StockUI(root)
            with self.assertRaises(ValueError):
                with screen:
                    raise ValueError("app failed")
            screen.close()
            self.assertEqual(2,len(calls))

    def test_already_suspended_ui_is_not_adopted(self):
        with self.machine() as (root,targets,calls,state,kill,rpc):
            state(101,"T")
            with self.assertRaises(RuntimeError):
                with stock_ui.StockUI(root):
                    self.fail("must not start")
            self.assertEqual([],calls)

    def test_existing_replacement_ui_is_not_restarted(self):
        with self.machine() as (root,targets,calls,state,kill,rpc):
            with stock_ui.StockUI(root):
                state(101,born=456)
            self.assertEqual(1,len(calls))
            kill.assert_not_called()

    def test_backend_using_reused_pid_is_left_alone(self):
        with self.machine() as (root,targets,calls,state,kill,rpc):
            with stock_ui.StockUI(root):
                targets[101]="/usr/sbin/gpsd"
                state(101,born=456)
            self.assertTrue((root/"101/stat").exists())
            self.assertEqual(2,len(calls))
            kill.assert_not_called()

    def test_rpc_error_after_ui_removal_restores_interface(self):
        with self.machine() as (root,targets,calls,state,kill,rpc):
            def failure(args,**kwargs):
                result=rpc(args,**kwargs)
                if args[0]=="ubus":
                    raise subprocess.TimeoutExpired(args,3)
                return result
            with patch("hackomon.stock_ui.subprocess.run",side_effect=failure):
                with self.assertRaises(subprocess.TimeoutExpired):
                    with stock_ui.StockUI(root):
                        pass
            self.assertTrue((root/"404/stat").exists())

    def test_no_visual_process_does_not_create_an_extra_interface(self):
        with self.machine() as (root,targets,calls,state,kill,rpc):
            targets.pop(101)
            with stock_ui.StockUI(root):
                pass
            self.assertEqual([],calls)

    def test_app_crash_still_recreates_ui(self):
        with self.machine() as (root,targets,calls,state,kill,rpc):
            child=MagicMock()
            child.poll.return_value=-9
            with patch("hackomon.stock_ui.subprocess.Popen",return_value=child):
                self.assertEqual(137,stock_ui.run(["python3","app.py"],root))
            self.assertEqual(2,len(calls))

    def test_app_start_failure_recreates_ui(self):
        with self.machine() as (root,targets,calls,state,kill,rpc):
            with patch("hackomon.stock_ui.subprocess.Popen",side_effect=OSError("failed")):
                with self.assertRaises(OSError):
                    stock_ui.run(["python3","app.py"],root)
            self.assertEqual(2,len(calls))

    def test_unresponsive_app_has_bounded_shutdown_and_ui_is_restored(self):
        with self.machine() as (root,targets,calls,state,kill,rpc):
            handlers={}
            def install(sig,handler):
                if callable(handler):
                    handlers[sig]=handler
                return signal.SIG_DFL
            child=MagicMock()
            ticks=iter([0,0,11,14,14])
            polls=0
            def poll():
                nonlocal polls
                polls+=1
                if polls==1:
                    handlers[signal.SIGTERM](signal.SIGTERM,None)
                return None if polls<4 else -9
            child.poll.side_effect=poll
            with patch("hackomon.stock_ui.signal.signal",side_effect=install), \
                    patch("hackomon.stock_ui.time.monotonic",side_effect=lambda:next(ticks)), \
                    patch("hackomon.stock_ui.time.sleep"), \
                    patch("hackomon.stock_ui.os.killpg",create=True) as group, \
                    patch("hackomon.stock_ui.subprocess.Popen",return_value=child):
                self.assertEqual(143,stock_ui.run(["python3","app.py"],root))
            child.send_signal.assert_called_once_with(signal.SIGINT)
            self.assertEqual([(child.pid,signal.SIGTERM),(child.pid,signal.SIGKILL)],
                             [call.args for call in group.call_args_list])
            self.assertEqual(2,len(calls))

    def test_empty_command_does_not_borrow_screen(self):
        with patch("hackomon.stock_ui.StockUI") as screen:
            self.assertEqual(2,stock_ui.main([]))
            screen.assert_not_called()

    def test_python_interrupt_is_reestablished_after_native_display_initializes(self):
        events=[]
        def install(sig,handler):
            events.append("signal")
            return signal.SIG_DFL
        with patch("hackomon.app.CreatureCatalog.load_default"), patch("hackomon.app.StateStore"), \
                patch("hackomon.app.PagerDisplay") as display, patch("hackomon.app.HackomonApp") as app, \
                patch("hackomon.app.signal.signal",side_effect=install):
            display.return_value.__enter__.side_effect=lambda:events.append("display")
            app.return_value.run.side_effect=lambda:events.append("app")
            run_on_pager()
        self.assertEqual(["display","signal","app","signal"],events)


if __name__=="__main__":
    unittest.main()
