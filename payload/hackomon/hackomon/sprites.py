"""Deterministic 32×32 pixel-art compositor for Hackomon creatures."""

import math
import random
from collections import OrderedDict

from .constants import SPRITE_SIZE


POSE_LENGTHS = {"idle": 4, "happy": 3, "sad": 2, "sleep": 2, "walk": 4}
_FRAME_CACHE = OrderedDict()
_FRAME_CACHE_LIMIT = 96


def _hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def _mix(first, second, amount):
    return tuple(
        max(0, min(255, int(a * (1.0 - amount) + b * amount)))
        for a, b in zip(first, second)
    )


def _darken(rgb, factor):
    return tuple(max(0, min(255, int(channel * factor))) for channel in rgb)


def palette_rgb(creature):
    """Return transparent + seven derived shades for a compact 3-color descriptor."""
    primary, secondary, accent = [_hex_rgb(value) for value in creature["sprite"]["palette"]]
    outline = _darken(_mix(primary, accent, 0.12), 0.22)
    highlight = _mix(primary, (255, 255, 255), 0.55)
    shadow = _darken(primary, 0.58)
    glow = _mix(accent, (255, 255, 255), 0.34)
    return ((0, 0, 0), primary, secondary, accent, outline, highlight, shadow, glow)


def rgb565(rgb):
    red, green, blue = rgb
    return ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)


def palette_rgb565(creature):
    return tuple(rgb565(color) for color in palette_rgb(creature))


def _new_frame():
    return [[0 for _ in range(SPRITE_SIZE)] for _ in range(SPRITE_SIZE)]


def _put(frame, x, y, color):
    if 0 <= x < SPRITE_SIZE and 0 <= y < SPRITE_SIZE:
        frame[y][x] = color


def _rect(frame, x, y, width, height, color):
    for py in range(y, y + height):
        for px in range(x, x + width):
            _put(frame, px, py, color)


def _ellipse(frame, cx, cy, rx, ry, color):
    rx = max(1, int(rx))
    ry = max(1, int(ry))
    for py in range(cy - ry, cy + ry + 1):
        for px in range(cx - rx, cx + rx + 1):
            dx = (px - cx) / float(rx)
            dy = (py - cy) / float(ry)
            if dx * dx + dy * dy <= 1.0:
                _put(frame, px, py, color)


def _outlined_ellipse(frame, cx, cy, rx, ry, fill=1):
    _ellipse(frame, cx, cy, rx, ry, 4)
    _ellipse(frame, cx, cy, max(1, rx - 1), max(1, ry - 1), fill)


def _outlined_rect(frame, x, y, width, height, fill=1):
    _rect(frame, x, y, width, height, 4)
    if width > 2 and height > 2:
        _rect(frame, x + 1, y + 1, width - 2, height - 2, fill)


def _line(frame, x0, y0, x1, y1, color):
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    error = dx + dy
    while True:
        _put(frame, x0, y0, color)
        if x0 == x1 and y0 == y1:
            return
        double = 2 * error
        if double >= dy:
            error += dy
            x0 += sx
        if double <= dx:
            error += dx
            y0 += sy


def _triangle(frame, points, color):
    ys = [point[1] for point in points]
    minimum = max(0, min(ys))
    maximum = min(SPRITE_SIZE - 1, max(ys))
    for y in range(minimum, maximum + 1):
        crossings = []
        for index, first in enumerate(points):
            second = points[(index + 1) % len(points)]
            if first[1] == second[1]:
                continue
            low, high = sorted((first[1], second[1]))
            if low <= y < high:
                ratio = (y - first[1]) / float(second[1] - first[1])
                crossings.append(first[0] + ratio * (second[0] - first[0]))
        if len(crossings) >= 2:
            left, right = sorted(crossings)[:2]
            for x in range(int(math.ceil(left)), int(math.floor(right)) + 1):
                _put(frame, x, y, color)


def _outlined_triangle(frame, points, fill=1):
    _triangle(frame, points, 4)
    center_x = sum(point[0] for point in points) // 3
    center_y = sum(point[1] for point in points) // 3
    inner = []
    for x, y in points:
        inner.append((x + (1 if x < center_x else -1), y + (1 if y < center_y else -1)))
    _triangle(frame, inner, fill)


