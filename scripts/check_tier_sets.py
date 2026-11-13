#!/usr/bin/env python
r"""
check_tier_sets.py - does the viewer colour a stone the way the research does?

    python scripts\check_tier_sets.py "D:\designs" --limit 300

WHY
---
The ten tier-colour sets only mean anything if the colours land where the
research says they should: touching tiers at least SEP apart in CIEDE2000 as
that viewer SEES them. `gcs_viewer` carries its own port of
`tier_adjacency.graph` and `tier_assign.assign`; this runs the research's own
code beside it over real designs and compares, tier for tier.

A difference in the TIER COUNT is not a failure. The research reads `<tier>`
elements straight out of the XML; the viewer splits a tier element that holds
more than one cutting step, which is the whole point of `tier_groups()`. Those
designs are reported separately and skipped, since there is nothing to compare
them against.

Needs the research tree and scikit-image, so this is a workstation check, not
something the test suite can run. Read-only: it opens design files and writes
nothing but its own report.
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESEARCH_SCRIPTS = r"D:\Facetdiagrams.org\Scripts"
PALETTES = r"D:\Facetdiagrams.org\research\tier-colors\palettes.json"

# (viewer set id, key in palettes.json, which field)
PAIRS = [
    ("vibrant", "normal", "optimized_alternative"),
    ("pastel", "normal", "colors"),
    ("deuteranomaly", "deuteranomaly", "colors"),
    ("protanomaly", "protanomaly", "colors"),
    ("deuteranopia", "deuteranopia", "colors"),
    ("protanopia", "protanopia", "colors"),
    ("tritanomaly", "tritanomaly", "colors"),
    ("tritanopia", "tritanopia", "colors"),
    ("achromatopsia", "achromatopsia", "colors"),
    ("bcm", "bcm", "colors"),
]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)

    if not os.path.exists(PALETTES):
        sys.exit("the research tree is not on this machine: %s" % PALETTES)
    sys.path.insert(0, RESEARCH_SCRIPTS)
    sys.path.insert(0, HERE)
    import json
    import tier_adjacency as ta
    import tier_assign as tas
    import gcs_viewer as gv

    sets = json.load(open(PALETTES, encoding="utf-8"))["sets"]["16"]
    tables = {}
    for sid, key, field in PAIRS:
        hexes = [c.lower() for c in sets[key][field]]
        tables[sid] = (hexes,
                       tas.seen_distance(sets[key][field],
                                         key if field == "colors" else "normal"))

    files = []
    for root in a.roots:
        if os.path.isfile(root):
            files.append(root)
            continue
        for dirpath, _dirs, names in os.walk(root):
            for n in sorted(names):
                if n.lower().endswith(".gcs"):
                    files.append(os.path.join(dirpath, n))
    files.sort()
    if a.limit:
        # evenly spaced rather than the first N, so one folder cannot stand
        # in for the collection
        step = max(1, len(files) // a.limit)
        files = files[::step][:a.limit]

    checked = agreed = split = bad = 0
    disagree, shortfalls = [], {}
    for path in files:
        try:
            n_r, adj_r = ta.graph(path)
            facets, _info, _mat = gv.load_design(path)
            order, adj_v = gv.tier_adjacency(facets)
        except Exception:
            bad += 1
            continue
        if n_r != len(order):
            split += 1
            continue
        if any(set(adj_r.get(i, set())) != adj_v[i] for i in range(n_r)):
            disagree.append((path, "adjacency"))
            continue
        checked += 1
        same = True
        for sid, (hexes, D) in tables.items():
            col_r, short_r = tas.assign(n_r, adj_r, D)
            pal_v, short_v = gv.tier_palette_set(facets, sid)
            want = [hexes[col_r[i]] for i in range(n_r)]
            got = ["#%02x%02x%02x" % tuple(int(round(c * 255)) for c in rgb)
                   for rgb in pal_v.values()]
            if short_v:
                shortfalls[sid] = shortfalls.get(sid, 0) + 1
            if want != got or short_r != short_v:
                same = False
                disagree.append((path, sid))
        agreed += same

    print("%d designs; %d comparable, %d agreed with the research"
          % (len(files), checked, agreed))
    print("  %d skipped: a <tier> element holding more than one cutting step"
          % split)
    print("  %d unreadable" % bad)
    if shortfalls:
        print("  shortfalls (no colour far enough from a neighbour): "
              + ", ".join("%s %d" % kv for kv in sorted(shortfalls.items())))
    for path, why in disagree[:20]:
        print("  DIFFERS (%s) %s" % (why, path))
    return 1 if disagree else 0


if __name__ == "__main__":
    sys.exit(main())
