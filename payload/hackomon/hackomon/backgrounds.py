"""Personalized low-cost pixel backgrounds for every creature and stage."""

import math
import random
from collections import OrderedDict

from .sprites import palette_rgb, rgb565


BACKGROUND_WIDTH = 43
BACKGROUND_HEIGHT = 35
_CACHE = OrderedDict()
_CACHE_LIMIT = 96


def _mix(first, second, amount):
    return tuple(
        max(0, min(255, int(a * (1.0 - amount) + b * amount)))
        for a, b in zip(first, second)
    )


def _darken(color, factor):
    return tuple(max(0, min(255, int(channel * factor))) for channel in color)


def background_palette_rgb(creature):
    source = palette_rgb(creature)
    primary, secondary, accent = source[1], source[2], source[3]
    return (
        _darken(_mix(primary, (5, 9, 22), 0.72), 0.72),
        _darken(_mix(secondary, (10, 18, 38), 0.68), 0.82),
        _darken(_mix(primary, accent, 0.18), 0.35),
        _darken(_mix(secondary, accent, 0.22), 0.50),
        _darken(accent, 0.62),
        _mix(accent, (255, 255, 255), 0.28),
        _darken(primary, 0.20),
        _mix(secondary, (255, 255, 255), 0.48),
    )


def background_palette_rgb565(creature):
    return tuple(rgb565(color) for color in background_palette_rgb(creature))


def _frame(width, height, color=0):
    return [[color for _ in range(width)] for _ in range(height)]


def _put(frame, x, y, color):
    if 0 <= y < len(frame) and 0 <= x < len(frame[0]):
        frame[y][x] = color


def _rect(frame, x, y, width, height, color):
    for py in range(y, y + height):
        for px in range(x, x + width):
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


def _ellipse(frame, cx, cy, rx, ry, color):
    rx = max(1, int(rx))
    ry = max(1, int(ry))
    for py in range(cy - ry, cy + ry + 1):
        for px in range(cx - rx, cx + rx + 1):
            dx = (px - cx) / float(rx)
            dy = (py - cy) / float(ry)
            if dx * dx + dy * dy <= 1.0:
                _put(frame, px, py, color)


