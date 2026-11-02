"""Minimal ctypes adapter for the external MIT-licensed libpagerctl.so."""

import ctypes
import os
import time
import unicodedata
from pathlib import Path

from .constants import BTN_A, BTN_B, BTN_DOWN, BTN_LEFT, BTN_POWER, BTN_RIGHT, BTN_UP


class PagerDependencyError(RuntimeError):
    pass


class _PagerInput(ctypes.Structure):
    _fields_ = [
        ("current", ctypes.c_uint8),
        ("pressed", ctypes.c_uint8),
        ("released", ctypes.c_uint8),
    ]


def _candidate_libraries(explicit=None):
    values = [
        explicit,
        os.environ.get("TAMAFI_PAGERCTL_LIB"),
        str(Path(__file__).resolve().parents[1] / "lib" / "libpagerctl.so"),
        "/root/payloads/user/utilities/PAGERCTL/libpagerctl.so",
        "/mmc/root/payloads/user/utilities/PAGERCTL/libpagerctl.so",
    ]
    seen = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            yield value


def find_library(explicit=None):
    for candidate in _candidate_libraries(explicit):
        if Path(candidate).is_file():
            return candidate
    raise PagerDependencyError("libpagerctl.so não encontrada")


class PagerDisplay:
    BTN_UP = BTN_UP
    BTN_DOWN = BTN_DOWN
    BTN_LEFT = BTN_LEFT
    BTN_RIGHT = BTN_RIGHT
    BTN_A = BTN_A
    BTN_B = BTN_B
    BTN_POWER = BTN_POWER

    def __init__(self, library_path=None):
        self.library_path = find_library(library_path)
        self._lib = ctypes.CDLL(self.library_path)
        self._initialized = False
        self._bind()

    def _bind(self):
        lib = self._lib
        lib.pager_init.argtypes = []
        lib.pager_init.restype = ctypes.c_int
        lib.pager_cleanup.argtypes = []
        lib.pager_cleanup.restype = None
        lib.pager_set_rotation.argtypes = [ctypes.c_int]
        lib.pager_set_rotation.restype = None
        lib.pager_clear.argtypes = [ctypes.c_uint16]
        lib.pager_clear.restype = None
        lib.pager_flip.argtypes = []
        lib.pager_flip.restype = None
        lib.pager_delay.argtypes = [ctypes.c_uint32]
        lib.pager_delay.restype = None
        lib.pager_fill_rect.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint16,
        ]
        lib.pager_fill_rect.restype = None
        lib.pager_draw_text.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint16,
            ctypes.c_int,
        ]
        lib.pager_draw_text.restype = ctypes.c_int
        lib.pager_draw_text_centered.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint16,
            ctypes.c_int,
        ]
        lib.pager_draw_text_centered.restype = None
        lib.pager_text_width.argtypes = [ctypes.c_char_p, ctypes.c_int]
        lib.pager_text_width.restype = ctypes.c_int
        lib.pager_poll_input.argtypes = [ctypes.POINTER(_PagerInput)]
        lib.pager_poll_input.restype = None
        if hasattr(lib, "pager_vibrate"):
            lib.pager_vibrate.argtypes = [ctypes.c_int]
            lib.pager_vibrate.restype = None

    @staticmethod
    def _ascii(text):
        normalized = unicodedata.normalize("NFKD", str(text))
        return normalized.encode("ascii", "ignore")

    def __enter__(self):
        result = self._lib.pager_init()
        if result != 0:
            raise RuntimeError("pager_init falhou com código %d" % result)
        self._initialized = True
        self.set_rotation(270)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._initialized:
            self._lib.pager_cleanup()
            self._initialized = False
        return False

    def set_rotation(self, degrees):
        self._lib.pager_set_rotation(int(degrees))

    def clear(self, color=0):
        self._lib.pager_clear(int(color))

    def flip(self):
        self._lib.pager_flip()

    def delay(self, milliseconds):
        self._lib.pager_delay(int(milliseconds))

    def fill_rect(self, x, y, width, height, color):
        if width > 0 and height > 0:
            self._lib.pager_fill_rect(int(x), int(y), int(width), int(height), int(color))

    def draw_text(self, x, y, text, color, size=1):
        return self._lib.pager_draw_text(int(x), int(y), self._ascii(text), int(color), int(size))

    def draw_text_centered(self, y, text, color, size=1):
        self._lib.pager_draw_text_centered(int(y), self._ascii(text), int(color), int(size))

    def text_width(self, text, size=1):
        return self._lib.pager_text_width(self._ascii(text), int(size))

    def poll_input(self):
        state = _PagerInput()
        self._lib.pager_poll_input(ctypes.byref(state))
        return state.current, state.pressed, state.released

    def vibrate(self, milliseconds=80):
        if hasattr(self._lib, "pager_vibrate"):
            self._lib.pager_vibrate(int(milliseconds))


class MemoryDisplay:
    """Small test double used by the desktop smoke test."""

    BTN_UP = BTN_UP
    BTN_DOWN = BTN_DOWN
    BTN_LEFT = BTN_LEFT
    BTN_RIGHT = BTN_RIGHT
    BTN_A = BTN_A
    BTN_B = BTN_B
    BTN_POWER = BTN_POWER

    def __init__(self):
        self.operations = []
        self.inputs = []

    def clear(self, color=0):
        self.operations.append(("clear", color))

    def flip(self):
        self.operations.append(("flip",))

    def delay(self, milliseconds):
        time.sleep(min(milliseconds / 1000.0, 0.001))

    def fill_rect(self, x, y, width, height, color):
        self.operations.append(("rect", x, y, width, height, color))

    def draw_text(self, x, y, text, color, size=1):
        self.operations.append(("text", x, y, str(text), color, size))
        return len(str(text)) * 6 * size

    def draw_text_centered(self, y, text, color, size=1):
        self.operations.append(("center", y, str(text), color, size))

    def text_width(self, text, size=1):
        return len(str(text)) * 6 * size

    def poll_input(self):
        return self.inputs.pop(0) if self.inputs else (0, 0, 0)

    def vibrate(self, milliseconds=80):
        self.operations.append(("vibrate", milliseconds))

