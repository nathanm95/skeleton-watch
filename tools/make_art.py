#!/usr/bin/env python3
"""Render the movement for each round watch into resources/data, and write
src/c/layout_gen.h with the matching geometry.

  tools/make_art.py            all platforms
  tools/make_art.py --preview  also write art/preview/*.png (art at 3x)

The trick: a gear looks the same after turning one tooth. Each gear's toothed
rim is drawn K times, each turned 1/K of a tooth further under the same light,
so frame K-1 runs straight into frame 0 and the rim loops however far the
wheel turns. Spokes break that symmetry, so the watch draws those in code at
the true angle, under the rim.

Bridges, jewels, screws and the chapter ring never move: they are one static
overlay drawn over the gears. All art is stored as colour *roles* (see
src/c/palette.c), so the Finish setting recolours it for free.

Blob layout (little-endian), resources/data/art~<platform>.bin:
  u8 count, u8 0, u16 0, u32 sheet offset[count], sheets...
  sheet: u8 frames, u8 0, u16 w, u16 h, s16 left, s16 top, u16 0,
         u32 frame offset[frames] (from the end of this table), frame data
  frame: rows back to back, bytes (run-1) << 4 | role, runs never cross a row
"""
import math
import os
import struct
import sys

import numpy as np
from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "resources", "data")
PREVIEW = os.path.join(ROOT, "art", "preview")
HEADER = os.path.join(ROOT, "src", "c", "layout_gen.h")

SS = 4          # supersampling per axis
K = 6           # frames per tooth
DESIGN = 260.0  # layout below is in gabbro pixels; chalk scales it

PLATFORMS = {
    # pitch: tooth-to-tooth distance along the pitch circle, px
    "gabbro": {"size": 260, "pitch": 6.4, "define": "PBL_PLATFORM_GABBRO"},
    "chalk": {"size": 180, "pitch": 4.9, "define": "PBL_PLATFORM_CHALK"},
}

# Light from the upper left, a little in front.
LIGHT = np.array([-1.0, -1.25, 1.4])
LIGHT = LIGHT / np.linalg.norm(LIGHT)
FLAT = LIGHT[2]

# Overlay roles: material -> (first role, levels). Gear sheets use roles 1..6
# of their own palette (WHEEL).
MATS = {"bridge": (1, 5), "gold": (6, 4), "ruby": (10, 2), "screw": (12, 2),
        "ring": (14, 1), "white": (15, 1)}
MAT_ID = {name: i + 1 for i, name in enumerate(MATS)}
MAT_NAME = {i: name for name, i in MAT_ID.items()}
WHEEL = 6

# Preview colours (the Gold finish), role -> RGB. src/c/palette.c is the truth.
PREVIEW_OVERLAY = {
    1: (0, 0, 85), 2: (85, 85, 85), 3: (170, 170, 170), 4: (170, 170, 170), 5: (255, 255, 255),
    6: (85, 85, 0), 7: (170, 85, 0), 8: (255, 170, 0), 9: (255, 255, 85),
    10: (170, 0, 0), 11: (255, 0, 0), 12: (0, 0, 170), 13: (0, 85, 255),
    14: (0, 0, 0), 15: (255, 255, 255),
}
PREVIEW_WHEEL = {1: (85, 0, 0), 2: (85, 85, 0), 3: (170, 85, 0), 4: (255, 170, 0),
                 5: (255, 255, 85), 6: (255, 255, 170)}

# ------------------------------------------------------------------ layout --
# Design units are gabbro pixels from the screen centre, y down. Angles are
# screen angles: 0 = 3 o'clock, positive = clockwise.

# The going train. Each wheel after the first meshes its parent at `angle`;
# meshing wheels turn opposite ways and pass the same number of teeth.
TRAIN = [
    {"name": "centre", "r": 30, "dir": 1, "spokes": 4, "hub": 6.0, "rim": 4.5},
    # The barrel at 12, under its ratchet wheel (overlay).
    {"name": "barrel", "parent": "centre", "angle": -90, "r": 38, "dir": -1,
     "spokes": 0, "drum": 25.0, "rim": 0},
    # Third and fourth wheels down the right-hand side.
    {"name": "third", "parent": "centre", "angle": -8, "r": 24, "dir": -1, "spokes": 5,
     "hub": 4.5, "rim": 3.5},
    {"name": "fourth", "parent": "third", "angle": 78, "r": 20, "dir": 1, "spokes": 4,
     "hub": 4.0, "rim": 3.0},
    # Motion works on the left: minute wheel and a small solid setting wheel.
    {"name": "minute", "parent": "centre", "angle": 192, "r": 21, "dir": -1, "spokes": 3,
     "hub": 4.0, "rim": 3.0},
    {"name": "setting", "parent": "minute", "angle": 235, "r": 13, "dir": 1, "spokes": 0,
     "solid": True},
]
# The escape wheel's pinion meets the fourth wheel under the escape bridge, so
# it sits on its own and steps half a tooth per beat.
ESCAPE = {"name": "escape", "pos": (35, 74), "r": 15, "teeth": 15, "dir": 1,
          "spokes": 4, "hub": 3.0, "rim": 2.5}