def _pose_state(pose, frame_index):
    index = frame_index % POSE_LENGTHS[pose]
    if pose == "idle":
        return {"index": index, "dx": 0, "dy": (0, -1, 0, 0)[index], "blink": index == 2}
    if pose == "happy":
        return {"index": index, "dx": 0, "dy": (0, -3, -1)[index], "blink": False}
    if pose == "sad":
        return {"index": index, "dx": 0, "dy": (0, 1)[index], "blink": False}
    if pose == "sleep":
        return {"index": index, "dx": 0, "dy": (1, 2)[index], "blink": True}
    return {
        "index": index,
        "dx": (0, 1, 0, -1)[index],
        "dy": (0, -1, 0, -1)[index],
        "blink": False,
    }


def _draw_egg(frame, cx, cy, sprite, motion):
    _outlined_ellipse(frame, cx, cy, 8, 11, 1)
    _ellipse(frame, cx - 2, cy - 3, 4, 5, 2)
    _line(frame, cx - 5, cy + 3, cx - 1, cy + 1, 3)
    _line(frame, cx - 1, cy + 1, cx + 3, cy + 4, 3)
    _put(frame, cx - 4, cy - 6, 5)
    _put(frame, cx - 3, cy - 7, 5)
    if sprite["variant"] % 2:
        _put(frame, cx + 5, cy - 2, 3)
        _put(frame, cx + 4, cy - 1, 3)
    return cx, cy - 1


def _draw_blob(frame, cx, cy, growth, variant, pose, motion):
    rx = 8 + growth
    ry = 6 + growth // 2
    _outlined_ellipse(frame, cx, cy + 2, rx, ry, 1)
    _ellipse(frame, cx - 2, cy - 1, max(3, rx - 4), max(2, ry - 3), 2)
    foot_y = cy + ry + 1
    for offset in (-rx + 2, -3, 3, rx - 2):
        _ellipse(frame, cx + offset, foot_y, 2, 2, 4)
        _ellipse(frame, cx + offset, foot_y - 1, 1, 1, 1)
    arm_raise = 4 if pose == "happy" else motion["index"] % 2
    _line(frame, cx - rx + 2, cy + 1, cx - rx - 2, cy - arm_raise, 4)
    _line(frame, cx + rx - 2, cy + 1, cx + rx + 2, cy - arm_raise, 4)
    if variant == 3 and growth >= 2:
        _outlined_triangle(frame, [(cx - 5, cy - ry), (cx - 2, cy - ry - 6), (cx, cy - ry)], 3)
        _outlined_triangle(frame, [(cx + 1, cy - ry), (cx + 5, cy - ry - 5), (cx + 7, cy - ry)], 3)
    if variant == 4:
        for side in (-1, 1):
            wave = motion["index"] % 2
            _line(frame, cx + side * 6, cy + 5, cx + side * 10, cy + 9 + wave, 4)
            _put(frame, cx + side * 10, cy + 9 + wave, 3)
    return cx, cy


