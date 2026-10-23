#!/usr/bin/env python3
"""Clips for the Reddit / profile showcase card that shows off the settings:
the movement ticks the whole time while the finish and hands change.

  tools/showcase_clips.py      -> ~/Projects/pebble/showcase/recordings/skeleton-watch/
                                  configs_chalk.gif, configs_gabbro.gif,
                                  card_720x320.png

The card is the store banner with only the name: no tagline. Both clips are
15 s so they loop together and both open on blued hands. The Round 2 holds its
first look a second longer, so the changes run left to right a second apart,
and the two watches never show the same finish at the same time.

Then: cd ~/Projects/pebble/showcase && python3 build_showcase.py skeleton-watch
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
import store_assets  # noqa: E402

OUT = os.path.expanduser("~/Projects/pebble/showcase/recordings/skeleton-watch")

# (finish, hands): finishes 0 Classic 1 Gold 2 Steel 3 Rose 4 Black;
# hands 0 white 1 blued 2 gold.
CHALK = [(1, 1), (2, 2), (0, 0), (4, 1), (3, 2), (2, 1)]
GABBRO = [(0, 1), (4, 2), (2, 0), (1, 1), (0, 2), (3, 0)]

HOLD = 2500   # ms per look
LEADS = {"chalk": 0, "gabbro": 1000}

# Card geometry (1x, 720x320), as store_assets.banner() places the watches.
W, H = 720, 320
SCREENS = {"chalk": (256, 100, 180, 180), "gabbro": (452, 30, 260, 260)}


def script(looks, lead):
    ev = ["M1"]  # tick all the time
    for k, (finish, hands) in enumerate(looks):
        ms = HOLD + (lead if k == 0 else 0) - (lead if k == len(looks) - 1 else 0)
        ev += ["f%d" % finish, "h%d" % hands, "w%d" % ms]
    return ev


def card(path):
    """The store banner with blank screens and just the name."""
    im = Image.new("RGBA", (W, H), (8, 8, 12, 255))
    d = ImageDraw.Draw(im)
    font = ImageFont.truetype(store_assets.SERIF, 52, index=0)
    col = 250 // 2
    for i, word in enumerate(("Skeleton", "Watch")):
        w = d.textlength(word, font=font)
        d.text((col - w / 2, 100 + i * 56), word, font=font, fill=(255, 170, 0))
    for plat in ("chalk", "gabbro"):
        x, y, w, _ = SCREENS[plat]
        tile = store_assets.round_watch(Image.new("RGB", (w, w), (0, 0, 0)), 6)
        im.alpha_composite(tile, (x - 6, y - 6))
    im.convert("RGB").save(path)


def main():
    os.makedirs(OUT, exist_ok=True)
    for plat, looks in (("chalk", CHALK), ("gabbro", GABBRO)):
        frames = store_assets.harness(plat, "10:08", script(looks, LEADS[plat]))
        path = os.path.join(OUT, "configs_%s.gif" % plat)
        store_assets.save_gif(frames, path)
        print(path, len(frames), "frames", "%.2fs" % (len(frames) * store_assets.FRAME_MS / 1000))
    card(os.path.join(OUT, "card_720x320.png"))
    print(os.path.join(OUT, "card_720x320.png"))


if __name__ == "__main__":
    main()
