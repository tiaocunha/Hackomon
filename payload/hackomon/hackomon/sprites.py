"""Tiny deterministic pixel-art compositor with five animation poses."""

import math
import random

from .constants import SPRITE_SIZE


POSE_LENGTHS = {"idle": 4, "happy": 3, "sad": 2, "sleep": 2, "walk": 4}


def _hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def _darken(rgb, factor=0.35):
    return tuple(max(0, min(255, int(channel * factor))) for channel in rgb)


def palette_rgb(creature):
    base = [_hex_rgb(value) for value in creature["sprite"]["palette"]]
    return ((0, 0, 0), base[0], base[1], base[2], _darken(base[0]), (248, 250, 255))


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
    rx = max(1, rx)
    ry = max(1, ry)
    for py in range(cy - ry, cy + ry + 1):
        for px in range(cx - rx, cx + rx + 1):
            dx = (px - cx) / float(rx)
            dy = (py - cy) / float(ry)
            if dx * dx + dy * dy <= 1.0:
                _put(frame, px, py, color)


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
    for y in range(max(0, min(ys)), min(SPRITE_SIZE - 1, max(ys)) + 1):
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


def _pose_offsets(pose, frame_index):
    length = POSE_LENGTHS[pose]
    index = frame_index % length
    if pose == "idle":
        return 0, (0, -1, 0, 0)[index], index == 2
    if pose == "happy":
        return 0, (0, -2, -1)[index], False
    if pose == "sad":
        return 0, (0, 1)[index], False
    if pose == "sleep":
        return 0, (0, 1)[index], True
    return (0, 1, 2, 1)[index], (0, -1, 0, -1)[index], False


def _draw_egg(frame, cx, cy, stage):
    _ellipse(frame, cx, cy, 6, 8, 4)
    _ellipse(frame, cx, cy, 5, 7, 1)
    _ellipse(frame, cx - 1, cy - 2, 3, 3, 2)


def _draw_blob(frame, cx, cy, growth):
    radius_x = 6 + growth
    radius_y = 5 + growth // 2
    _ellipse(frame, cx, cy, radius_x, radius_y, 4)
    _ellipse(frame, cx, cy - 1, radius_x - 1, radius_y - 1, 1)
    for x in range(cx - radius_x + 1, cx + radius_x):
        if (x + growth) % 4 != 0:
            _put(frame, x, cy + radius_y, 4)


