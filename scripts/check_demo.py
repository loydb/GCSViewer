#!/usr/bin/env python
"""
check_demo.py - the committed demo stone still matches its generator.

    python scripts/check_demo.py

docs/demo.gcs illustrates the README, and is produced by make_demo.py. If the
two ever part company, the picture describes a stone the program no longer
makes.

Compared as geometry, not as bytes. A .gcs stores full-precision reprs of
coordinates computed with sin, cos and tan, and those are library calls: the
last bit differs between the Windows CRT and glibc, so the same generator
writes files that differ in the seventeenth digit on different machines. A
byte comparison fails there for reasons that have nothing to do with this
program - which is exactly what it did on the Linux CI job, once.
"""

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))
os.environ.setdefault("GCS_VIEWER_NO_GUI", "1")

import gcs_viewer as gv
from make_demo import build

TOL = 1e-9


def main():
    committed = os.path.join(HERE, "docs", "demo.gcs")
    if not os.path.exists(committed):
        sys.exit("docs/demo.gcs is missing - run scripts/make_demo.py")

    on_disk, info, _ = gv.load_design(committed)
    fresh = build()

    if len(on_disk) != len(fresh):
        sys.exit("demo.gcs has %d facets, the generator makes %d"
                 % (len(on_disk), len(fresh)))

    worst = 0.0
    for i, (a, b) in enumerate(zip(on_disk, fresh)):
        if (a.get("tier") or "") != (b.get("tier") or ""):
            sys.exit("facet %d: tier %r on disk, %r from the generator"
                     % (i, a.get("tier"), b.get("tier")))
        if (a.get("instr") or "") != (b.get("instr") or ""):
            sys.exit("facet %d: instruction %r on disk, %r from the generator"
                     % (i, a.get("instr"), b.get("instr")))
        va, vb = np.asarray(a["verts"], float), np.asarray(b["verts"], float)
        if va.shape != vb.shape:
            sys.exit("facet %d: %s vertices on disk, %s from the generator"
                     % (i, va.shape, vb.shape))
        worst = max(worst, float(np.abs(va - vb).max()))

    if worst > TOL:
        sys.exit("demo.gcs geometry differs from the generator by %.3g "
                 "(tolerance %g) - regenerate it with scripts/make_demo.py"
                 % (worst, TOL))

    print("docs/demo.gcs matches its generator: %d facets, %d tiers, "
          "worst vertex difference %.3g" %
          (len(fresh), len({f["tid"] for f in on_disk}), worst))
    return 0


if __name__ == "__main__":
    sys.exit(main())
