#!/usr/bin/env python
"""
make_demo_anim.py - the README's illustration, with the stone turning.

    python scripts/make_demo_anim.py

Writes docs/demo-turn.webp: the same sheet make_demo.py produces, except the
3/4 panel turns - left and right, and up and down.  A still picture of this
program looks like a diagram; the point of the third panel is that you can
grab it and move it on both axes, and only an animation says so.

Only the 3/4 panel is re-rendered per frame.  The table and side views are
drawn once and reused, and each frame is assembled by the viewer's own
compose(), so the layout cannot drift from what the application produces and
there is no panel geometry duplicated here.

Animated WebP rather than GIF: a third of the bytes, full colour instead of a
256-entry palette, and delays in exact milliseconds.  GitHub renders it in a
README the same as any image.
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))
os.environ.setdefault("GCS_VIEWER_NO_GUI", "1")

import gcs_viewer as gv
from make_demo import build

PANEL = 300           # on-screen panel size for each of the three views
FRAMES = 48
MS = 60               # ~2.9 s for the full loop
COLOUR = (0.20, 0.55, 0.90)
QUALITY = 72

# Not a spin.  A continuous revolution of a sixteen-main round stone reads as
# a shimmer, because the silhouette repeats every 22.5 degrees and barely
# changes anyway - and it shows only one of the two axes you can drag.  This
# turns it left and right *and* tips it up and down, the elevation a quarter
# cycle out of phase with the azimuth so the viewpoint travels an ellipse
# rather than sawing along a diagonal.  Both are sinusoidal, so the motion
# eases at the extremes the way a hand does, and both return exactly to where
# they started, so the loop is seamless.
AZ_MID, AZ_SWING = 35.0, 55.0      # -20 to 90 degrees around the stone
EL_MID, EL_SWING = 26.0, 22.0      # 4 to 48 degrees above the girdle


def main():
    facets = build()
    scale = gv.world_scale(facets)
    info = {"title": "Demo Stone - 16 Main Brilliant"}

    # the two fixed panels and the instruction table are drawn once
    top = gv.render_view(facets, gv.view_basis(0, 90), scale, COLOUR,
                         size=PANEL, ss=2, labels=True)
    side = gv.render_view(facets, gv.view_basis(0, 0), scale, COLOUR,
                          size=PANEL, ss=2, labels=True)
    rows = gv.tier_table(facets, gear=96)
    instr = gv.render_instructions(rows, width=PANEL * 3 + 32)

    frames = []
    for i in range(FRAMES):
        t = 2 * math.pi * i / FRAMES
        az = AZ_MID + AZ_SWING * math.sin(t)
        el = EL_MID + EL_SWING * math.cos(t)
        spun = gv.render_view(facets, gv.view_basis(az, el), scale, COLOUR,
                              size=PANEL, ss=2, labels=True)
        # composed by the application's own layout code, not re-implemented
        frames.append(gv.compose([top, side, spun], info, "demo.gcs", PANEL,
                                 instr_img=instr).convert("RGB"))
        sys.stdout.write("\r  rendered %d/%d" % (i + 1, FRAMES))
        sys.stdout.flush()
    print()

    docs = os.path.join(HERE, "docs")
    os.makedirs(docs, exist_ok=True)
    out = os.path.join(docs, "demo-turn.webp")
    frames[0].save(out, format="WEBP", save_all=True,
                   append_images=frames[1:], duration=MS, loop=0,
                   quality=QUALITY, method=4)

    kb = os.path.getsize(out) / 1024.0
    print("wrote %s (%dx%d, %d frames, %.0f KB)"
          % (out, frames[0].width, frames[0].height, len(frames), kb))
    if kb > 3000:
        print("  that is large for a README - lower PANEL or FRAMES")
    return 0


if __name__ == "__main__":
    sys.exit(main())