def _draw_mammal(frame, cx, cy, growth, variant):
    _ellipse(frame, cx, cy + 2, 6 + growth, 5 + growth // 2, 4)
    _ellipse(frame, cx, cy + 1, 5 + growth, 4 + growth // 2, 1)
    ear_height = 3 + growth // 2
    _triangle(frame, [(cx - 5, cy - 2), (cx - 3, cy - 2 - ear_height), (cx - 1, cy - 2)], 4)
    _triangle(frame, [(cx + 1, cy - 2), (cx + 3, cy - 2 - ear_height), (cx + 5, cy - 2)], 4)
    _put(frame, cx - 3, cy - 3, 2)
    _put(frame, cx + 3, cy - 3, 2)
    tail_x = cx + 7 + growth
    _line(frame, cx + 5, cy + 3, tail_x, cy - (variant % 3), 4)
    _put(frame, tail_x, cy - (variant % 3), 3)


def _draw_avian(frame, cx, cy, growth, variant):
    _ellipse(frame, cx, cy + 1, 5 + growth, 6 + growth // 2, 4)
    _ellipse(frame, cx, cy, 4 + growth, 5 + growth // 2, 1)
    wing_side = -1 if variant % 2 else 1
    _ellipse(frame, cx + wing_side * 4, cy + 2, 3 + growth // 2, 4, 2)
    _triangle(frame, [(cx + 4, cy - 1), (cx + 8, cy + 1), (cx + 4, cy + 2)], 3)
    if growth >= 2:
        _line(frame, cx - 2, cy - 6, cx - 3, cy - 9, 3)
        _line(frame, cx, cy - 6, cx, cy - 10, 3)


def _draw_reptile(frame, cx, cy, growth, variant):
    _ellipse(frame, cx - 1, cy + 2, 7 + growth, 4 + growth // 2, 4)
    _ellipse(frame, cx - 1, cy + 1, 6 + growth, 3 + growth // 2, 1)
    _ellipse(frame, cx + 5, cy - 1, 4, 4, 4)
    _ellipse(frame, cx + 5, cy - 1, 3, 3, 2)
    _line(frame, cx - 7, cy + 2, cx - 10 - growth, cy + 5 - variant % 2, 4)
    for spike in range(max(0, growth - 1)):
        x = cx - 4 + spike * 3
        _triangle(frame, [(x, cy - 3), (x + 1, cy - 6), (x + 2, cy - 3)], 3)


def _draw_aquatic(frame, cx, cy, growth, variant):
    _ellipse(frame, cx, cy, 7 + growth, 4 + growth // 2, 4)
    _ellipse(frame, cx, cy - 1, 6 + growth, 3 + growth // 2, 1)
    _triangle(frame, [(cx - 6, cy), (cx - 11, cy - 5), (cx - 11, cy + 5)], 2)
    _triangle(frame, [(cx, cy + 2), (cx - 3, cy + 7), (cx + 3, cy + 3)], 3)
    if variant in (0, 3):
        _line(frame, cx + 3, cy - 3, cx + 5, cy - 7, 3)


def _draw_insect(frame, cx, cy, growth, variant):
    wing = 3 + growth // 2
    _ellipse(frame, cx - 4, cy - 1, wing, 5 + growth // 2, 2)
    _ellipse(frame, cx + 4, cy - 1, wing, 5 + growth // 2, 2)
    _ellipse(frame, cx, cy + 1, 4 + growth // 2, 6 + growth // 2, 4)
    _ellipse(frame, cx, cy, 3 + growth // 2, 5 + growth // 2, 1)
    _line(frame, cx - 2, cy - 5, cx - 4 - variant % 2, cy - 9, 3)
    _line(frame, cx + 2, cy - 5, cx + 4 + variant % 2, cy - 9, 3)
    for band_y in range(cy - 1, cy + 5, 3):
        _line(frame, cx - 3, band_y, cx + 3, band_y, 3)


def _draw_spectral(frame, cx, cy, growth, variant):
    _ellipse(frame, cx, cy - 1, 6 + growth, 6 + growth // 2, 4)
    _ellipse(frame, cx, cy - 2, 5 + growth, 5 + growth // 2, 1)
    bottom = cy + 7 + growth // 2
    _triangle(frame, [(cx - 6 - growth, cy + 1), (cx - 4, bottom), (cx, cy + 4)], 1)
    _triangle(frame, [(cx, cy + 4), (cx + 3, bottom - variant % 2), (cx + 6 + growth, cy + 1)], 1)
    if growth >= 3:
        _put(frame, cx - 9, cy - 5, 3)
        _put(frame, cx + 9, cy - 3, 3)


def _draw_botanical(frame, cx, cy, growth, variant):
    _rect(frame, cx - 5, cy + 3, 10, 7, 4)
    _rect(frame, cx - 4, cy + 3, 8, 6, 1)
    _line(frame, cx, cy + 3, cx, cy - 5 - growth, 2)
    canopy_y = cy - 5 - growth
    _ellipse(frame, cx, canopy_y, 5 + growth, 4 + growth // 2, 4)
    _ellipse(frame, cx, canopy_y - 1, 4 + growth, 3 + growth // 2, 2)
    _ellipse(frame, cx - 4, cy - 1, 3, 2, 2)
    if variant in (0, 2):
        _put(frame, cx, canopy_y, 3)
        _put(frame, cx - 2, canopy_y + 1, 3)
        _put(frame, cx + 2, canopy_y + 1, 3)


def _draw_robotic(frame, cx, cy, growth, variant):
    width = 10 + growth * 2
    height = 9 + growth
    _rect(frame, cx - width // 2, cy - height // 2, width, height, 4)
    _rect(frame, cx - width // 2 + 1, cy - height // 2 + 1, width - 2, height - 2, 1)
    _line(frame, cx, cy - height // 2, cx + variant - 2, cy - height // 2 - 4, 3)
    _put(frame, cx + variant - 2, cy - height // 2 - 5, 3)
    _rect(frame, cx - 4, cy + height // 2, 2, 3, 4)
    _rect(frame, cx + 2, cy + height // 2, 2, 3, 4)
    if growth >= 2:
        _rect(frame, cx - width // 2 - 2, cy - 1, 2, 4, 3)
        _rect(frame, cx + width // 2, cy - 1, 2, 4, 3)


def _draw_cosmic(frame, cx, cy, growth, variant):
    _ellipse(frame, cx, cy, 6 + growth, 6 + growth // 2, 4)
    _ellipse(frame, cx, cy - 1, 5 + growth, 5 + growth // 2, 1)
    radius = 8 + growth
    for x in range(cx - radius, cx + radius + 1):
        offset = int(round(math.sin((x - cx) / float(radius) * math.pi) * 3))
        if (x + variant) % 2 == 0:
            _put(frame, x, cy + offset, 3)
    if growth >= 2:
        _put(frame, cx - 8, cy - 7, 3)
        _put(frame, cx + 7, cy - 8, 2)


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


def _draw_motif(frame, creature, cx, cy):
    sprite = creature["sprite"]
    rng = random.Random(sprite["seed"])
    motif = sprite["motif"]
    growth = sprite["growth"]
    count = 1 + growth // 2
    if motif in ("bolt", "circuit", "signal"):
        _line(frame, cx - 2, cy - 3, cx + 1, cy, 3)
        _line(frame, cx + 1, cy, cx - 1, cy + 3, 3)
    elif motif in ("moon", "orbit", "wave", "echo"):
        for index in range(3 + growth):
            _put(frame, cx - 3 + index, cy + (index % 2), 3)
    elif motif in ("horn", "blade", "crystal", "shell", "shield", "gear"):
        _triangle(frame, [(cx - 2, cy - 4), (cx, cy - 7 - growth), (cx + 2, cy - 4)], 3)
    else:
        for _ in range(count):
            _put(frame, cx + rng.randint(-4, 4), cy + rng.randint(-3, 3), 3)

    if growth == 4:
        for x, y in ((2, 5), (21, 6), (3, 18), (20, 19)):
            _put(frame, x, y, 3)
            if (x + y + sprite["variant"]) % 2:
                _put(frame, x + (1 if x < 12 else -1), y, 2)


def _draw_face(frame, pose, blink, cx, cy, growth):
    eye_gap = 2 + min(2, growth // 2)
    eye_y = cy - 1
    if blink or pose == "sleep":
        _line(frame, cx - eye_gap - 1, eye_y, cx - eye_gap + 1, eye_y, 4)
        _line(frame, cx + eye_gap - 1, eye_y, cx + eye_gap + 1, eye_y, 4)
    elif pose == "happy":
        _put(frame, cx - eye_gap, eye_y, 5)
        _put(frame, cx + eye_gap, eye_y, 5)
        _put(frame, cx - eye_gap - 1, eye_y - 1, 4)
        _put(frame, cx + eye_gap + 1, eye_y - 1, 4)
    else:
        _put(frame, cx - eye_gap, eye_y, 4)
        _put(frame, cx + eye_gap, eye_y, 4)
        if growth >= 2:
            _put(frame, cx - eye_gap, eye_y - 1, 5)
            _put(frame, cx + eye_gap, eye_y - 1, 5)

    mouth_y = cy + 2
    if pose == "happy":
        _put(frame, cx - 1, mouth_y, 4)
        _put(frame, cx, mouth_y + 1, 4)
        _put(frame, cx + 1, mouth_y, 4)
    elif pose == "sad":
        _put(frame, cx - 1, mouth_y + 1, 4)
        _put(frame, cx, mouth_y, 4)
        _put(frame, cx + 1, mouth_y + 1, 4)
    elif pose != "sleep":
        _line(frame, cx - 1, mouth_y, cx + 1, mouth_y, 4)


def sprite_frame(creature, pose="idle", frame_index=0):
    if pose not in POSE_LENGTHS:
        raise ValueError("unknown pose: %s" % pose)
    sprite = creature["sprite"]
    growth = int(sprite["growth"])
    variant = int(sprite["variant"])
    dx, dy, blink = _pose_offsets(pose, frame_index)
    cx = 12 + dx
    cy = 13 + dy
    frame = _new_frame()

    if growth == 0:
        _draw_egg(frame, cx, cy, growth)
    else:
        drawer = DRAWERS[sprite["shape"]]
        if sprite["shape"] == "blob":
            drawer(frame, cx, cy, growth)
        else:
            drawer(frame, cx, cy, growth, variant)

    _draw_motif(frame, creature, cx, cy)
    _draw_face(frame, pose, blink, cx, cy, growth)
    if pose == "sleep":
        _put(frame, min(22, cx + 7), max(1, cy - 7), 3)
        _put(frame, min(22, cx + 8), max(1, cy - 8), 3)
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


def draw_sprite(display, creature, x, y, scale=5, pose="idle", frame_index=0):
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

