#!/usr/bin/env python3
"""Appstore set, rendered by the Mac harness (it runs the real movement code,
so frames match the emulator pixel for pixel).

  tools/store_assets.py [platform ...]     default: gabbro and chalk

Writes into store/:
  <plat>_1_preview.gif   a flick sets the movement ticking (8 s, real speed)
  <plat>_2_time.png      10:08, Classic finish, at rest
  <plat>_3_ticking.png   mid-swing, Black finish
  <plat>_4_gold.png      Gold finish, blued hands
  <plat>_5_steel.png     Steel finish
  reddit_gabbro.gif      the gabbro preview at 2x
  icon_80x80.png, icon_144x144.png, banner_720x320.png
"""
import glob
import math
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STORE = os.path.join(ROOT, "store")
sys.path.insert(0, os.path.dirname(__file__))
import make_art as M  # noqa: E402

PLATFORMS = ["gabbro", "chalk"]
FRAME_MS = 40
SERIF = "/System/Library/Fonts/Supplemental/Didot.ttc"


def harness(plat, start, events):
    out = tempfile.mkdtemp(prefix="skeleton-")
    env = dict(os.environ, KEEP="1")
    subprocess.run([os.path.join(ROOT, "tools/host/run.sh"), plat, out, start] + events,
                   cwd=ROOT, env=env, check=True, capture_output=True)
    frames = [Image.open(p).convert("RGB") for p in sorted(glob.glob(os.path.join(out, "f*.ppm")))]
    shutil.rmtree(out)
    return frames


def palette_image():
    """One fixed palette of the 64 watch colours: exact pixels, small GIFs."""
    pal = []
    for r in (0, 85, 170, 255):
        for g in (0, 85, 170, 255):
            for b in (0, 85, 170, 255):
                pal += [r, g, b]
    im = Image.new("P", (1, 1))
    im.putpalette(pal + [0, 0, 0] * (256 - 64))
    return im


def save_gif(frames, path, ms=FRAME_MS, scale=1):
    pal = palette_image()
    if scale > 1:
        frames = [f.resize((f.width * scale, f.height * scale), Image.NEAREST) for f in frames]
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    q[0].save(path, save_all=True, append_images=q[1:], duration=ms, loop=0, optimize=True)


def shots(plat):
    # The harness opens with the movement already running (as the face does);
    # M2 holds it still for the opening frame, M0 + p sets it going.
    gif = harness(plat, "10:08", ["M2", "s", "s", "s", "M0", "p", "w8000"])
    save_gif(gif, os.path.join(STORE, "%s_1_preview.gif" % plat))
    if plat == "gabbro":
        save_gif(gif, os.path.join(STORE, "reddit_gabbro.gif"), scale=2)
    harness(plat, "10:08", ["M2", "s"])[0].save(os.path.join(STORE, "%s_2_time.png" % plat))
    harness(plat, "10:08", ["f4", "p", "w1180"])[-1].save(os.path.join(STORE, "%s_3_ticking.png" % plat))
    harness(plat, "10:08", ["f1", "h1", "M2", "s"])[0].save(os.path.join(STORE, "%s_4_gold.png" % plat))
    harness(plat, "10:08", ["f2", "h2", "M2", "s"])[0].save(os.path.join(STORE, "%s_5_steel.png" % plat))
    print(plat, "done")


# ---------------------------------------------------------- icons/banner --

WHEEL = {1: (85, 0, 0), 2: (170, 85, 0), 3: (255, 170, 0), 4: (255, 170, 0), 5: (255, 255, 85),
         6: (255, 255, 170)}
STEEL = {1: (0, 0, 85), 2: (85, 85, 85), 3: (170, 170, 170), 4: (170, 170, 170), 5: (255, 255, 255),
         6: (255, 255, 255)}


class IconGeo:
    """Enough of make_art.Geo to render one gear at icon size."""

    def __init__(self, size, pitch):
        self.size, self.s, self.c = size, size / M.DESIGN, size / 2.0
        self.pitch, self.m = pitch, pitch / math.pi
        self.plat = "icon"

    def px(self, v):
        return v * self.s


