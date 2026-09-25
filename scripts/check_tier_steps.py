#!/usr/bin/env python
"""
check_tier_steps.py - does every <tier> in these files hold ONE cutting step,
and does the stone survive being re-cut from what the tiers say?

    python scripts/check_tier_steps.py "D:\\some\\designs" [more...]
    python scripts/check_tier_steps.py --recut "D:\\some\\designs"

WHY
---
A .gcs <tier> carries one angle= and one depth= for all of its facets:

    <tier angle="141.0" depth="0.3507711312728803" name="P3" ...>

Gem Cut Studio draws the 3D stone straight from the stored polygons, so a
tier holding facets from two different cuts still looks perfect on screen.
Its SHEET is different: GCS re-cuts the stone from (angle, index, depth) per
tier to print the facet table, the instructions and the plan views, and there
the second cut is dropped along with every later tier that met it.

  Saw Tooth Marquise (Graham, Book 04): 57 facets in the mesh, and GCS
  printed "Total facets 27" over a plan view whose lines do not close.

--recut approximates that arithmetic here - every tier becomes one
half-space per facet index at the tier's own depth, and the intersection is
counted - so the damage can be seen without opening Gem Cut Studio.

It is an approximation and not a copy: on Saw Tooth Marquise it leaves 43 of
the 57 facets standing where Gem Cut Studio printed 27, so it tells you that
facets are lost, not how many.  Whatever else Gem Cut Studio does on the way
to a sheet is not modelled here.  The mixed-tier count above it IS exact -
the file either has a tier holding two steps or it does not - and that is the
defect itself, so it is the number to regress against.

--recut is also the slow path and needs scipy.

Read-only.  Nothing is written but the console summary and, with --csv, a
row per file.
"""

import argparse
import csv
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ.setdefault("GCS_VIEWER_NO_GUI", "1")

import gcs_viewer as gv                                      # noqa: E402


def tiers_of(facets):
    """Facets grouped by the <tier> element they were read from, which is
    what tid is; NOT gv.tier_groups(), which already splits on the step and
    so could never report a mixed tier."""
    out = []
    for f in facets:
        key = (f.get("tid"), f.get("tier", ""))
        if not out or out[-1][0] != key:
            out.append((key, []))
        out[-1][1].append(f)
    return out


def mixed(facets):
    """[(tier name, [step key, ...]), ...] for the tiers holding more than
    one cutting step."""
    bad = []
    for (_tid, name), grp in tiers_of(facets):
        steps = list(dict.fromkeys(gv.step_key(f) for f in grp))
        if len(steps) > 1:
            bad.append((name, steps))
    return bad


def recut(facets, gear=96):
    """How many faces the stone has when it is re-cut from what the tiers
    say - one plane per (tier depth, facet index), intersected.

    This is the sheet's arithmetic, not the file's geometry: the normal is
    rebuilt from the tier's angle and the facet's index, and the distance is
    the tier's depth.  A tier holding two cuts can only lend one depth to
    all of its facets, so the facets belonging to the other cut come out at
    the wrong distance and are swallowed."""
    from scipy.optimize import linprog
    from scipy.spatial import HalfspaceIntersection

    planes = []
    for _key, grp in tiers_of(facets):
        angle, depth = gv.facet_plane(grp[0])          # the tier's own pair
        nz = math.cos(math.radians(angle))
        h = math.sqrt(max(0.0, 1.0 - nz * nz))
        for f in grp:
            n = np.asarray(f["normal"], float)
            n = n / (np.linalg.norm(n) or 1.0)
            az = math.atan2(n[0], n[1])                 # the facet's index
            planes.append(([h * math.sin(az), h * math.cos(az), nz], depth))

    A = np.array([p[0] for p in planes], float)
    b = np.array([p[1] for p in planes], float)
    norm = np.linalg.norm(A, axis=1, keepdims=True)
    res = linprog(c=[0, 0, 0, -1], A_ub=np.hstack([A, norm]), b_ub=b,
                  bounds=[(None, None)] * 3 + [(0, None)], method="highs")
    if not res.success or res.x[3] <= 1e-9:
        raise ValueError("degenerate: the tiers do not enclose a solid")
    hs = HalfspaceIntersection(np.hstack([A, -b[:, None]]), res.x[:3])
    pts = hs.intersections

    faces = 0
    for n, d in zip(A, b):
        on = pts[np.abs(pts @ n - d) < 1e-7 * max(1.0, abs(d))]
        if len(on) < 3:
            continue
        c = on.mean(axis=0)
        u = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
        u = u - n * (u @ n)
        u = u / np.linalg.norm(u)
        v = np.cross(n, u)
        on = on[np.argsort(np.arctan2((on - c) @ v, (on - c) @ u))]
        area = 0.5 * np.linalg.norm(
            sum(np.cross(on[j] - on[0], on[(j + 1) % len(on)] - on[0])
                for j in range(1, len(on) - 1)))
        if area > 1e-9:
            faces += 1
    return faces


def gcs_files(roots):
    for r in roots:
        if os.path.isfile(r):
            yield r
            continue
        for base, _dirs, names in os.walk(r):
            for n in sorted(names):
                if n.lower().endswith(".gcs"):
                    yield os.path.join(base, n)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+", help="a .gcs file or a folder of them")
    ap.add_argument("--recut", action="store_true",
                    help="also count the faces a re-cut from the tiers gives")
    ap.add_argument("--csv", help="write a row per file here")
    a = ap.parse_args(argv)

    rows, n_mixed, n_short, n_files = [], 0, 0, 0
    for path in gcs_files(a.roots):
        n_files += 1
        try:
            facets, _info, _mat = gv.parse_gcs(path)
        except Exception as exc:                       # a corpus has everything
            print("  unreadable: %s (%s)" % (path, exc))
            continue
        bad = mixed(facets)
        faces = ""
        if a.recut:
            try:
                faces = recut(facets)
            except Exception as exc:
                faces = "failed: %s" % exc
            if isinstance(faces, int) and faces < len(facets):
                n_short += 1
                print("  re-cuts to %d of %d facets: %s"
                      % (faces, len(facets), path))
        if bad:
            n_mixed += 1
            print("  %d mixed tier(s): %s" % (len(bad), path))
            for name, steps in bad[:3]:
                print("      %-10s %s" % (name or "(unnamed)",
                                          "  ".join(map(str, steps))))
        rows.append({"file": path, "facets": len(facets),
                     "tiers": len(tiers_of(facets)), "mixed": len(bad),
                     "recut_faces": faces})

    print("\n%d file(s): %d with a mixed tier" % (n_files, n_mixed), end="")
    print(", %d that re-cut short" % n_short if a.recut else "")

    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, ["file", "facets", "tiers", "mixed",
                                    "recut_faces"])
            w.writeheader()
            w.writerows(rows)
        print("wrote %s" % a.csv)

    return 1 if n_mixed or n_short else 0


if __name__ == "__main__":
    sys.exit(main())
