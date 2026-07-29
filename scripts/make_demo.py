#!/usr/bin/env python
"""
make_demo.py - build the sample stone shipped in docs/.

    python scripts/make_demo.py

Writes docs/demo.gcs and docs/demo.png.  The stone is generated here rather
than borrowed from a published design, so the repository can show what the
viewer does without redistributing somebody else's cutting instructions.

It is a real cut, not a decorative mesh: sixteen pavilion mains meeting
exactly at the culet, a girdle band, sixteen crown mains, and a table whose
corners land precisely on the crown facet edges.  Every meet is computed, so
opening it in the viewer shows clean junctions the way a solved design does.
"""

import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import gcs_viewer as gv

N = 16                      # mains
R = 1.0                     # girdle radius
GIRDLE = 0.10               # girdle thickness
PAV_ANGLE = 43.0
CROWN_ANGLE = 42.0
TABLE_FRACTION = 0.62       # how far up the crown the table cuts


def ring(k, r, z):
    """Point k half-steps round the girdle, at radius r and height z."""
    t = 2 * math.pi * k / N
    return [r * math.sin(t), r * math.cos(t), z]


def facet(verts, tier, instr, tid, centre):
    V = np.array(verts, dtype=float)
    n = gv._newell(V)
    if np.dot(n, V.mean(axis=0) - centre) < 0:
        n = -n
    return {"verts": V, "normal": n, "tier": tier, "instr": instr, "tid": tid}


def build():
    apothem = R * math.cos(math.pi / N)
    culet_z = -apothem * math.tan(math.radians(PAV_ANGLE))
    crown_h = apothem * math.tan(math.radians(CROWN_ANGLE))
    apex_z = GIRDLE + crown_h
    table_z = GIRDLE + TABLE_FRACTION * crown_h
    # the crown tapers linearly from the girdle to its apex, so the radius at
    # the table's height is what makes the table corners meet the facet edges
    table_r = R * (1.0 - TABLE_FRACTION)

    centre = np.array([0.0, 0.0, (culet_z + apex_z) / 2.0])
    out = []

    for i in range(N):                                    # pavilion mains
        out.append(facet([ring(i - 0.5, R, 0.0), ring(i + 0.5, R, 0.0),
                          [0.0, 0.0, culet_z]],
                         "P1", "Cut to a center point", 0, centre))
    for i in range(N):                                    # girdle
        out.append(facet([ring(i - 0.5, R, 0.0), ring(i + 0.5, R, 0.0),
                          ring(i + 0.5, R, GIRDLE), ring(i - 0.5, R, GIRDLE)],
                         "g1", "Cut to equal depth, level the girdle", 1,
                         centre))
    for i in range(N):                                    # crown mains
        out.append(facet([ring(i - 0.5, R, GIRDLE), ring(i + 0.5, R, GIRDLE),
                          ring(i + 0.5, table_r, table_z),
                          ring(i - 0.5, table_r, table_z)],
                         "C1", "Meet the girdle and the table", 2, centre))
    out.append(facet([ring(i + 0.5, table_r, table_z) for i in range(N)],
                     "T", "Table - cut until the crown mains all meet it", 3,
                     centre))
    return out


def main():
    docs = os.path.join(HERE, "docs")
    os.makedirs(docs, exist_ok=True)
    facets = build()

    gcs = os.path.join(docs, "demo.gcs")
    gv.write_gcs(gcs, facets,
                 {"title": "Demo Stone - 16 Main Brilliant"},
                 {"color": (0.20, 0.55, 0.90)}, gear=96)
    print("wrote %s (%d facets)" % (gcs, len(facets)))

    # sanity: what was written must read back as the same stone
    back, info, _ = gv.load_design(gcs)
    assert len(back) == len(facets), "%d != %d" % (len(back), len(facets))
    rows = gv.tier_table(back, gear=info.get("gear", 96.0))
    for r in rows:
        print("  %-3s %6.2f  %s  %s" % (r["name"], r["angle"], r["section"],
                                        r["index"]))

    png = os.path.join(docs, "demo.png")
    rc = gv.main(["gcs_viewer.py", gcs, "--save", png])
    print("wrote %s (%d KB)" % (png, os.path.getsize(png) // 1024))
    return rc


if __name__ == "__main__":
    sys.exit(main())