BALANCE = {"pos": (-22, 70), "r": 33, "rim": 3.4, "arms": 2, "screws": 12,
           "spring_r0": 4.0, "spring_r1": 21.0, "turns": 7, "stud": 300}
PLATE_IN, CHAPTER_IN = 105.0, 113.0

DRAW_ORDER = ["barrel", "centre", "third", "fourth", "minute", "setting", "escape"]

# Bridges, as curves through anchors: a gear name, "pivot" (pallet fork),
# "balance", or a plate angle in degrees. Each entry: (anchors, width); a
# middle anchor given as (r, deg) bends the curve through that design point.
BRIDGES = [
    (["plate:-148", (62, -128), "barrel"], 11),
    (["barrel", (62, -52), "plate:-32"], 11),
    (["plate:-38", (74, -22), "third"], 9),
    (["third", (66, 30), "fourth"], 8),
    (["fourth", (90, 42), "plate:52"], 9),
    (["plate:68", (95, 62), "escape"], 7),
    (["escape", "pivot"], 6),
    (["plate:142", (88, 132), "balance"], 11),
    (["plate:166", (66, 178), "minute"], 8),
    (["minute", (60, 222), "setting"], 7),
    (["setting", (92, 216), "plate:228"], 8),
    (["reserve", "plate:152"], 8),
]
# Bosses round the arbors the bridges hold: anchor -> radius.
BOSSES = {"barrel": 20, "third": 6.5, "fourth": 6, "escape": 5.5, "pivot": 5,
          "balance": 8.5, "minute": 6, "setting": 5.5}
JEWELS = ["third", "fourth", "escape", "pivot", "minute", "setting"]
# Power reserve (the watch battery): a small engraved dial at 8 o'clock whose
# blued hand the watch draws, sweeping clockwise from START to START + SWEEP.
RESERVE = {"pos": (-72, 38), "r": 15, "start": 140, "sweep": 260, "hand": 10.5}
FEET = [-148, -32, -38, 52, 68, 142, 166, 228]


class Geo:
    def __init__(self, plat):
        p = PLATFORMS[plat]
        self.plat = plat
        self.size = p["size"]
        self.s = self.size / DESIGN
        self.c = self.size / 2.0
        self.pitch = p["pitch"]
        self.m = self.pitch / math.pi

    def pt(self, d):
        """Design point -> screen px (continuous; pixel x covers [x, x+1))."""
        return (self.c + d[0] * self.s, self.c + d[1] * self.s)

    def px(self, v):
        return v * self.s


def polar(r, deg, origin=(0.0, 0.0)):
    a = math.radians(deg)
    return (origin[0] + r * math.cos(a), origin[1] + r * math.sin(a))


def layout(g):
    """Gear table in screen px for one watch."""
    gears = {}
    for spec in TRAIN:
        n = int(round(2 * spec["r"] * g.s / g.m))
        gear = dict(spec)
        gear["teeth"] = n
        gear["rp"] = n * g.m / 2
        if "parent" in spec:
            p = gears[spec["parent"]]
            d = g.m * (p["teeth"] + n) / 2
            beta = math.radians(spec["angle"])
            gear["c"] = (p["c"][0] + d * math.cos(beta), p["c"][1] + d * math.sin(beta))
            # Phase (in teeth, clockwise) that puts a gap of this wheel on
            # the parent's tooth at the contact point; see README "Meshing".
            ph = ((beta + math.pi) * n / (2 * math.pi) - 0.5 - p["phase"]
                  + beta * p["teeth"] / (2 * math.pi))
            gear["phase"] = ph % 1.0
        else:
            gear["c"] = g.pt((0, 0))
            gear["phase"] = 0.0
        gear["drive"] = 0
        gears[spec["name"]] = gear
    e = dict(ESCAPE)
    e["rp"] = g.px(e["r"])
    e["c"] = g.pt(e["pos"])
    e["phase"] = 0.0
    e["drive"] = 1
    gears["escape"] = e
    for gear in gears.values():
        add_profile(g, gear)
    return gears


