#!/usr/bin/env python3
"""Turn harness PPM frames into PNGs, a contact sheet and a GIF.

  tools/host/frames.py <dir> [every]   sheet uses every Nth frame (default 4)
"""
import glob
import os
import sys
from PIL import Image


def main(d, every=4):
    paths = sorted(glob.glob(os.path.join(d, "f*.ppm")))
    if not paths:
        return
    frames = [Image.open(p).convert("RGB") for p in paths]
    frames[0].resize((frames[0].width * 2, frames[0].height * 2), Image.NEAREST).save(
        os.path.join(d, "first.png"))
    frames[-1].resize((frames[-1].width * 2, frames[-1].height * 2), Image.NEAREST).save(
        os.path.join(d, "last.png"))
    pick = frames[::every]
    cols = min(6, len(pick))
    rows = (len(pick) + cols - 1) // cols
    w, h = frames[0].size
    sheet = Image.new("RGB", (cols * (w + 4), rows * (h + 4)), (255, 0, 255))
    for i, f in enumerate(pick):
        sheet.paste(f, ((i % cols) * (w + 4), (i // cols) * (h + 4)))
    sheet.save(os.path.join(d, "sheet.png"))
    if len(frames) > 1:
        frames[0].save(os.path.join(d, "anim.gif"), save_all=True, append_images=frames[1:],
                       duration=50, loop=0)
    for p in paths:
        os.remove(p)
    print("%d frames -> %s" % (len(frames), d))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 4)