def wheel_layer(size, cx, cy, teeth, pitch, rim, spokes, rot, colours, solid=False):
    """RGBA image of one shaded wheel (rim frame + spokes) at icon scale."""
    g = IconGeo(size, pitch)
    gear = {"name": "icon", "teeth": teeth, "rp": teeth * g.m / 2, "rim": rim}
    gear["add"], gear["ded"], gear["hw"] = 0.34 * pitch, 0.44 * pitch, 0.23 * pitch
    gear["r_root"] = gear["rp"] - gear["ded"]
    gear["r_tip"] = gear["rp"] + gear["add"]
    gear["r_in"] = 0.0 if solid else gear["r_root"] - rim
    ss = M.SS
    xs = (np.arange(size * ss) + 0.5) / ss - cx
    x, y = np.meshgrid(xs, (np.arange(size * ss) + 0.5) / ss - cy)
    r, phi = np.hypot(x, y), np.arctan2(y, x)
    mask = M.gear_mask(r, phi, rot, gear)
    hub = r <= max(4.0, gear["rp"] * 0.2)
    mask |= hub
    for k in range(spokes):
        a = 2 * math.pi * (k / spokes + rot / teeth) + 0.4
        end = (gear["r_in"] + 1) * math.cos(a), (gear["r_in"] + 1) * math.sin(a)
        mask |= M.seg_dist(x, y, (0, 0), end) <= max(1.5, gear["rp"] * 0.07)
    v = M.bevel(mask, max(1.0, size / 90))
    cov = M.down(mask.astype(np.float32))
    vm = M.down(v * mask) / np.maximum(cov, 1e-6)
    roles = np.where(cov >= 0.5, 1 + M.quantise(vm, 6), 0)
    rgba = np.zeros((size, size, 4), np.uint8)
    for role, col in colours.items():
        rgba[roles == role] = col + (255,)
    return Image.fromarray(rgba, "RGBA")


def jewel_layer(size, cx, cy, r):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rc = r * 1.6
    d.ellipse((cx - rc, cy - rc, cx + rc, cy + rc), fill=(255, 255, 85))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(170, 0, 0))
    d.ellipse((cx - r * 0.8, cy - r * 0.8, cx + r * 0.5, cy + r * 0.5), fill=(255, 0, 85))
    h = max(1, r * 0.35)
    d.ellipse((cx - r * 0.55, cy - r * 0.55, cx - r * 0.55 + h, cy - r * 0.55 + h), fill=(255, 255, 255))
    return im


def icon(size):
    """A big gold wheel with a jewelled arbor, meshing a steel one in the corner."""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    pitch = size / 9.5
    big_teeth, small_teeth = 16, 10
    rb, rs = big_teeth * pitch / math.pi / 2, small_teeth * pitch / math.pi / 2
    bx, by = size * 0.44, size * 0.56
    d = rb + rs
    a = math.radians(-48)
    sx, sy = bx + d * math.cos(a), by + d * math.sin(a)
    # Phase the small wheel into the big one's gap (make_art.layout()).
    ph = ((a + math.pi) * small_teeth / (2 * math.pi) - 0.5 + a * big_teeth / (2 * math.pi)) % 1.0
    im.alpha_composite(wheel_layer(size, sx, sy, small_teeth, pitch, size / 22, 3, ph, STEEL))
    im.alpha_composite(wheel_layer(size, bx, by, big_teeth, pitch, size / 14, 5, 0.0, WHEEL))
    im.alpha_composite(jewel_layer(size, bx, by, max(2.5, size / 20)))
    return im.convert("RGB")


def round_watch(im, bezel):
    """The face in a dark round bezel, as an RGBA tile."""
    w = im.width
    out = Image.new("RGBA", (w + 2 * bezel, w + 2 * bezel), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    d.ellipse((0, 0, out.width - 1, out.height - 1), fill=(60, 60, 64))
    d.ellipse((bezel // 2, bezel // 2, out.width - 1 - bezel // 2, out.height - 1 - bezel // 2), fill=(25, 25, 28))
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, w - 1, w - 1), fill=255)
    out.paste(im, (bezel, bezel), mask)
    return out


def banner():
    """Title and tagline on the left, then the two watches side by side."""
    W, H = 720, 320
    im = Image.new("RGBA", (W, H), (8, 8, 12, 255))
    d = ImageDraw.Draw(im)
    title = ImageFont.truetype(SERIF, 52, index=0)
    tag = ImageFont.truetype(SERIF, 17, index=0)
    d.text((20, 34), "Skeleton", font=title, fill=(255, 170, 0))
    d.text((20, 88), "Watch", font=title, fill=(255, 170, 0))
    for i, line in enumerate(("A see-through movement:", "gears turn behind the hands",
                              "and the balance ticks.", "Flick to set it going.")):
        d.text((22, 172 + i * 24), line, font=tag, fill=(225, 225, 230))
    gw = round_watch(Image.open(os.path.join(STORE, "gabbro_2_time.png")).convert("RGB"), 6)
    cw = round_watch(Image.open(os.path.join(STORE, "chalk_4_gold.png")).convert("RGB"), 6)
    gx = W - gw.width - 2
    im.alpha_composite(gw, (gx, (H - gw.height) // 2))
    im.alpha_composite(cw, (gx - cw.width - 4, (H - cw.height) // 2 + 30))
    return im.convert("RGB")


def main():
    os.makedirs(STORE, exist_ok=True)
    plats = sys.argv[1:] or PLATFORMS
    for p in plats:
        shots(p)
    if not sys.argv[1:]:
        icon(144).save(os.path.join(STORE, "icon_144x144.png"))
        icon(80).save(os.path.join(STORE, "icon_80x80.png"))
        banner().save(os.path.join(STORE, "banner_720x320.png"))
        print("icons and banner done")


if __name__ == "__main__":
    main()