def add_profile(g, gear):
    if gear["name"] == "escape":
        pe = 2 * math.pi * gear["rp"] / gear["teeth"]
        gear["add"], gear["ded"] = 0.25 * pe, 0.35 * pe
    else:
        # Teeth a little under half a pitch wide, and roots deeper than tips
        # are tall, so meshing wheels clear each other with play to spare.
        gear["add"], gear["ded"] = 0.34 * g.pitch, 0.44 * g.pitch
        gear["hw"] = 0.23 * g.pitch
    gear["r_root"] = gear["rp"] - gear["ded"]
    gear["r_tip"] = gear["rp"] + gear["add"]
    if gear.get("solid"):
        gear["r_in"] = 0.0
    elif gear.get("drum"):
        gear["r_in"] = g.px(gear["drum"])
    else:
        gear["r_in"] = gear["r_root"] - max(1.5, g.px(gear["rim"]))


# ----------------------------------------------------------------- shading --

def blur(a, sigma):
    if sigma <= 0:
        return a
    r = max(1, int(3 * sigma + 0.5))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    h, w = a.shape
    p = np.pad(a, ((0, 0), (r, r)))
    b = sum(k[i] * p[:, i:i + w] for i in range(2 * r + 1))
    p = np.pad(b, ((r, r), (0, 0)))
    return sum(k[i] * p[i:i + h, :] for i in range(2 * r + 1))


def lit(height_px, gloss=0.35):
    """Height field (px) -> brightness, 0..1, flat ground ~0.55."""
    gy, gx = np.gradient(height_px)
    nx, ny = -gx * SS, -gy * SS
    nz = np.ones_like(nx)
    n = np.sqrt(nx * nx + ny * ny + nz * nz)
    diff = (nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]) / n
    hv = LIGHT + np.array([0, 0, 1.0])
    hv = hv / np.linalg.norm(hv)
    spec = np.clip((nx * hv[0] + ny * hv[1] + nz * hv[2]) / n, 0, 1) ** 24
    flat_spec = hv[2] ** 24
    return 0.55 + 1.25 * (diff - FLAT) + gloss * (spec - flat_spec)


def bevel(mask, width_px, height=1.0):
    return lit(blur(mask.astype(np.float32), width_px * SS / 2.0) * height)


def dome(dx, dy, r, height=0.8):
    d2 = dx * dx + dy * dy
    return lit(np.sqrt(np.clip(r * r - d2, 0, None)) * height, gloss=0.8)


