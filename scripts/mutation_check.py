#!/usr/bin/env python
"""
mutation_check.py - prove the test suite would notice if the viewer broke.

A green suite only means something if it can go red.  This copies the module
and its tests into a scratch directory, introduces one deliberate defect at a
time, and reports which checks catch it.  A mutation that survives is a hole
in the suite, not a success.

    python scripts/mutation_check.py

Each mutation is a plain (find, replace) pair against gcs_viewer.py, so the
list below doubles as a description of what the suite is actually guarding.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MUTATIONS = [
    ("let the instruction-table cache return a stale image",
     "    for k, img in _INSTR_CACHE:\n        if k == key:",
     "    for k, img in _INSTR_CACHE:\n        if True:"),
    ("put a copyright line back on the sheet",
     'parts = [(info or {}).get("shape", ""), (info or {}).get("date", "")]',
     'parts = ["Copyright 2026", (info or {}).get("shape", "")]'),
    ("give up on a .gcs that is not valid UTF-8",
     'for enc in ("utf-8-sig", "cp1252", "latin-1"):',
     'for enc in ():'),
    ("drop the .gem Y mirror",
     "* np.array([1.0, -1.0, 1.0])",
     "* np.array([1.0, 1.0, 1.0])"),
    ("stop culling back faces",
     "if float(np.dot(n, forward)) >= -1e-6:",
     "if False:"),
    ("draw nearest-first instead of farthest-first",
     "drawables.sort(key=lambda t: -t[0])",
     "drawables.sort(key=lambda t: t[0])"),
    ("ignore the gear when computing index positions",
     "idxs.append(int(round(ang / (2 * math.pi) * gear)) % gi)",
     "idxs.append(int(round(ang / (2 * math.pi) * 96)) % 96)"),
    ("section every tier as Crown",
     'section = "Pavilion" if nz < 1e-3 else "Crown"',
     'section = "Crown"'),
    ("read only the first facet's instruction, losing later steps in a tier",
     "            if s and s not in instrs:\n                instrs.append(s)",
     "            if s and not instrs:\n                instrs.append(s)"),
    ("lose the tier instruction text",
     'rows.append({"name": str(grp[0].get("tier", "") or ""), "angle": angle,',
     'rows.append({"name": "", "angle": angle,'),
    ("skip the trailing strings in .gem (the 2026-07-13 title/notes work)",
     'info["title"] = trailing[0].strip()',
     'info["title"] = ""'),
    ("merge two same-named tiers into one on write",
     "        if len(by_tid) > len(by_name):\n            boundaries = by_tid",
     "        if False:\n            boundaries = by_tid"),
    ("write vertices at reduced precision",
     "return repr(float(x))",
     'return "%.3f" % float(x)'),
    ("ignore the light= override",
     "lgt = LIGHT if light is None else \\",
     "lgt = LIGHT if True else \\"),
    ("freeze the top view to the legacy basis, breaking az rotation",
     "right = np.array([ca, sa, 0.0])",
     "right = np.array([1.0, 0.0, 0.0])"),
]


def run(cwd):
    env = dict(os.environ, GCS_VIEWER_NO_GUI="1")
    p = subprocess.run([sys.executable, "test_gcs_viewer.py"], cwd=cwd,
                       env=env, capture_output=True, text=True, timeout=900)
    failed = re.findall(r"^  FAIL (.+?)   ", p.stdout, re.M)
    return p.returncode, failed


def main():
    src = os.path.join(HERE, "gcs_viewer.py")
    with open(src, encoding="utf-8") as fh:
        original = fh.read()

    tmp = tempfile.mkdtemp(prefix="gcsviewer-mutants-")
    shutil.copy2(os.path.join(HERE, "test_gcs_viewer.py"), tmp)
    target = os.path.join(tmp, "gcs_viewer.py")

    shutil.copy2(src, target)
    rc, failed = run(tmp)
    if rc != 0:
        print("the unmutated suite already fails - fix that first:")
        print("  " + "\n  ".join(failed))
        return 1
    print("baseline: suite passes\n")

    survivors = []
    for label, find, repl in MUTATIONS:
        if find not in original:
            print("SKIP  %s\n      (anchor no longer in the source: %r)"
                  % (label, find[:60]))
            survivors.append(label + " [stale anchor]")
            continue
        # every occurrence, not just the first: the .gem Y mirror appears
        # twice, and mutating only one of them leaves the geometry correct -
        # which reads as a surviving mutation when it is really a weak one
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(original.replace(find, repl))
        rc, failed = run(tmp)
        if rc == 0:
            print("SURVIVED  %s" % label)
            survivors.append(label)
        else:
            print("caught    %s" % label)
            if failed:
                print("          %d check(s), first: %s"
                      % (len(failed), failed[0]))
            else:
                # a non-zero exit with no FAIL lines means the mutant made the
                # suite raise rather than report - still caught, less useful
                print("          suite errored out rather than reporting")

    shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d/%d mutations caught" % (len(MUTATIONS) - len(survivors),
                                        len(MUTATIONS)))
    for s in survivors:
        print("  SURVIVOR: %s" % s)
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