def _gradient(frame, horizon):
    width = len(frame[0])
    height = len(frame)
    _rect(frame, 0, 0, width, max(1, horizon // 2), 0)
    _rect(frame, 0, horizon // 2, width, max(1, horizon - horizon // 2), 1)
    _rect(frame, 0, horizon, width, height - horizon, 2)
    _rect(frame, 0, min(height - 1, horizon + 3), width, max(1, height - horizon - 3), 6)


def _cavern(frame, rng, stage, variant, horizon):
    width, height = len(frame[0]), len(frame)
    _rect(frame, 0, 0, width, height, 0)
    stalactites = 4 + stage // 2
    for index in range(stalactites):
        x = index * max(1, width - 1) // max(1, stalactites - 1)
        depth = 3 + rng.randrange(0, max(2, 3 + stage))
        for y in range(depth):
            _put(frame, x + y // 2, y, 6 if y < depth - 1 else 4)
    _rect(frame, 0, horizon, width, height - horizon, 2)
    _ellipse(frame, width // 2, height - 3, width // 4 + variant, 2 + stage // 2, 4)
    _ellipse(frame, width // 2, height - 3, width // 5, 1 + stage // 2, 5)
    for index in range(1 + stage):
        x = 3 + (index * 9 + variant * 4) % max(4, width - 6)
        base = horizon + 4 + index % 3
        _line(frame, x, base, x + (index % 2), base - 4 - stage // 2, 4)
        _put(frame, x, base - 4 - stage // 2, 5)


def _forest(frame, rng, stage, variant, horizon):
    width, height = len(frame[0]), len(frame)
    _gradient(frame, horizon)
    tree_count = 2 + stage // 2
    for index in range(tree_count):
        x = 3 + (index * (width - 6) // max(1, tree_count - 1))
        trunk_height = 9 + (index + variant) % 5
        _rect(frame, x, horizon - trunk_height, 2 + index % 2, trunk_height + 5, 6)
        _ellipse(frame, x + 1, horizon - trunk_height, 5 + stage // 2, 4, 3)
        _ellipse(frame, x - 2 + variant % 3, horizon - trunk_height - 2, 4, 3, 4)
    for x in range(0, width, 3):
        _put(frame, x, horizon + (x + variant) % 3, 3)
    if stage >= 3:
        _ellipse(frame, width - 6, 5, 3, 3, 5)


def _sky(frame, rng, stage, variant, horizon):
    width, height = len(frame[0]), len(frame)
    _gradient(frame, horizon)
    cloud_count = 2 + stage // 2
    for index in range(cloud_count):
        x = (4 + index * 13 + variant * 5) % max(8, width - 5)
        y = 4 + (index * 5 + variant) % max(5, horizon - 8)
        _ellipse(frame, x, y, 4, 2, 7)
        _ellipse(frame, x + 4, y + 1, 3, 2, 7)
    peak = width // 2 + (variant - 2) * 2
    for y in range(horizon - 7, horizon + 1):
        spread = y - (horizon - 7)
        _line(frame, peak - spread, y, peak + spread, y, 6 if y < horizon - 2 else 3)
    _rect(frame, 0, horizon + 1, width, height - horizon - 1, 6)


def _desert(frame, rng, stage, variant, horizon):
    width, height = len(frame[0]), len(frame)
    _gradient(frame, horizon)
    _ellipse(frame, 6 + variant * 5, 6, 3 + stage // 2, 3 + stage // 2, 5)
    _rect(frame, 0, horizon - 2, width, height - horizon + 2, 2)
    for x in range(width):
        y = horizon + int(round(math.sin((x + variant * 4) / 6.0) * 2))
        _put(frame, x, y, 3)
        if x % 5 == 0:
            _put(frame, x, min(height - 1, y + 4), 3)
    if variant in (0, 2, 4):
        ruin_x = width - 10 if variant != 4 else 3
        _rect(frame, ruin_x, horizon - 6 - stage, 3, 7 + stage, 6)
        _rect(frame, ruin_x + 5, horizon - 4 - stage, 3, 5 + stage, 6)
        _line(frame, ruin_x, horizon - 6 - stage, ruin_x + 7, horizon - 4 - stage, 4)
    else:
        cactus_x = width - 7
        _rect(frame, cactus_x, horizon - 7, 2, 9, 4)
        _line(frame, cactus_x, horizon - 4, cactus_x - 3, horizon - 6, 4)


def _ocean(frame, rng, stage, variant, horizon):
    width, height = len(frame[0]), len(frame)
    _rect(frame, 0, 0, width, height // 3, 0)
    _rect(frame, 0, height // 3, width, height // 3, 1)
    _rect(frame, 0, 2 * height // 3, width, height - 2 * height // 3, 2)
    for y in range(5, height - 3, 6):
        offset = (y + variant) % 4
        for x in range(offset, width, 8):
            _line(frame, x, y, min(width - 1, x + 4), y, 3)
    for index in range(2 + stage):
        x = 3 + (index * 11 + variant * 3) % max(4, width - 6)
        y = height - 4 - (index * 5) % max(5, height - 8)
        _put(frame, x, y, 7)
        if index % 2:
            _put(frame, x + 1, y - 1, 5)
    for x in (3 + variant, width - 5 - variant):
        _line(frame, x, height - 1, x - 2, height - 8 - stage, 4)
        _line(frame, x, height - 5, x + 3, height - 9, 4)


def _meadow(frame, rng, stage, variant, horizon):
    width, height = len(frame[0]), len(frame)
    _gradient(frame, horizon)
    _ellipse(frame, width - 6 - variant, 6, 3, 3, 5)
    _rect(frame, 0, horizon, width, height - horizon, 3)
    for x in range(0, width, 4):
        height_offset = 2 + (x + variant) % (4 + stage)
        _line(frame, x, height - 1, x + (1 if x % 4 else -1), height - 1 - height_offset, 4)
    for index in range(1 + stage):
        x = 4 + (index * 9 + variant * 5) % max(5, width - 8)
        y = horizon + 3 + index % 4
        _put(frame, x, y, 5)
        _put(frame, x - 1, y + 1, 7)
        _put(frame, x + 1, y + 1, 7)


def _haunt(frame, rng, stage, variant, horizon):
    width, height = len(frame[0]), len(frame)
    _rect(frame, 0, 0, width, height, 0)
    _ellipse(frame, width - 7 - variant, 6, 4 + stage // 2, 4 + stage // 2, 7)
    _ellipse(frame, width - 5 - variant, 5, 4, 4, 0)
    _rect(frame, 0, horizon, width, height - horizon, 6)
    grave_count = 2 + stage // 2
    for index in range(grave_count):
        x = 3 + (index * 11 + variant * 3) % max(6, width - 7)
        y = horizon - 3 - index % 2
        _rect(frame, x, y, 4, 7, 2)
        _ellipse(frame, x + 2, y, 2, 2, 2)
        _line(frame, x + 2, y + 1, x + 2, y + 4, 4)
    for x in range(0, width, 5):
        _put(frame, x + (variant % 2), horizon - 7 + (x % 3), 4)
    if stage >= 3:
        _line(frame, 0, horizon - 5, width - 1, horizon - 3, 1)


def _garden(frame, rng, stage, variant, horizon):
    width, height = len(frame[0]), len(frame)
    _gradient(frame, horizon)
    _rect(frame, 0, horizon, width, height - horizon, 2)
    plant_count = 3 + stage
    for index in range(plant_count):
        x = 2 + (index * max(3, width // plant_count) + variant * 2) % max(4, width - 4)
        stem = 3 + (index + variant) % 6
        _line(frame, x, height - 2, x, height - 2 - stem, 4)
        _ellipse(frame, x - 2, height - 3 - stem, 2, 1, 3)
        _ellipse(frame, x + 2, height - 5 - stem, 2, 1, 3)
        if index % 2 == 0:
            _put(frame, x, height - 3 - stem, 5)
    if variant == 0:
        _ellipse(frame, width - 7, horizon - 5, 5, 3, 4)
        for x in range(width - 11, width - 2, 3):
            _put(frame, x, horizon - 6, 7)


def _lab(frame, rng, stage, variant, horizon):
    width, height = len(frame[0]), len(frame)
    _rect(frame, 0, 0, width, height, 0)
    for y in range(0, height, 7):
        _line(frame, 0, y, width - 1, y, 6)
    for x in range(4, width, 10):
        for y in range(1, height, 14):
            _line(frame, x, y, x, min(height - 1, y + 4), 6)
    panel_count = 2 + stage // 2
    for index in range(panel_count):
        x = 2 + (index * 13 + variant * 4) % max(5, width - 9)
        y = 3 + (index * 7 + variant) % max(5, horizon - 8)
        _rect(frame, x, y, 7, 5, 2)
        _rect(frame, x + 1, y + 1, 5, 3, 1)
        _put(frame, x + 2, y + 2, 5)
        _put(frame, x + 4, y + 2, 4)
    _rect(frame, 0, horizon, width, height - horizon, 2)
    _line(frame, 0, horizon + 3, width - 1, horizon + 3, 4)
    if stage >= 3:
        _line(frame, width // 2, 0, width // 2 + variant - 2, horizon, 5)


def _space(frame, rng, stage, variant, horizon):
    width, height = len(frame[0]), len(frame)
    _rect(frame, 0, 0, width, height, 0)
    star_count = 6 + stage * 2
    for index in range(star_count):
        x = rng.randrange(width)
        y = rng.randrange(height)
        _put(frame, x, y, 7 if index % 3 == 0 else 5)
    planet_x = 6 + variant * max(3, width // 7)
    planet_y = 7 + (variant * 4) % max(5, height - 14)
    radius = 3 + stage // 2
    _ellipse(frame, planet_x, planet_y, radius, radius, 3)
    _ellipse(frame, planet_x - 1, planet_y - 1, max(1, radius - 1), max(1, radius - 1), 4)
    if variant in (1, 2, 4):
        _line(frame, planet_x - radius - 3, planet_y + 1, planet_x + radius + 3, planet_y - 1, 5)
    if stage == 4:
        _line(frame, width - 10, 2, width - 2, 10, 4)
        _put(frame, width - 2, 10, 5)


FAMILY_DRAWERS = {
    "slime": _cavern,
    "mammal": _forest,
    "avian": _sky,
    "reptile": _desert,
    "aquatic": _ocean,
    "insect": _meadow,
    "spectral": _haunt,
    "botanical": _garden,
    "robotic": _lab,
    "cosmic": _space,
}


def _motif_mark(frame, motif, seed, stage, frame_index):
    width, height = len(frame[0]), len(frame)
    x = 5 + (seed % max(1, width - 10))
    y = 4 + ((seed >> 5) % max(1, height // 3))
    if motif in ("bolt", "circuit", "signal", "byte", "glitch", "pixel"):
        _line(frame, x, y, x + 3, y + 3, 5)
        _line(frame, x + 3, y + 3, x + 1, y + 7, 5)
    elif motif in ("star", "sun", "spark", "prism", "aurora"):
        _put(frame, x, y, 5)
        _put(frame, x - 1, y, 7)
        _put(frame, x + 1, y, 7)
        _put(frame, x, y - 1, 7)
        _put(frame, x, y + 1, 7)
    elif motif in ("moon", "orbit", "wave", "echo", "trail"):
        _line(frame, x - 3, y + 2, x + 3, y, 4)
        _put(frame, x + 4, y - (frame_index % 2), 5)
    elif motif in ("rune", "lantern", "shield", "gear", "shell"):
        _rect(frame, x - 2, y - 2, 5, 5, 4)
        _put(frame, x, y, 7)
    elif stage >= 2:
        _ellipse(frame, x, y, 2, 2, 4)
        _put(frame, x, y, 5)


def _stage_layer(frame, creature, rng, frame_index):
    stage = int(creature["stage"])
    width, height = len(frame[0]), len(frame)
    if stage == 0:
        nest_y = height - 4
        _ellipse(frame, width // 2, nest_y, max(4, width // 7), 2, 3)
        _line(frame, width // 2 - 5, nest_y - 1, width // 2 + 5, nest_y + 1, 4)
        return
    for index in range(stage * 2):
        x = rng.randrange(1, max(2, width - 1))
        y = rng.randrange(1, max(2, height - 4))
        if frame[y][x] in (0, 1):
            _put(frame, x, y, 4 if index % 2 else 5)
    if stage == 4:
        pulse = frame_index % 2
        for x, y in ((1, 2), (width - 2, 3), (2, height - 5), (width - 3, height - 6)):
            if (x + y + pulse) % 2:
                _put(frame, x, y, 5)
                _put(frame, x + (1 if x < width // 2 else -1), y, 7)


def _uncached_background(creature, width, height, frame_index):
    sprite = creature["sprite"]
    stage = int(creature["stage"])
    variant = int(sprite["variant"])
    seed = int(sprite["seed"])
    rng = random.Random(seed)
    frame = _frame(width, height, 0)
    horizon = max(height // 2, height - 10 - min(4, stage))
    drawer = FAMILY_DRAWERS[creature["family_id"]]
    drawer(frame, rng, stage, variant, horizon)
    _motif_mark(frame, sprite["motif"], seed, stage, frame_index)
    _stage_layer(frame, creature, rng, frame_index)
    return frame


def background_frame(creature, width=BACKGROUND_WIDTH, height=BACKGROUND_HEIGHT, frame_index=0):
    animation_frame = frame_index % 2 if creature["stage"] == 4 else 0
    key = (creature["id"], int(width), int(height), animation_frame)
    if key in _CACHE:
        frame = _CACHE.pop(key)
        _CACHE[key] = frame
        return frame
    frame = _uncached_background(creature, int(width), int(height), animation_frame)
    _CACHE[key] = frame
    if len(_CACHE) > _CACHE_LIMIT:
        _CACHE.popitem(last=False)
    return frame


def iter_background_runs(frame):
    for y, row in enumerate(frame):
        x = 0
        while x < len(row):
            color = row[x]
            start = x
            while x < len(row) and row[x] == color:
                x += 1
            yield start, y, x - start, color


def draw_background(display, creature, x, y, width, height, frame_index=0):
    scale = max(1, min(width // BACKGROUND_WIDTH, height // BACKGROUND_HEIGHT))
    pixel_width = min(BACKGROUND_WIDTH, width // scale)
    pixel_height = min(BACKGROUND_HEIGHT, height // scale)
    frame = background_frame(creature, pixel_width, pixel_height, frame_index)
    palette = background_palette_rgb565(creature)
    origin_x = x + (width - pixel_width * scale) // 2
    origin_y = y + (height - pixel_height * scale) // 2
    display.fill_rect(x, y, width, height, palette[0])
    for run_x, run_y, run_width, color_index in iter_background_runs(frame):
        display.fill_rect(
            origin_x + run_x * scale,
            origin_y + run_y * scale,
            run_width * scale,
            scale,
            palette[color_index],
        )