def down(a):
    h, w = a.shape
    return a.reshape(h // SS, SS, w // SS, SS).mean(axis=(1, 3))


def quantise(v, levels):
    return np.clip((v * levels).astype(int), 0, levels - 1)


# ------------------------------------------------------------------- gears --

def gear_mask(r, phi, rot, gear):
    """Gear body at rotation `rot` teeth (clockwise), interior cut away."""
    n = gear["teeth"]
    u = np.mod(phi * n / (2 * math.pi) - rot, 1.0)
    h = r - gear["r_root"]
    if gear["name"] == "escape":
        # Club teeth leaning the way the wheel turns (clockwise = rising u):
        # a long back slope, a short flat club, then the steep locking face.
        top = gear["add"] + gear["ded"]
        prof = np.where(u < 0.55, top * u / 0.55, np.where(u < 0.7, top, -1))
        tooth = (h >= 0) & (h <= prof)
    else:
        arc = np.minimum(u, 1 - u) * 2 * math.pi * r / n
        # Parallel flanks, then a rounded tip over the top 60% of the addendum.
        above = np.clip((h - gear["ded"] - 0.4 * gear["add"]) / (0.6 * gear["add"]), 0, None)
        hw = gear["hw"] * np.sqrt(np.clip(1 - above * above, 0, None))
        tooth = (h >= 0) & (arc <= hw)
    rim = (r >= gear["r_in"]) & (h < 0.01)
    return tooth | rim


def gear_frames(g, gear, frames):
    cx, cy = gear["c"]
    rad = gear["r_tip"] + 1.5
    left, top = int(math.floor(cx - rad)), int(math.floor(cy - rad))
    w, h = int(math.ceil(cx + rad)) - left, int(math.ceil(cy + rad)) - top
    xs = left + (np.arange(w * SS) + 0.5) / SS - cx
    ys = top + (np.arange(h * SS) + 0.5) / SS - cy
    x, y = np.meshgrid(xs, ys)
    r, phi = np.hypot(x, y), np.arctan2(y, x)
    # Concentric graining: the same at any angle, so it loops too.
    grain = 0.05 * np.sin(2 * math.pi * r / max(1.6, 2.2 * g.s))
    out = []
    for f in range(frames):
        mask = gear_mask(r, phi, f / frames, gear)
        v = bevel(mask, 1.0 if g.size > 200 else 0.8) + grain
        cov = down(mask.astype(np.float32))
        vm = down(v * mask) / np.maximum(cov, 1e-6)
        roles = np.where(cov >= 0.5, 1 + quantise(vm, WHEEL), 0)
        out.append(roles.astype(np.uint8))
    return left, top, out


def check_mesh(g, gears):
    """Meshing wheels must never overlap, at any point of the turn."""
    for gear in gears.values():
        if "parent" not in gear:
            continue
        p = gears[gear["parent"]]
        mx = (p["c"][0] + gear["c"][0]) / 2
        my = (p["c"][1] + gear["c"][1]) / 2
        span = 2 * g.pitch
        xs = mx + np.linspace(-span, span, 120)
        ys = my + np.linspace(-span, span, 120)
        x, y = np.meshgrid(xs, ys)
        worst = 0
        for step in range(12):
            d = step / 12.0
            ma = gear_mask(np.hypot(x - p["c"][0], y - p["c"][1]),
                           np.arctan2(y - p["c"][1], x - p["c"][0]), p["phase"] + p["dir"] * d, p)
            mb = gear_mask(np.hypot(x - gear["c"][0], y - gear["c"][1]),
                           np.arctan2(y - gear["c"][1], x - gear["c"][0]),
                           gear["phase"] + gear["dir"] * d, gear)
            worst = max(worst, int((ma & mb).sum()))
        if worst > 3:
            sys.exit("%s: %s and %s overlap (%d samples)" % (g.plat, p["name"], gear["name"], worst))


# ----------------------------------------------------------------- overlay --

class Canvas:
    """Full-screen supersampled material + brightness buffers."""

    def __init__(self, g):
        self.g = g
        n = g.size * SS
        self.mat = np.zeros((n, n), np.uint8)
        self.v = np.zeros((n, n), np.float32)

    def grid(self, box):
        """Sample coords (screen px) for a box (x0, y0, x1, y1) in px."""
        n = self.g.size
        x0, y0 = max(0, int(box[0]) - 2), max(0, int(box[1]) - 2)
        x1, y1 = min(n, int(math.ceil(box[2])) + 2), min(n, int(math.ceil(box[3])) + 2)
        xs = x0 + (np.arange((x1 - x0) * SS) + 0.5) / SS
        ys = y0 + (np.arange((y1 - y0) * SS) + 0.5) / SS
        x, y = np.meshgrid(xs, ys)
        return (x0 * SS, y0 * SS), x, y

    def put(self, origin, mask, material, v):
        oy, ox = origin[1], origin[0]
        h, w = mask.shape
        sub_m = self.mat[oy:oy + h, ox:ox + w]
        sub_v = self.v[oy:oy + h, ox:ox + w]
        sub_m[mask] = MAT_ID[material]
        sub_v[mask] = v[mask]

    def roles(self):
        n = self.g.size
        m = self.mat.reshape(n, SS, n, SS).transpose(0, 2, 1, 3).reshape(n, n, SS * SS)
        v = self.v.reshape(n, SS, n, SS).transpose(0, 2, 1, 3).reshape(n, n, SS * SS)
        empty = (m == 0).sum(axis=2)
        best = np.zeros((n, n), np.uint8)
        best_count = np.zeros((n, n), int)
        for mid in MAT_NAME:
            cnt = (m == mid).sum(axis=2)
            take = cnt > best_count
            best[take] = mid
            best_count[take] = cnt[take]
        out = np.zeros((n, n), np.uint8)
        for mid, name in MAT_NAME.items():
            sel = (best == mid) & (empty * 2 <= SS * SS)
            if not sel.any():
                continue
            hit = m == mid
            vm = (v * hit).sum(axis=2) / np.maximum(hit.sum(axis=2), 1)
            base, levels = MATS[name]
            out[sel] = (base + quantise(vm, levels))[sel]
        return out


def seg_dist(x, y, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = np.clip(((x - ax) * dx + (y - ay) * dy) / max(dx * dx + dy * dy, 1e-9), 0, 1)
    return np.hypot(x - (ax + t * dx), y - (ay + t * dy))


def bezier(p0, p1, p2, steps=16):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        pts.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                    (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]))
    return pts


