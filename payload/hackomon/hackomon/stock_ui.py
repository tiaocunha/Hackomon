"""Lend the framebuffer without stopping the stock UI service or radio backend."""

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
        try:
            candidates = self.targets()
            # An already suspended UI may belong to another payload. Do not adopt it.
            if any(state in ("T", "t") for _pid, _born, state in candidates):
                raise RuntimeError("A interface Hak5 ja esta suspensa por outro processo")
            for pid, born, _state in candidates:
                current = self.read(pid)
                if current is None or current[0] != born:
                    raise RuntimeError("A interface Hak5 mudou durante a abertura")
                self.owned.append((pid, born))
                os.kill(pid, signal.SIGSTOP)
                deadline = time.monotonic() + 1
                while True:
                    current = self.read(pid)
                    if current and current[0] == born and current[1] in ("T", "t"):
                        break
                    if current is None or current[0] != born or time.monotonic() >= deadline:
                        raise RuntimeError("Nao foi possivel suspender apenas a tela Hak5")
                    time.sleep(0.01)
            return self
        except BaseException:
            self.close()
            raise

    def close(self):
        failures = False
        for pid, born in reversed(self.owned):
            current = self.read(pid)
            if current and current[0] == born and current[1] in ("T", "t"):
                try:
                    os.kill(pid, signal.SIGCONT)
                except ProcessLookupError:
                    pass
                except OSError:
                    failures = True
        self.owned.clear()
        if failures:
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
    """A separate guard survives app crashes and resumes the original UI PID."""
    child = None
    requested = []
    signals = [signal.SIGINT, signal.SIGTERM, signal.SIGHUP]
    handlers = {}

    def interrupted(signum, _frame):
        if requested:
            return
        requested.append(signum)
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
            try:
                code = child.wait()
            finally:
                if child.poll() is None:
                    child.send_signal(signal.SIGINT)
                    child.wait()
        return 128 + requested[0] if requested else (128 - code if code < 0 else code)
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
        return run(command)
    except (OSError, RuntimeError):
        print("Hackomon: falha ao emprestar/devolver a tela Hak5; servicos nao alterados", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
