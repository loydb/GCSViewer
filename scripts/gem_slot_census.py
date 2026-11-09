#!/usr/bin/env python
r"""
gem_slot_census.py - how often each of a .gem's eight trailing slots is used.

    python scripts\gem_slot_census.py "D:\Gemology" "D:\Facetdiagrams.org"

WHY
---
A .gem's trailing strings are eight fixed fields (gcs_viewer.GEM_SLOTS), and
an unused one is an EMPTY string, not a missing one.  That is what made two
earlier readings of the chain lose the comment lines: stopping at the first
blank, and then stopping after two.  This counts how many files fill each
slot, so the claim that the later slots are populated at all is a measurement
rather than an assumption - and so the "N of M subtitles begin with 'by'"
figure behind leaving <info author> empty can be recounted rather than quoted.

Prints a line per slot and nothing else; parse failures are counted, not
dumped.  Reads only - it writes no files anywhere.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gcs_viewer as gv                                       # noqa: E402


def main(argv=None):
    roots = (argv if argv is not None else sys.argv[1:])
    if not roots:
        sys.exit(__doc__.strip().splitlines()[2].strip())

    seen = set()
    counts = {s: 0 for s in gv.GEM_SLOTS}
    files = bad = by = subtitled = 0
    for root in roots:
        for dirpath, _dirs, names in os.walk(root):
            for n in sorted(names):
                if not n.lower().endswith(".gem"):
                    continue
                p = os.path.join(dirpath, n)
                key = os.path.normcase(os.path.abspath(p))
                if key in seen:
                    continue
                seen.add(key)
                files += 1
                try:
                    _facets, info, _mat = gv.parse_gem(p)
                except Exception:
                    bad += 1
                    continue
                for s in gv.GEM_SLOTS:
                    if (info.get(s) or "").strip():
                        counts[s] += 1
                sub = (info.get("header1") or "").strip()
                if sub:
                    subtitled += 1
                    if sub.lower().startswith("by "):
                        by += 1

    print("%d .gem files, %d unreadable" % (files, bad))
    for s in gv.GEM_SLOTS:
        print("  %-8s %5d" % (s, counts[s]))
    print('%d of %d subtitles begin with "by "' % (by, subtitled))
    return 0


if __name__ == "__main__":
    sys.exit(main())