def overlay(g, gears):
    cv = Canvas(g)
    n = g.size
    full = (0, 0, n, n)
    S = g.px
    P = g.pt
    centre = (g.c, g.c)
    bal = P(BALANCE["pos"])
    esc = gears["escape"]["c"]
    third, fourth, barrel = gears["third"]["c"], gears["fourth"]["c"], gears["barrel"]["c"]
    pivot = pallet_pivot(g, gears)

    def design(pt):
        return ((pt[0] - g.c) / g.s, (pt[1] - g.c) / g.s)

    def plate_pt(deg, r=109):
        return P(polar(r, deg))

    def anchor(a):
        if isinstance(a, tuple):
            return P(polar(a[0], a[1]))
        if a.startswith("plate:"):
            return plate_pt(float(a[6:]))
        if a == "pivot":
            return pivot
        if a == "balance":
            return bal
        if a == "reserve":
            return P(RESERVE["pos"])
        return gears[a]["c"]

    # --- bridges: one union, so their bevels run into each other ---
    o, x, y = cv.grid(full)
    rr = np.hypot(x - g.c, y - g.c)
    bridge = (rr >= S(PLATE_IN)) & (rr <= S(CHAPTER_IN + 2))
    for anchors, width in BRIDGES:
        pts = [anchor(a) for a in anchors]
        if len(pts) == 3:
            pts = bezier(*pts)
        for a, b in zip(pts, pts[1:]):
            bridge |= seg_dist(x, y, a, b) <= S(width) / 2
    for name, r in list(BOSSES.items()) + [("reserve", RESERVE["r"])]:
        c = anchor(name)
        bridge |= np.hypot(x - c[0], y - c[1]) <= S(r)
    # Polished flat faces with bright bevelled edges. (Cotes de Geneve
    # stripes were tried: at this size they read as barber poles.)
    cv.put(o, bridge, "bridge", bevel(bridge, 1.4 if n > 200 else 1.0))

    # --- the power reserve: a black dial in a steel bezel, white ticks, the
    # empty end in red ---
    rc = P(RESERVE["pos"])
    o, x, y = cv.grid((rc[0] - S(16), rc[1] - S(16), rc[0] + S(16), rc[1] + S(16)))
    dx, dy = x - rc[0], y - rc[1]
    face = np.hypot(dx, dy) <= S(RESERVE["r"] - 2.2)
    cv.put(o, face, "ring", np.full(face.shape, 0.5, np.float32))
    for k in range(5):
        a = math.radians(RESERVE["start"] + RESERVE["sweep"] * k / 4)
        u = dx * math.cos(a) + dy * math.sin(a)
        w = -dx * math.sin(a) + dy * math.cos(a)
        long_tick = k in (0, 4)
        tick = (u >= S(8 if long_tick else 9.5)) & (u <= S(12.3)) & (np.abs(w) <= max(0.5, S(0.8)))
        cv.put(o, tick, "ruby" if k == 0 else "white", np.full(tick.shape, 0.7, np.float32))

    # --- chapter ring with gold batons and white minute ticks ---
    o, x, y = cv.grid(full)
    rr = np.hypot(x - g.c, y - g.c)
    ang = np.degrees(np.arctan2(y - g.c, x - g.c))
    ring = rr >= S(CHAPTER_IN)
    cv.put(o, ring, "ring", np.full(ring.shape, 0.5, np.float32))
    ticks = np.zeros_like(ring)
    for k in range(60):
        if k % 5 == 0:
            continue
        a = math.radians(k * 6 - 90)
        u = (x - g.c) * math.cos(a) + (y - g.c) * math.sin(a)
        w = -(x - g.c) * math.sin(a) + (y - g.c) * math.cos(a)
        ticks |= (u >= S(124.5)) & (u <= S(128.5)) & (np.abs(w) <= max(0.5, S(0.6)))
    cv.put(o, ticks, "white", np.full(ticks.shape, 0.5, np.float32))
    for k in range(12):
        a = math.radians(k * 30 - 90)
        for off in ((-2.6, 2.6) if k == 0 else (0,)):
            u = (x - g.c) * math.cos(a) + (y - g.c) * math.sin(a)
            w = -(x - g.c) * math.sin(a) + (y - g.c) * math.cos(a) - S(off)
            half = S(1.9) if k % 3 == 0 else S(1.5)
            bar = (u >= S(116)) & (u <= S(128)) & (np.abs(w) <= half)
            cv.put(o, bar, "gold", bevel(bar, 0.8))

    # --- ratchet wheel on the barrel, the crown wheel and the click ---
    rt = S(24)
    box = (barrel[0] - rt - 2, barrel[1] - rt - 2, barrel[0] + rt + 2, barrel[1] + rt + 2)
    o, x, y = cv.grid(box)
    dx, dy = x - barrel[0], y - barrel[1]
    r, phi = np.hypot(dx, dy), np.arctan2(dy, dx)
    nt = 26 if n > 200 else 20
    u = np.mod(phi * nt / (2 * math.pi), 1.0)
    depth = max(2.0, S(3.4))
    ratchet = r <= (rt - depth) + depth * u
    rays = 0.06 * np.sin(phi * 40)
    # Steel with a sunburst finish, as on most movements.
    cv.put(o, ratchet, "bridge", bevel(ratchet, 1.0) + rays)
    crown_c = P(polar(37, -22, design(barrel)))
    crown = {"name": "crown", "teeth": 20 if n > 200 else 16, "rp": S(12.5), "rim": 0}
    crown["hw"] = 0.27 * (2 * math.pi * crown["rp"] / crown["teeth"])
    crown["add"] = crown["ded"] = 0.4 * (2 * math.pi * crown["rp"] / crown["teeth"])
    crown["r_root"] = crown["rp"] - crown["ded"]
    crown["r_in"] = 0
    rc = crown["rp"] + crown["add"]
    o, x, y = cv.grid((crown_c[0] - rc, crown_c[1] - rc, crown_c[0] + rc, crown_c[1] + rc))
    dx, dy = x - crown_c[0], y - crown_c[1]
    r, phi = np.hypot(dx, dy), np.arctan2(dy, dx)
    cm = gear_mask(r, phi, 0.25, crown)
    cv.put(o, cm, "bridge", bevel(cm, 1.0) + 0.06 * np.sin(phi * 30))
    # Click: a small pawl resting on the ratchet teeth at about 11 o'clock.
    ck0 = P(polar(31, -168, design(barrel)))
    ck1 = P(polar(23.5, -145, design(barrel)))
    o, x, y = cv.grid((min(ck0[0], ck1[0]) - 6, min(ck0[1], ck1[1]) - 6,
                       max(ck0[0], ck1[0]) + 6, max(ck0[1], ck1[1]) + 6))
    t = np.clip(((x - ck0[0]) * (ck1[0] - ck0[0]) + (y - ck0[1]) * (ck1[1] - ck0[1]))
                / ((ck1[0] - ck0[0]) ** 2 + (ck1[1] - ck0[1]) ** 2), 0, 1)
    click = seg_dist(x, y, ck0, ck1) <= S(3.2) * (1 - 0.6 * t)
    cv.put(o, click, "bridge", bevel(click, 0.9))

    # --- jewels in gold chatons, and blued screws ---
    def jewel(c, r):
        o, x, y = cv.grid((c[0] - r - 3, c[1] - r - 3, c[0] + r + 3, c[1] + r + 3))
        dx, dy = x - c[0], y - c[1]
        d = np.hypot(dx, dy)
        chaton = d <= r + max(1.0, S(1.6))
        cv.put(o, chaton, "gold", bevel(chaton, 0.7))
        stone = d <= r
        v = dome(dx, dy, r)
        cv.put(o, stone & (v < 0.95), "ruby", v)
        cv.put(o, stone & (v >= 0.95), "white", v)

    def screw(c, r, slot_deg):
        o, x, y = cv.grid((c[0] - r - 2, c[1] - r - 2, c[0] + r + 2, c[1] + r + 2))
        dx, dy = x - c[0], y - c[1]
        head = np.hypot(dx, dy) <= r
        v = dome(dx, dy, r, 0.6)
        a = math.radians(slot_deg)
        slot = np.abs(-dx * math.sin(a) + dy * math.cos(a)) <= max(0.45, r * 0.18)
        v = np.where(slot, 0.0, v)
        cv.put(o, head & (v < 0.97), "screw", v)
        cv.put(o, head & (v >= 0.97), "white", v)

    jr = max(1.4, S(2.4))
    for name in JEWELS:
        jewel(anchor(name), jr)
    jewel(bal, max(1.6, S(2.8)))
    screw(barrel, S(7.5), 30)
    screw(crown_c, S(3.6), -50)
    for i, deg in enumerate(FEET):
        screw(plate_pt(deg), S(3.0), 20 + 47 * i)
    return cv.roles()


