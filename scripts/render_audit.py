#!/usr/bin/env python
"""
render_audit.py - find designs that render wrongly rather than not at all.

    python scripts/render_audit.py "D:\\designs" [--ext .gem] [--limit N]

A render sweep that only asks "did it crash?" passes a stone drawn inside
out.  The .gem reader has to *infer* which way each face points - the stored
normals cannot be trusted, so they are recomputed with Newell's method and
flipped to point away from the centre of the stone.  When that inference is
wrong the facet is culled instead of drawn, and the result is a gem with a
hole in it, or nothing at all: a perfectly valid PNG of almost nothing.

So this measures ink.  For each design it renders the three panels and reports
what fraction of each is not background, plus how many facets survived the
back-face cull.  A solid stone fills a good part of its panel from every
angle; a stone whose normals are inverted goes nearly empty from at least one.

Only the outliers are printed.  Everything else is a count.
"""

import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ.setdefault("GCS_VIEWER_NO_GUI", "1")
import gcs_viewer as gv

BG = np.array([14, 14, 16])
VIEWS = (("top", (0, 90)), ("side", (0, 0)), ("34", (35, 28)))

# render_view reserves a fixed 46*ss pixel margin, so the drawable area is a
# fraction of the panel and that fraction depends on the panel size.  At 120
# pixels only a 28-pixel box is left and a perfectly good stone measures 4%
# ink.  Measure at the size the application actually uses, and against the
# drawable area rather than the whole panel, so the number means something.
PANEL = 460
MARGIN = 46
DRAWABLE = ((PANEL - 2 * MARGIN) / float(PANEL)) ** 2


def ink(facets, scale, colour, angles):
    img = gv.render_view(facets, gv.view_basis(*angles), scale, colour,
                         size=PANEL, ss=1, labels=False)
    a = np.asarray(img).astype(int)
    return float((np.abs(a - BG).max(axis=2) > 6).mean()) / DRAWABLE


def visible(facets, angles):
    fwd = gv.view_basis(*angles)[2]
    return sum(1 for f in facets if float(np.dot(f["normal"], fwd)) < -1e-6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--ext", default=".gcs,.gem")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--floor", type=float, default=0.15,
                    help="a panel filling less of the drawable area than "
                         "this is reported")
    args = ap.parse_args()

    exts = tuple(e.strip().lower() for e in args.ext.split(","))
    files = []
    for root in args.roots:
        for dp, _, ns in os.walk(root):
            files += [os.path.join(dp, n) for n in sorted(ns)
                      if n.lower().endswith(exts)]
    if args.limit:
        files = files[:args.limit]
    print("auditing %d designs" % len(files))

    flagged, skipped, stats = [], 0, {k: [] for k, _ in VIEWS}
    for i, p in enumerate(files, 1):
        try:
            facets, _, material = gv.load_design(p)
            if not facets:
                skipped += 1
                continue
            scale = gv.world_scale(facets)
            if not math.isfinite(scale) or scale <= 0:
                flagged.append((p, "degenerate scale", {}, {}))
                continue
            inks = {k: ink(facets, scale, material["color"], a)
                    for k, a in VIEWS}
            vis = {k: visible(facets, a) for k, a in VIEWS}
        except Exception as e:                 # noqa: BLE001
            skipped += 1
            continue
        for k in inks:
            stats[k].append(inks[k])
        worst = min(inks, key=inks.get)
        if inks[worst] < args.floor or min(vis.values()) == 0:
            flagged.append((p, "thin %s panel" % worst, inks, vis))
        if i % 250 == 0:
            print("  %d/%d, %d flagged" % (i, len(files), len(flagged)))

    print("\n%d audited, %d unreadable, %d flagged" %
          (len(files) - skipped, skipped, len(flagged)))
    for k, _ in VIEWS:
        v = np.array(stats[k]) if stats[k] else np.array([0.0])
        print("  %-4s ink  median %.3f   5th pct %.3f   min %.3f"
              % (k, float(np.median(v)), float(np.percentile(v, 5)),
                 float(v.min())))
    for p, why, inks, vis in flagged[:25]:
        print("  %-58s %s" % (os.path.basename(p)[:58], why))
        if inks:
            print("      ink %s   facets facing camera %s"
                  % ({k: round(x, 3) for k, x in inks.items()}, vis))
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
