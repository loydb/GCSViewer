#!/usr/bin/env python
"""
gen_icon.py - draw the application icon with the application.

    python scripts/gen_icon.py

Writes docs/gcsviewer.ico.  The icon is the demo stone rendered by the
viewer's own renderer, at a low tilt so the silhouette keeps the pointed
pavilion that reads as "gem" at 16 pixels.  Nothing is drawn by hand, so the
icon cannot drift away from what the program actually produces.

The renderer paints on a solid dark panel, which an icon must not have.  The
alpha channel therefore comes from a second pass over the same geometry with
the lighting model flattened to pure white - a coverage mask.  Keying the
colour pass instead would delete the stone's own dark facets: a pavilion in
shadow is only a few levels away from the background, so the bottom half of
the gem would silently vanish and leave a floating crown.  The mask is
Lanczos-downsampled like everything else, so partial coverage along the
silhouette arrives as partial alpha.

The colour pass uses the light= override to mix a headlight into the fixed
light.  A 3/4 view lit only from the upper left leaves the pavilion nearly
black, which is fine in a 460-pixel panel and unreadable at 16.

build_exe.py picks the .ico up automatically; Install-GcsViewer.ps1 also
points the .gcs/.gem document type at it, so Explorer shows the gem rather
than a blank page.
"""

import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

import gcs_viewer as gv
from make_demo import build

SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128),
         (256, 256)]
BG = np.array([14, 14, 16])            # render_view's panel colour
AZ, EL = 30.0, 18.0                    # low enough to keep the culet visible


def coverage_mask(facets, basis, scale):
    """Render the same stone as a flat white silhouette.  AMBIENT/DIFFUSE/
    SPEC_K are module-level constants, so they are borrowed and put back."""
    saved = (gv.AMBIENT, gv.DIFFUSE, gv.SPEC_K)
    gv.AMBIENT, gv.DIFFUSE, gv.SPEC_K = 1.0, 0.0, 0.0
    try:
        flat = gv.render_view(facets, basis, scale, (1.0, 1.0, 1.0),
                              size=512, ss=3, labels=False)
    finally:
        gv.AMBIENT, gv.DIFFUSE, gv.SPEC_K = saved
    dist = np.abs(np.asarray(flat).astype(int) - BG).max(axis=2)
    alpha = np.clip(dist * (255.0 / (255 - int(BG.max()))), 0, 255)
    # facet outlines are drawn 70 levels darker, which would otherwise show up
    # as a lattice of translucent seams across a solid stone
    alpha[alpha > 150] = 255
    return alpha


def main():
    facets = build()
    scale = gv.world_scale(facets)
    basis = gv.view_basis(AZ, EL)
    cam = basis[3]

    # 55% headlight, 45% the viewer's own fixed light: enough modelling to
    # show the facets, not so much that the pavilion goes to black
    light = 0.55 * np.asarray(cam) + 0.45 * np.asarray(gv.LIGHT)
    panel = gv.render_view(facets, basis, scale, (0.20, 0.55, 0.90),
                           size=512, ss=3, labels=False, light=light)

    rgb = np.asarray(panel).astype(int)
    alpha = coverage_mask(facets, basis, scale)
    rgba = np.dstack([rgb.astype(np.uint8), alpha.astype(np.uint8)])
    img = Image.fromarray(rgba, "RGBA")

    ys, xs = np.nonzero(alpha > 8)
    if not len(xs):
        sys.exit("nothing rendered - cannot build an icon from an empty panel")
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    img = img.crop((int(x0), int(y0), int(x1), int(y1)))

    # square it with a small margin, so no size in the .ico distorts the stone
    side = int(max(img.width, img.height) * 1.06)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - img.width) // 2, (side - img.height) // 2))

    docs = os.path.join(HERE, "docs")
    os.makedirs(docs, exist_ok=True)
    out = os.path.join(docs, "gcsviewer.ico")
    square.resize((256, 256), Image.LANCZOS).save(out, format="ICO",
                                                  sizes=SIZES)
    print("wrote %s (%d bytes, %d sizes)" % (out, os.path.getsize(out),
                                             len(SIZES)))

    png = os.path.join(docs, "icon-preview.png")
    strip = Image.new("RGBA", (sum(s[0] for s in SIZES) + 8 * len(SIZES), 256),
                      (0, 0, 0, 0))
    x = 0
    with Image.open(out) as ico:
        for w, h in SIZES:
            ico.size = (w, h)
            frame = ico.convert("RGBA")
            strip.paste(frame, (x, 256 - h), frame)
            x += w + 8
    strip.save(png)
    print("wrote %s" % png)
    return 0


if __name__ == "__main__":
    sys.exit(main())