def _draw_mammal(frame, cx, cy, growth, variant, pose, motion):
    _outlined_ellipse(frame, cx, cy + 5, 9 + growth // 2, 7, 1)
    _outlined_ellipse(frame, cx, cy - 2, 7 + growth // 2, 7, 2)
    if variant == 2:
        for side in (-1, 1):
            x = cx + side * 4
            _outlined_ellipse(frame, x, cy - 11, 2 + growth // 3, 7 + growth, 2)
            _rect(frame, x, cy - 13, 1, 5 + growth, 5)
    elif variant == 3:
        _outlined_ellipse(frame, cx - 5, cy - 7, 3, 3, 2)
        _outlined_ellipse(frame, cx + 5, cy - 7, 3, 3, 2)
    else:
        ear_height = 5 + growth // 2
        _outlined_triangle(frame, [(cx - 7, cy - 5), (cx - 5, cy - 5 - ear_height), (cx - 1, cy - 6)], 2)
        _outlined_triangle(frame, [(cx + 1, cy - 6), (cx + 5, cy - 5 - ear_height), (cx + 7, cy - 5)], 2)
    step = 1 if pose == "walk" and motion["index"] % 2 else 0
    _outlined_rect(frame, cx - 7 - step, cy + 9, 4, 5, 1)
    _outlined_rect(frame, cx + 3 + step, cy + 9, 4, 5, 1)
    wag = (-2, 0, 2, 0)[motion["index"] % 4]
    tail_x = cx + 11 + growth
    if variant == 4:
        _line(frame, cx + 8, cy + 5, tail_x, cy - 3 + wag, 4)
        _line(frame, tail_x, cy - 3 + wag, tail_x - 2, cy - 7 + wag, 3)
    else:
        _line(frame, cx + 8, cy + 5, tail_x, cy + wag, 4)
        _outlined_ellipse(frame, tail_x, cy - 1 + wag, 3 + variant % 2, 3, 2)
    if growth >= 3:
        _rect(frame, cx - 3, cy + 4, 6, 2, 3)
    return cx, cy - 3


def _draw_avian(frame, cx, cy, growth, variant, pose, motion):
    _outlined_ellipse(frame, cx, cy + 4, 8, 9 + growth // 2, 1)
    _outlined_ellipse(frame, cx + 1, cy - 5, 6 + growth // 2, 6, 2)
    lift = 6 if pose == "happy" else (3 if motion["index"] % 2 else 0)
    _outlined_triangle(frame, [(cx - 3, cy), (cx - 12, cy - lift), (cx - 8, cy + 8)], 2)
    _outlined_triangle(frame, [(cx + 4, cy), (cx + 12, cy - lift), (cx + 8, cy + 8)], 2)
    _outlined_triangle(frame, [(cx + 6, cy - 7), (cx + 12, cy - 4), (cx + 6, cy - 2)], 3)
    _line(frame, cx - 3, cy + 13, cx - 5, cy + 16, 4)
    _line(frame, cx + 3, cy + 13, cx + 5, cy + 16, 4)
    if variant == 0:
        _outlined_triangle(frame, [(cx - 2, cy - 10), (cx, cy - 16), (cx + 2, cy - 10)], 3)
    elif variant == 3:
        _ellipse(frame, cx - 3, cy - 6, 3, 3, 4)
        _ellipse(frame, cx + 3, cy - 6, 3, 3, 4)
    elif growth >= 2:
        for offset in (-3, 0, 3):
            _line(frame, cx + offset, cy - 10, cx + offset + variant - 2, cy - 14, 3)
    return cx + 1, cy - 6


def _draw_reptile(frame, cx, cy, growth, variant, pose, motion):
    tail_wave = (-2, 0, 2, 0)[motion["index"] % 4]
    if variant == 3:
        for segment in range(5):
            _outlined_ellipse(frame, cx - 10 + segment * 5, cy + (segment % 2) * 2, 4, 4, 1 if segment % 2 else 2)
        _outlined_ellipse(frame, cx + 10, cy - 1, 5, 5, 2)
        face = (cx + 11, cy - 2)
    else:
        _outlined_ellipse(frame, cx - 1, cy + 4, 11, 6, 1)
        _outlined_ellipse(frame, cx + 8, cy - 1, 6, 6, 2)
        _line(frame, cx - 10, cy + 4, cx - 15, cy + 7 + tail_wave, 4)
        _line(frame, cx - 15, cy + 7 + tail_wave, cx - 13, cy + 9 + tail_wave, 3)
        face = (cx + 9, cy - 2)
        if variant == 2:
            _outlined_ellipse(frame, cx - 3, cy + 1, 8, 7, 2)
            for offset in (-3, 2):
                _line(frame, cx + offset, cy - 4, cx + offset, cy + 6, 3)
        else:
            step = 2 if pose == "walk" and motion["index"] % 2 else 0
            _line(frame, cx - 6, cy + 8, cx - 8 - step, cy + 13, 4)
            _line(frame, cx + 4, cy + 8, cx + 7 + step, cy + 13, 4)
    if variant == 0 and growth >= 2:
        _outlined_triangle(frame, [(cx - 4, cy - 1), (cx - 8, cy - 10), (cx + 1, cy - 4)], 2)
        _outlined_triangle(frame, [(cx + 3, cy - 4), (cx + 7, cy - 11), (cx + 9, cy - 3)], 2)
    elif variant == 1:
        for offset in (-6, -1, 4):
            _put(frame, cx + offset, cy + 1, 3)
            _put(frame, cx + offset + 1, cy + 2, 3)
    return face


def _draw_aquatic(frame, cx, cy, growth, variant, pose, motion):
    tail_wave = (-3, 0, 3, 0)[motion["index"] % 4]
    if variant == 3:
        _outlined_ellipse(frame, cx, cy + 3, 9, 7, 1)
        _outlined_ellipse(frame, cx - 5, cy - 4, 4, 4, 2)
        _outlined_ellipse(frame, cx + 5, cy - 4, 4, 4, 2)
        _outlined_triangle(frame, [(cx - 6, cy + 6), (cx - 14, cy + 13), (cx - 2, cy + 10)], 2)
        _outlined_triangle(frame, [(cx + 6, cy + 6), (cx + 14, cy + 13), (cx + 2, cy + 10)], 2)
        return cx, cy - 2
    if variant == 4:
        _outlined_ellipse(frame, cx, cy, 7, 6, 1)
        _outlined_triangle(frame, [(cx - 3, cy), (cx - 15, cy - 7 + tail_wave // 2), (cx - 12, cy + 8)], 2)
        _outlined_triangle(frame, [(cx + 3, cy), (cx + 15, cy - 7 - tail_wave // 2), (cx + 12, cy + 8)], 2)
        _line(frame, cx, cy + 5, cx, cy + 14, 4)
        _put(frame, cx, cy + 14, 3)
        return cx, cy - 1
    _outlined_ellipse(frame, cx + 2, cy, 11, 7, 1)
    _outlined_triangle(frame, [(cx - 8, cy), (cx - 15, cy - 7 + tail_wave), (cx - 15, cy + 7 + tail_wave)], 2)
    _outlined_triangle(frame, [(cx, cy + 4), (cx - 4, cy + 11), (cx + 5, cy + 6)], 3)
    if variant == 0:
        for side in (-1, 1):
            base = cx + 7 * side
            _line(frame, base, cy - 4, base + side * 3, cy - 10, 3)
            _line(frame, base, cy, base + side * 4, cy - 5, 3)
            _line(frame, base, cy + 3, base + side * 4, cy + 7, 3)
    elif variant == 2:
        _outlined_triangle(frame, [(cx, cy - 6), (cx + 4, cy - 13), (cx + 7, cy - 5)], 2)
        _line(frame, cx + 7, cy + 2, cx + 11, cy + 3, 5)
    return cx + 6, cy - 1


def _draw_insect(frame, cx, cy, growth, variant, pose, motion):
    wing_open = 5 if pose == "happy" else (2 + motion["index"] % 2 * 3)
    if variant == 1:
        _outlined_triangle(frame, [(cx - 2, cy - 2), (cx - 14, cy - 9 - wing_open), (cx - 10, cy + 10)], 2)
        _outlined_triangle(frame, [(cx + 2, cy - 2), (cx + 14, cy - 9 - wing_open), (cx + 10, cy + 10)], 2)
        _put(frame, cx - 10, cy - 7, 3)
        _put(frame, cx + 10, cy - 7, 3)
    else:
        _outlined_ellipse(frame, cx - 7, cy - wing_open // 2, 6, 8, 2)
        _outlined_ellipse(frame, cx + 7, cy - wing_open // 2, 6, 8, 2)
    _outlined_ellipse(frame, cx, cy + 2, 6, 10, 1)
    _outlined_ellipse(frame, cx, cy - 7, 6, 5, 2)
    _line(frame, cx - 3, cy - 10, cx - 7 - variant % 2, cy - 15, 4)
    _line(frame, cx + 3, cy - 10, cx + 7 + variant % 2, cy - 15, 4)
    if variant == 0:
        for y in (cy, cy + 4, cy + 8):
            _line(frame, cx - 5, y, cx + 5, y, 3)
    elif variant == 2:
        _line(frame, cx, cy - 1, cx, cy + 11, 3)
        _outlined_triangle(frame, [(cx - 5, cy - 1), (cx, cy - 6), (cx, cy + 1)], 3)
        _outlined_triangle(frame, [(cx + 5, cy - 1), (cx, cy - 6), (cx, cy + 1)], 3)
    elif variant == 3:
        _line(frame, cx - 4, cy - 2, cx - 12, cy + 2 - wing_open, 4)
        _line(frame, cx + 4, cy - 2, cx + 12, cy + 2 - wing_open, 4)
    elif variant == 4:
        _ellipse(frame, cx, cy + 7, 4, 4, 7)
    return cx, cy - 7


def _draw_spectral(frame, cx, cy, growth, variant, pose, motion):
    _outlined_ellipse(frame, cx, cy - 2, 9 + growth // 2, 9, 1)
    wave = motion["index"] % 2
    _outlined_triangle(frame, [(cx - 9, cy + 1), (cx - 7, cy + 13 + wave), (cx - 2, cy + 6)], 1)
    _outlined_triangle(frame, [(cx - 3, cy + 5), (cx, cy + 14 - wave), (cx + 3, cy + 5)], 1)
    _outlined_triangle(frame, [(cx + 2, cy + 6), (cx + 8, cy + 13 + wave), (cx + 9, cy + 1)], 1)
    if variant == 0:
        _outlined_triangle(frame, [(cx - 5, cy - 9), (cx, cy - 16), (cx + 4, cy - 9)], 3)
    elif variant == 1:
        for offset in (-12, 12):
            _line(frame, cx + (offset // 2), cy, cx + offset, cy + (-3 if offset < 0 else 3), 3)
    elif variant == 4:
        _outlined_rect(frame, cx - 4, cy + 5, 8, 9, 2)
        _ellipse(frame, cx, cy + 8, 2, 3, 7)
    return cx, cy - 3


def _draw_botanical(frame, cx, cy, growth, variant, pose, motion):
    sway = (-2, 0, 2, 0)[motion["index"] % 4]
    if variant == 0:
        _outlined_rect(frame, cx - 6, cy + 5, 12, 8, 1)
        _outlined_ellipse(frame, cx + sway, cy - 4, 11 + growth // 2, 6, 2)
        _rect(frame, cx - 7 + sway, cy - 5, 3, 2, 3)
        _rect(frame, cx + 3 + sway, cy - 2, 3, 2, 3)
        return cx, cy + 7
    if variant == 1:
        _outlined_rect(frame, cx - 6, cy + 8, 12, 6, 2)
        _outlined_ellipse(frame, cx + sway, cy, 7, 12, 1)
        _line(frame, cx - 5 + sway, cy - 3, cx - 10 + sway, cy - 7, 4)
        _line(frame, cx + 5 + sway, cy + 1, cx + 10 + sway, cy - 3, 4)
        for offset in (-3, 3):
            _put(frame, cx + offset + sway, cy - 4, 3)
        return cx + sway, cy - 2
    if variant == 2:
        _line(frame, cx, cy + 12, cx + sway, cy - 3, 4)
        for angle in range(0, 360, 45):
            radians = math.radians(angle)
            px = cx + sway + int(round(math.cos(radians) * 8))
            py = cy - 4 + int(round(math.sin(radians) * 8))
            _outlined_ellipse(frame, px, py, 4, 4, 2)
        _outlined_ellipse(frame, cx + sway, cy - 4, 5, 5, 3)
        _outlined_rect(frame, cx - 5, cy + 9, 10, 5, 1)
        return cx + sway, cy - 4
    if variant == 3:
        _outlined_rect(frame, cx - 6, cy + 9, 12, 5, 1)
        _line(frame, cx, cy + 9, cx + sway, cy - 11, 4)
        for y, side in ((cy + 5, -1), (cy + 1, 1), (cy - 4, -1)):
            _outlined_ellipse(frame, cx + sway + side * 5, y, 5, 3, 2)
        return cx + sway, cy - 1
    _outlined_rect(frame, cx - 7, cy + 8, 14, 6, 1)
    for x in range(cx - 8, cx + 9, 4):
        height = 5 + (x + growth) % 6
        _outlined_ellipse(frame, x + sway, cy + 4 - height, 4, height, 2)
    return cx + sway, cy


def _draw_robotic(frame, cx, cy, growth, variant, pose, motion):
    bob = -1 if motion["index"] % 2 else 0
    if variant == 0:
        _outlined_rect(frame, cx - 9, cy - 5 + bob, 18, 11, 1)
        _outlined_rect(frame, cx - 14, cy - 2 + bob, 5, 5, 2)
        _outlined_rect(frame, cx + 9, cy - 2 + bob, 5, 5, 2)
        _line(frame, cx, cy - 5 + bob, cx + motion["index"] - 2, cy - 13 + bob, 4)
        _put(frame, cx + motion["index"] - 2, cy - 14 + bob, 7)
    elif variant == 1:
        _outlined_ellipse(frame, cx, cy, 11, 11, 1)
        for angle in range(0, 360, 45):
            radians = math.radians(angle)
            x = cx + int(round(math.cos(radians) * 13))
            y = cy + int(round(math.sin(radians) * 13))
            _rect(frame, x - 1, y - 1, 3, 3, 4)
        _outlined_ellipse(frame, cx, cy, 5, 5, 2)
    elif variant == 2:
        _outlined_rect(frame, cx - 10, cy - 8, 20, 18, 1)
        _outlined_rect(frame, cx - 6, cy - 5, 12, 7, 2)
        _line(frame, cx - 4, cy - 8, cx - 8, cy - 14, 4)
        _line(frame, cx + 4, cy - 8, cx + 8, cy - 14, 4)
        for radius in range(2, 6, 2):
            _put(frame, cx + radius + motion["index"], cy + 6, 3)
    elif variant == 3:
        _outlined_rect(frame, cx - 8, cy - 9, 16, 20, 1)
        _outlined_triangle(frame, [(cx - 8, cy - 2), (cx - 14, cy + 4), (cx - 8, cy + 8)], 2)
        _outlined_triangle(frame, [(cx + 8, cy - 2), (cx + 14, cy + 4), (cx + 8, cy + 8)], 2)
        _rect(frame, cx - 2, cy + 3, 4, 5, 3)
    else:
        _outlined_ellipse(frame, cx, cy, 10, 10, 1)
        _outlined_triangle(frame, [(cx - 8, cy - 4), (cx - 14, cy - 9), (cx - 10, cy + 3)], 3)
        _outlined_triangle(frame, [(cx + 8, cy - 4), (cx + 14, cy - 9), (cx + 10, cy + 3)], 3)
        _line(frame, cx - 7, cy + 7, cx - 10, cy + 13, 4)
        _line(frame, cx + 7, cy + 7, cx + 10, cy + 13, 4)
    return cx, cy - 2 + bob


def _draw_cosmic(frame, cx, cy, growth, variant, pose, motion):
    orbit_phase = motion["index"] % 4
    if variant == 1:
        _outlined_ellipse(frame, cx + 4, cy, 8, 8, 1)
        _outlined_triangle(frame, [(cx - 2, cy - 4), (cx - 15, cy - 9 + orbit_phase), (cx - 5, cy + 4)], 2)
        _line(frame, cx - 5, cy, cx - 14, cy + 7 - orbit_phase, 3)
        return cx + 4, cy - 1
    if variant == 3:
        _outlined_ellipse(frame, cx, cy, 11, 12, 2)
        _ellipse(frame, cx + 5, cy - 2, 9, 10, 4)
        _put(frame, cx - 5, cy - 6, 5)
        _put(frame, cx - 7, cy + 3, 3)
        return cx - 4, cy
    _outlined_ellipse(frame, cx, cy, 9 + growth // 2, 9 + growth // 2, 1)
    if variant == 0:
        for angle in range(0, 360, 72):
            radians = math.radians(angle + orbit_phase * 8)
            x = cx + int(round(math.cos(radians) * 14))
            y = cy + int(round(math.sin(radians) * 14))
            _line(frame, cx + int(round(math.cos(radians) * 9)), cy + int(round(math.sin(radians) * 9)), x, y, 3)
    elif variant == 2:
        _ellipse(frame, cx, cy, 5, 5, 4)
        for offset in (-12, 12):
            _put(frame, cx + offset, cy + (orbit_phase - 2), 7)
    else:
        for offset in (-7, 0, 7):
            _outlined_ellipse(frame, cx + offset, cy + (offset // 4), 5, 5, 2 if offset else 3)
    return cx, cy - 1


DRAWERS = {
    "blob": _draw_blob,
    "mammal": _draw_mammal,
    "avian": _draw_avian,
    "reptile": _draw_reptile,
    "aquatic": _draw_aquatic,
    "insect": _draw_insect,
    "spectral": _draw_spectral,
    "botanical": _draw_botanical,
    "robotic": _draw_robotic,
    "cosmic": _draw_cosmic,
}


def _shade(frame, seed):
    """Add directional highlights and shadow dithering before facial details."""
    for y in range(SPRITE_SIZE):
        for x in range(SPRITE_SIZE):
            color = frame[y][x]
            if color not in (1, 2):
                continue
            above_empty = y == 0 or frame[y - 1][x] in (0, 4)
            below_empty = y == SPRITE_SIZE - 1 or frame[y + 1][x] in (0, 4)
            left_empty = x == 0 or frame[y][x - 1] in (0, 4)
            right_empty = x == SPRITE_SIZE - 1 or frame[y][x + 1] in (0, 4)
            if color == 1 and (above_empty or left_empty) and (x + y + seed) % 3:
                frame[y][x] = 5
            elif color == 1 and (below_empty or right_empty):
                frame[y][x] = 6
            elif color == 1 and y > SPRITE_SIZE // 2 and (x * 3 + y + seed) % 9 == 0:
                frame[y][x] = 6


def _body_points(frame):
    return [
        (x, y)
        for y, row in enumerate(frame)
        for x, color in enumerate(row)
        if color in (1, 2, 5, 6)
    ]


def _draw_motif(frame, creature, cx, cy, pose, motion):
    sprite = creature["sprite"]
    motif = sprite["motif"]
    growth = int(sprite["growth"])
    rng = random.Random(sprite["seed"])
    points = _body_points(frame)
    if points:
        rng.shuffle(points)
        for x, y in points[: 2 + growth]:
            if (x + y + growth) % 2:
                _put(frame, x, y, 3)
    if motif in ("bolt", "circuit", "signal", "byte", "pixel", "glitch", "noise"):
        _line(frame, cx - 4, cy - 3, cx, cy, 3)
        _line(frame, cx, cy, cx - 2, cy + 4, 3)
        _put(frame, cx + 5, cy - 4, 7)
    elif motif in ("bands", "wave", "echo"):
        for y in range(cy - 3, cy + 6, 4):
            _line(frame, cx - 5, y, cx + 5, y + motion["index"] % 2, 3)
    elif motif in ("crystal", "prism") and growth >= 2:
        _outlined_triangle(frame, [(cx - 5, cy - 7), (cx - 2, cy - 14), (cx + 1, cy - 7)], 3)
        _outlined_triangle(frame, [(cx + 1, cy - 7), (cx + 5, cy - 12), (cx + 7, cy - 6)], 7)
    elif motif in ("moon", "orbit"):
        _line(frame, cx - 6, cy + 4, cx + 6, cy + 4, 3)
        _put(frame, cx - 7, cy + 2, 7)
        _put(frame, cx + 7, cy + 2, 7)
    elif motif in ("leaf", "gill", "drop") and growth >= 2:
        _outlined_ellipse(frame, cx - 8, cy + 3, 4, 2, 2)
        _outlined_ellipse(frame, cx + 8, cy + 1, 4, 2, 2)
    elif motif in ("rune", "lantern"):
        _rect(frame, cx - 1, cy - 5, 3, 1, 3)
        _rect(frame, cx, cy - 7, 1, 5, 3)
        _put(frame, cx - 2, cy - 6, 7)
        _put(frame, cx + 2, cy - 6, 7)
    if growth == 4:
        pulse = motion["index"] % 2
        aura = ((2, 7), (29, 8), (3, 23), (28, 24), (8, 2), (24, 3))
        for index, (x, y) in enumerate(aura):
            if (index + pulse) % 2 == 0 or pose == "happy":
                _put(frame, x, y, 7)
                _put(frame, x + (1 if x < 16 else -1), y, 3)


def _draw_face(frame, pose, blink, cx, cy, growth):
    eye_gap = 3 if growth >= 2 else 2
    eye_y = cy - 1
    if blink or pose == "sleep":
        _line(frame, cx - eye_gap - 1, eye_y, cx - eye_gap + 1, eye_y, 4)
        _line(frame, cx + eye_gap - 1, eye_y, cx + eye_gap + 1, eye_y, 4)
    elif pose == "happy":
        _line(frame, cx - eye_gap - 1, eye_y, cx - eye_gap, eye_y - 1, 4)
        _line(frame, cx - eye_gap, eye_y - 1, cx - eye_gap + 1, eye_y, 4)
        _line(frame, cx + eye_gap - 1, eye_y, cx + eye_gap, eye_y - 1, 4)
        _line(frame, cx + eye_gap, eye_y - 1, cx + eye_gap + 1, eye_y, 4)
    else:
        _rect(frame, cx - eye_gap - 1, eye_y - 1, 2, 3, 4)
        _rect(frame, cx + eye_gap, eye_y - 1, 2, 3, 4)
        _put(frame, cx - eye_gap - 1, eye_y - 1, 5)
        _put(frame, cx + eye_gap, eye_y - 1, 5)
    mouth_y = cy + 3
    if pose == "happy":
        _put(frame, cx - 2, mouth_y, 4)
        _line(frame, cx - 1, mouth_y + 1, cx + 1, mouth_y + 1, 4)
        _put(frame, cx + 2, mouth_y, 4)
        _put(frame, cx, mouth_y + 2, 3)
    elif pose == "sad":
        _put(frame, cx - 2, mouth_y + 1, 4)
        _line(frame, cx - 1, mouth_y, cx + 1, mouth_y, 4)
        _put(frame, cx + 2, mouth_y + 1, 4)
    elif pose != "sleep":
        _line(frame, cx - 1, mouth_y, cx + 1, mouth_y, 4)


def _draw_sleep_symbol(frame, cx, cy, phase):
    offset = phase % 2
    _line(frame, cx + 7, cy - 8 - offset, cx + 10, cy - 8 - offset, 7)
    _line(frame, cx + 10, cy - 8 - offset, cx + 7, cy - 5 - offset, 7)
    _line(frame, cx + 7, cy - 5 - offset, cx + 10, cy - 5 - offset, 7)
    _line(frame, cx + 11, cy - 13 + offset, cx + 14, cy - 13 + offset, 3)
    _line(frame, cx + 14, cy - 13 + offset, cx + 11, cy - 10 + offset, 3)
    _line(frame, cx + 11, cy - 10 + offset, cx + 14, cy - 10 + offset, 3)


def _uncached_sprite_frame(creature, pose, frame_index):
    sprite = creature["sprite"]
    growth = int(sprite["growth"])
    variant = int(sprite["variant"])
    motion = _pose_state(pose, frame_index)
    cx = SPRITE_SIZE // 2 + motion["dx"]
    cy = 17 + motion["dy"]
    frame = _new_frame()
    if growth == 0:
        face_x, face_y = _draw_egg(frame, cx, cy, sprite, motion)
    else:
        face_x, face_y = DRAWERS[sprite["shape"]](frame, cx, cy, growth, variant, pose, motion)
    _shade(frame, int(sprite["seed"]) & 0xFF)
    _draw_motif(frame, creature, face_x, face_y, pose, motion)
    _draw_face(frame, pose, motion["blink"], face_x, face_y, growth)
    if pose == "sleep":
        _draw_sleep_symbol(frame, face_x, face_y, motion["index"])
    return frame


def sprite_frame(creature, pose="idle", frame_index=0):
    if pose not in POSE_LENGTHS:
        raise ValueError("unknown pose: %s" % pose)
    key = (creature["id"], pose, frame_index % POSE_LENGTHS[pose])
    if key in _FRAME_CACHE:
        frame = _FRAME_CACHE.pop(key)
        _FRAME_CACHE[key] = frame
        return frame
    frame = _uncached_sprite_frame(creature, pose, frame_index)
    _FRAME_CACHE[key] = frame
    if len(_FRAME_CACHE) > _FRAME_CACHE_LIMIT:
        _FRAME_CACHE.popitem(last=False)
    return frame


def iter_color_runs(frame):
    """Yield horizontal non-transparent runs as (x, y, width, palette_index)."""
    for y, row in enumerate(frame):
        x = 0
        while x < len(row):
            color = row[x]
            if color == 0:
                x += 1
                continue
            start = x
            while x < len(row) and row[x] == color:
                x += 1
            yield start, y, x - start, color


def draw_sprite(display, creature, x, y, scale=4, pose="idle", frame_index=0):
    frame = sprite_frame(creature, pose=pose, frame_index=frame_index)
    palette = palette_rgb565(creature)
    for run_x, run_y, width, color_index in iter_color_runs(frame):
        display.fill_rect(
            x + run_x * scale,
            y + run_y * scale,
            width * scale,
            scale,
            palette[color_index],
        )
