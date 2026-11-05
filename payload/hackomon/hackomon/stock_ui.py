"""Release only the procd visual instance, bypassing the backend-stopping hook."""

import contextlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


STOCK_EXE = "/pineapple/pineapple"


class StockUI:
    def __init__(self, proc_root="/proc"):
        self.proc_root = Path(proc_root)
        self.owned = []

    def read(self, pid):
        try:
            folder = self.proc_root / str(pid)
            if os.readlink(str(folder / "exe")) != STOCK_EXE:
                return None
            # comm can contain spaces or parentheses; starttime is field 22.
            fields = (folder / "stat").read_text().rsplit(")", 1)[1].split()
            return (int(fields[19]), fields[0])
        except (OSError, ValueError, IndexError):
            return None

    def targets(self):
        candidates = []
        for folder in self.proc_root.iterdir():
            if folder.name.isdecimal():
                value = self.read(int(folder.name))
                if value:
                    candidates.append((int(folder.name), value[0], value[1]))
        return candidates

    def __enter__(self):
        self.owned = [(pid, born) for pid, born, state in self.targets()]
        self.restore_needed = False
        try:
            if any(state in ("T", "t") for _pid, _born, state in self.targets()):
                raise RuntimeError("A interface Hak5 ja esta suspensa por outro processo")
            if not self.owned:
                return self
            # Bypass pineapplepager's shell stop hook, which also stops PineAP.
            with blocked([signal.SIGINT, signal.SIGTERM, signal.SIGHUP]):
                self.restore_needed = True
                result = subprocess.run(["ubus", "call", "service", "delete",
                                         '{"name":"pineapplepager"}'],
                                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, timeout=3)
                if result.returncode:
                    raise RuntimeError("Nao foi possivel liberar apenas a interface visual")
                deadline = time.monotonic() + 10
                while any(self.read(pid) and self.read(pid)[0] == born for pid, born in self.owned):
                    if time.monotonic() >= deadline:
                        raise RuntimeError("A interface visual nao encerrou no prazo")
                    time.sleep(0.05)
            return self
        except BaseException:
            self.close()
            raise

    def close(self):
        if not getattr(self, "restore_needed", False):
            return
        self.restore_needed = False
        # Another controller may already have recreated the UI. Leave it alone.
        if self.targets():
            return
        result = subprocess.run(["/etc/init.d/pineapplepager", "start"],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=8)
        if result.returncode:
            raise RuntimeError("Nao foi possivel devolver a tela Hak5")

    def __exit__(self, *_args):
        self.close()


@contextlib.contextmanager
def blocked(signals):
    # Linux MIPS has different signal numbers; always use its Python constants.
    mask = getattr(signal, "pthread_sigmask", None)
    previous = mask(signal.SIG_BLOCK, signals) if mask else None
    try:
        yield
    finally:
        if mask:
            mask(signal.SIG_SETMASK, previous)


def run(command, proc_root="/proc"):
    """A separate guard survives app crashes and recreates only the native UI."""
    child = None
    requested = []
    signals = [signal.SIGINT, signal.SIGTERM, signal.SIGHUP]
    handlers = {}

    def interrupted(signum, _frame):
        if requested:
            return
        requested.append((signum, time.monotonic()))
        if child is None:
            raise SystemExit(128 + signum)
        try:
            # The app handles KeyboardInterrupt and closes its workers/save/display.
            child.send_signal(signal.SIGINT)
        except ProcessLookupError:
            pass

    try:
        for signum in signals:
            handlers[signum] = signal.signal(signum, interrupted)
        with StockUI(proc_root):
            with blocked(signals):
                child = subprocess.Popen(command, start_new_session=True)
            terminated = killed = False
            try:
                while True:
                    code = child.poll()
                    if code is not None:
                        break
                    if requested:
                        elapsed = time.monotonic() - requested[0][1]
                        if elapsed >= 10 and not terminated:
                            os.killpg(child.pid, signal.SIGTERM)
                            terminated = True
                        if elapsed >= 13 and not killed:
                            os.killpg(child.pid, signal.SIGKILL)
                            killed = True
                    time.sleep(0.1)
            finally:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
        return 128 + requested[0][0] if requested else (128 - code if code < 0 else code)
    finally:
        for signum, handler in handlers.items():
            signal.signal(signum, handler)


def main(argv=None):
    command = list(sys.argv[1:] if argv is None else argv)
    if command[:1] == ["--"]:
        command.pop(0)
    if not command:
        return 2
    try:
        # Do not belong to the visual service's process group when deleting it.
        if os.getpgrp() != os.getpid():
            os.setsid()
        return run(command)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        print("Hackomon: falha ao liberar/devolver a tela Hak5; backends preservados", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
