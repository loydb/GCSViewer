#!/usr/bin/env python
"""
make_demo_anim.py - the README's illustration, with the stone turning.

    python scripts/make_demo_anim.py

Writes docs/demo-turn.webp: the same sheet make_demo.py produces, except the
3/4 panel turns - left and right, and up and down - and the "Colour-code
tiers" checkbox is ticked and unticked as it runs.  A still picture of this
program looks like a diagram; the two things that most need saying about the
window are that the last panel can be grabbed and moved on both axes, and
that one box swaps the material colour for a colour per tier.  Only an
animation says either.

Only the 3/4 panel is re-rendered per frame.  The table, pavilion and side
views are drawn once per colour mode and reused, and each frame is assembled
by the viewer's own compose(), so the layout cannot drift from what the
application produces and there is no panel geometry duplicated here.
compose() captions panels by POSITION from PANEL_LABELS, so the list passed
to it must hold every panel the application shows, in the application's
order.

The one thing drawn here and nowhere else is the control row - compose()
returns the sheet split at the seam under the panels, exactly as the window
takes it, and the checkbox is painted into the gap the window fills with a
real tk widget.  It is a picture of that widget, so its colours are the
widget's colours, read off the ViewerApp construction below.

Animated WebP rather than GIF: a third of the bytes, full colour instead of a
256-entry palette, and delays in exact milliseconds.  GitHub renders it in a
README the same as any image.
"""

import math
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))
os.environ.setdefault("GCS_VIEWER_NO_GUI", "1")

import gcs_viewer as gv
from make_demo import build

PANEL = 260           # on-screen panel size for each of the four views
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

# The frames on which the box is clicked: off at the first, on again at the
# second.  Both are interior to the loop, so neither the pointer nor the
# state has to wrap around the seam - the loop opens and closes ticked, which
# is how the window opens.
TOGGLES = (16, 34)
POINTER_LEAD = 3      # frames the pointer is shown either side of a click

# The control row, matching ViewerApp: a Checkbutton on #1a1a1e with
# fg #c8c8d0 and selectcolor #33333a, packed padx=PANEL_PAD + 4.
STRIP_H = 34
BG = (26, 26, 30)
CHECK_FG = (200, 200, 208)
CHECK_SEL = (51, 51, 58)
CHECK_EDGE = (122, 122, 134)
CHECK_MARK = (232, 232, 240)
BOX = 15


def draw_controls(width, checked, pointer=False):
    """The window's control row as a strip: the checkbox, and the pointer on
    the frames around a click."""
    strip = Image.new("RGB", (width, STRIP_H), BG)
    d = ImageDraw.Draw(strip)
    font = gv._load_font(15)

    x = gv.PANEL_PAD + 4
    y = (STRIP_H - BOX) // 2
    d.rectangle([x, y, x + BOX, y + BOX],
                fill=CHECK_SEL if checked else BG, outline=CHECK_EDGE)
    if checked:
        d.line([(x + 3, y + 8), (x + 6, y + 11), (x + 12, y + 4)],
               fill=CHECK_MARK, width=2)
    d.text((x + BOX + 8, y - 1), "Colour-code tiers", fill=CHECK_FG, font=font)

    if pointer:
        # tip inside the box, so it is unambiguous what is being clicked
        tx, ty = x + 5, y + 6
        arrow = [(0, 0), (0, 15), (4, 11), (7, 17), (10, 15), (7, 10), (12, 10)]
        d.polygon([(tx + a, ty + b) for a, b in arrow],
                  fill=(245, 245, 250), outline=(20, 20, 24))
    return strip


def sheet(panels, info, instr, checked, pointer):
    """One frame: the sheet the window shows, control row and all.

    compose(split=True) hands back the same canvas cut at the seam under the
    panels, which is how the window gets the gap it packs the checkbox into.
    """
    top_img, bottom_img = gv.compose(panels, info, "demo.gcs", PANEL,
                                     instr_img=instr, split=True)
    strip = draw_controls(top_img.width, checked, pointer)
    frame = Image.new("RGB", (top_img.width,
                              top_img.height + STRIP_H + bottom_img.height), BG)
    frame.paste(top_img, (0, 0))
    frame.paste(strip, (0, top_img.height))
    frame.paste(bottom_img, (0, top_img.height + STRIP_H))
    return frame


def main():
    facets = build()
    scale = gv.world_scale(facets)
    info = {"title": "Demo Stone - 16 Main Brilliant"}

    palette = gv.tier_palette(facets)
    names = gv.tier_labels(facets)

    # the three fixed panels, once per colour mode; the cutting table is the
    # same either way, because its names are derived from the geometry rather
    # than tied to how the facets are painted
    fixed = {}
    for checked in (True, False):
        kw = {"palette": palette, "names": names} if checked else {}
        fixed[checked] = [
            gv.render_view(facets, gv.view_basis(0, 90), scale, COLOUR,
                           size=PANEL, ss=2, labels=True, **kw),
            gv.render_view(facets, gv.view_basis(180, -90), scale, COLOUR,
                           size=PANEL, ss=2, labels=True,
                           light=gv.LIGHT_BELOW, **kw),
            gv.render_view(facets, gv.view_basis(0, 0), scale, COLOUR,
                           size=PANEL, ss=2, labels=True, **kw),
        ]
    rows = gv.tier_table(facets, gear=96)
    instr = gv.render_instructions(rows, width=gv.instr_width(PANEL))

    frames = []
    for i in range(FRAMES):
        t = 2 * math.pi * i / FRAMES
        az = AZ_MID + AZ_SWING * math.sin(t)
        el = EL_MID + EL_SWING * math.cos(t)
        checked = sum(i >= f for f in TOGGLES) % 2 == 0
        pointer = any(abs(i - f) <= POINTER_LEAD for f in TOGGLES)
        kw = {"palette": palette, "names": names} if checked else {}
        spun = gv.render_view(facets, gv.view_basis(az, el), scale, COLOUR,
                              size=PANEL, ss=2, labels=True, **kw)
        # composed by the application's own layout code, not re-implemented
        frames.append(sheet(fixed[checked] + [spun], info, instr,
                            checked, pointer).convert("RGB"))
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