def pallet_pivot(g, gears):
    e = gears["escape"]["c"]
    b = g.pt(BALANCE["pos"])
    d = math.hypot(b[0] - e[0], b[1] - e[1])
    t = (gears["escape"]["r_tip"] + g.px(5)) / d
    return (e[0] + (b[0] - e[0]) * t, e[1] + (b[1] - e[1]) * t)


def balance_rim(g):
    c = g.pt(BALANCE["pos"])
    ro = g.px(BALANCE["r"])
    ri = ro - g.px(BALANCE["rim"])
    left, top = int(math.floor(c[0] - ro - 2)), int(math.floor(c[1] - ro - 2))
    w, h = int(math.ceil(c[0] + ro + 2)) - left, int(math.ceil(c[1] + ro + 2)) - top
    xs = left + (np.arange(w * SS) + 0.5) / SS - c[0]
    ys = top + (np.arange(h * SS) + 0.5) / SS - c[1]
    x, y = np.meshgrid(xs, ys)
    r = np.hypot(x, y)
    mask = (r <= ro) & (r >= ri)
    v = bevel(mask, 0.9)
    cov = down(mask.astype(np.float32))
    vm = down(v * mask) / np.maximum(cov, 1e-6)
    return left, top, [np.where(cov >= 0.5, 1 + quantise(vm, WHEEL), 0).astype(np.uint8)]


# -------------------------------------------------------------- packing --

def rle(grid):
    out = bytearray()
    for row in grid:
        x, w = 0, len(row)
        while x < w:
            v = int(row[x])
            k = 1
            while x + k < w and row[x + k] == v and k < 16:
                k += 1
            out.append(((k - 1) << 4) | v)
            x += k
    return bytes(out)


def pack_sheet(left, top, frames):
    h, w = frames[0].shape
    bodies = [rle(f) for f in frames]
    head = struct.pack("<BBHHhhH", len(frames), 0, w, h, left, top, 0)
    offs, pos = b"", 0
    for b in bodies:
        offs += struct.pack("<I", pos)
        pos += len(b)
    return head + offs + b"".join(bodies)


def pack_blob(sheets):
    head = struct.pack("<BBH", len(sheets), 0, 0)
    table_end = len(head) + 4 * len(sheets)
    offs, pos, body = b"", table_end, b""
    for s in sheets:
        offs += struct.pack("<I", pos)
        pos += len(s)
        body += s
    return head + offs + body


def preview(path, frames, colours, scale=3, bg=(0, 0, 0)):
    h, w = frames[0].shape
    im = Image.new("RGB", (len(frames) * (w + 2), h), (255, 0, 255))
    for i, f in enumerate(frames):
        rgb = np.zeros((h, w, 3), np.uint8)
        rgb[:] = bg
        for role, col in colours.items():
            rgb[f == role] = col
        im.paste(Image.fromarray(rgb), (i * (w + 2), 0))
    im.resize((im.width * scale, im.height * scale), Image.NEAREST).save(path)


# --------------------------------------------------------------- header --

def f16(v):
    return int(round(v * 16))


def header_block(g, gears, sheet_index):
    lines = []
    lines.append("#define LAY_GEARS %d" % len(DRAW_ORDER))
    lines.append("static const GearSpec LAY_GEAR[LAY_GEARS] = {")
    lines.append("  // cx16, cy16, sheet, teeth, frames, dir, drive, phase256, spokes,"
                 " r_hub16, r_in16, w_hub16, w_rim16")
    for name in DRAW_ORDER:
        gr = gears[name]
        spokes = gr.get("spokes", 0)
        hub = g.px(gr.get("hub", 0))
        w_hub = max(2.0, g.px(3.6 if gr["teeth"] > 20 else 3.0))
        w_rim = max(1.6, g.px(2.4 if gr["teeth"] > 20 else 2.0))
        lines.append("  { %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d },  // %s, rp %.1f px" % (
            f16(gr["c"][0]), f16(gr["c"][1]), sheet_index[name], gr["teeth"], K, gr["dir"],
            gr["drive"], int(round(gr["phase"] * 256)) % 256, spokes, f16(hub),
            f16(gr["r_in"] + 0.8), f16(w_hub), f16(w_rim), name, gr["rp"]))
    lines.append("};")
    b = g.pt(BALANCE["pos"])
    ro = g.px(BALANCE["r"])
    lines += [
        "#define LAY_BAL_CX16 %d" % f16(b[0]),
        "#define LAY_BAL_CY16 %d" % f16(b[1]),
        "#define LAY_BAL_SHEET %d" % sheet_index["balance"],
        "#define LAY_BAL_R16 %d  // rim centre line" % f16(ro - g.px(BALANCE["rim"]) / 2),
        "#define LAY_BAL_RIN16 %d" % f16(ro - g.px(BALANCE["rim"]) + 0.6),
        "#define LAY_BAL_ARM_W16 %d" % f16(max(1.8, g.px(3.0))),
        "#define LAY_BAL_ARMS %d" % BALANCE["arms"],
        "#define LAY_BAL_SCREWS %d" % BALANCE["screws"],
        "#define LAY_BAL_SCREW_R16 %d" % f16(max(1.1, g.px(1.9))),
        "#define LAY_BAL_SCREW_AT16 %d  // screw centres sit on the rim's outer edge" % f16(ro - g.px(0.6)),
        "#define LAY_SPRING_R0_16 %d" % f16(g.px(BALANCE["spring_r0"])),
        "#define LAY_SPRING_R1_16 %d" % f16(g.px(BALANCE["spring_r1"])),
        "#define LAY_SPRING_TURNS %d" % (BALANCE["turns"] if g.size > 200 else 4),
        "#define LAY_SPRING_STUD_DEG %d" % BALANCE["stud"],
        "#define LAY_ROLLER_R16 %d" % f16(max(1.5, g.px(3.2))),
    ]
    pv = pallet_pivot(g, gears)
    e = gears["escape"]
    # Pallet stones sit on the escape wheel's tip circle either side of the
    # line of centres; the lever runs from the pivot to the balance roller.
    ang = math.atan2(pv[1] - e["c"][1], pv[0] - e["c"][0])
    spread = 2.5 * math.pi / e["teeth"]
    stones = []
    for sgn in (-1, 1):
        a = ang + sgn * spread
        sx = e["c"][0] + (e["r_tip"] + 0.3) * math.cos(a)
        sy = e["c"][1] + (e["r_tip"] + 0.3) * math.sin(a)
        stones.append((sx - pv[0], sy - pv[1]))
    lever_len = math.hypot(b[0] - pv[0], b[1] - pv[1]) - g.px(3.0)
    lever_ang = math.degrees(math.atan2(b[1] - pv[1], b[0] - pv[0]))
    lines += [
        "#define LAY_PALLET_X16 %d" % f16(pv[0]),
        "#define LAY_PALLET_Y16 %d" % f16(pv[1]),
        "#define LAY_PALLET_LEVER_DEG %d" % int(round(lever_ang)),
        "#define LAY_PALLET_LEVER16 %d" % f16(lever_len),
        "#define LAY_PALLET_W16 %d" % f16(max(1.6, g.px(2.6))),
        "#define LAY_STONE_R16 %d" % f16(max(1.0, g.px(1.6))),
        "static const int16_t LAY_STONE16[2][2] = { { %d, %d }, { %d, %d } };" % (
            f16(stones[0][0]), f16(stones[0][1]), f16(stones[1][0]), f16(stones[1][1])),
        "#define LAY_OVERLAY_SHEET %d" % sheet_index["overlay"],
        "#define LAY_RESERVE_X16 %d" % f16(g.pt(RESERVE["pos"])[0]),
        "#define LAY_RESERVE_Y16 %d" % f16(g.pt(RESERVE["pos"])[1]),
        "#define LAY_RESERVE_LEN16 %d" % f16(g.px(RESERVE["hand"])),
        "#define LAY_RESERVE_START_DEG %d" % RESERVE["start"],
        "#define LAY_RESERVE_SWEEP_DEG %d" % RESERVE["sweep"],
        "#define LAY_RESERVE_W16 %d" % f16(max(1.4, g.px(2.2))),
        "#define LAY_RESERVE_PIN16 %d" % f16(max(1.3, g.px(2.4))),
        "#define LAY_HAND_MIN16 %d" % f16(g.px(118)),
        "#define LAY_HAND_HOUR16 %d" % f16(g.px(76)),
        "#define LAY_HAND_MIN_W16 %d" % f16(g.px(9)),
        "#define LAY_HAND_HOUR_W16 %d" % f16(g.px(11)),
        "#define LAY_HAND_TAIL16 %d" % f16(g.px(14)),
        "#define LAY_CAP_R16 %d" % f16(g.px(6.5)),
    ]
    return lines


def main():
    want_preview = "--preview" in sys.argv
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(PREVIEW, exist_ok=True)
    blocks = []
    for plat in PLATFORMS:
        g = Geo(plat)
        gears = layout(g)
        check_mesh(g, gears)
        sheets, index = [], {}
        for name in DRAW_ORDER:
            left, top, frames = gear_frames(g, gears[name], K)
            index[name] = len(sheets)
            sheets.append(pack_sheet(left, top, frames))
            if want_preview:
                preview(os.path.join(PREVIEW, "%s_%s.png" % (plat, name)), frames, PREVIEW_WHEEL)
        left, top, frames = balance_rim(g)
        index["balance"] = len(sheets)
        sheets.append(pack_sheet(left, top, frames))
        ov = overlay(g, gears)
        index["overlay"] = len(sheets)
        sheets.append(pack_sheet(0, 0, [ov]))
        if want_preview:
            preview(os.path.join(PREVIEW, "%s_overlay.png" % plat), [ov], PREVIEW_OVERLAY, scale=2,
                    bg=(40, 0, 40))
        blob = pack_blob(sheets)
        with open(os.path.join(DATA, "art~%s.bin" % plat), "wb") as f:
            f.write(blob)
        sizes = ", ".join("%s %d" % (k, len(sheets[v])) for k, v in index.items())
        print("%s: %d bytes (%s)" % (plat, len(blob), sizes))
        blocks.append((g, gears, index))

    out = ["// Generated by tools/make_art.py: do not edit.", "#pragma once", ""]
    for i, (g, gears, index) in enumerate(blocks):
        out.append("#%s defined(%s)" % ("if" if i == 0 else "elif", PLATFORMS[g.plat]["define"]))
        out += header_block(g, gears, index)
    out += ["#else", "#error \"Skeleton supports the round watches only\"", "#endif", ""]
    with open(HEADER, "w") as f:
        f.write("\n".join(out))


if __name__ == "__main__":
    main()
