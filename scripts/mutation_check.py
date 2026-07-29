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
    ("let the folder listing go stale when a design is added",
     "    if hit is not None and hit[0] == stamp:",
     "    if hit is not None:"),
    ("sort the folder listing lexically instead of naturally",
     "    files.sort(key=natural_key)",
     "    files.sort()"),
    ("let the instruction-table cache return a stale image",
     "    for k, img in _INSTR_CACHE:\n        if k == key:",
     "    for k, img in _INSTR_CACHE:\n        if True:"),
    ("put a copyright line back on the sheet",
     '    parts = [info.get("shape", ""), info.get("date", "")]',
     '    parts = ["Copyright 2026", info.get("shape", "")]'),
    ("drop the designer's notes from the sheet again",
     "    notes = (info.get(\"notes\") or \"\").strip()\n    if notes:",
     "    notes = (info.get(\"notes\") or \"\").strip()\n    if False:"),
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
    ("write only the opening step of a tier, losing the rest on conversion",
     "            if s and s not in steps:\n                steps.append(s)",
     "            if s and not steps:\n                steps.append(s)"),
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

    # these can only be judged where Tk has a display; on a headless runner
    # the GUI suite skips itself and they are reported as unjudged
    ("step through the folder in one direction whatever key is pressed",
     "cand = files[(idx + direction * k) % n]",
     "cand = files[(idx + k) % n]"),
    ("stop the folder walk at the first unreadable design",
     "            except Exception:\n                continue",
     "            except Exception:\n                break"),
    ("let the 3/4 view tilt past vertical",
     "self.el = max(-88.0, min(88.0, self.el + dele))",
     "self.el = self.el + dele"),
]

# labels above that only the windowed suite can catch
GUI_ONLY = {
    "step through the folder in one direction whatever key is pressed",
    "stop the folder walk at the first unreadable design",
    "let the 3/4 view tilt past vertical",
}


def run(cwd):
    """Both suites.  A mutation is caught if either of them goes red.

    UTF-8 on both sides of the pipe, deliberately.  A failing check prints
    the detail that failed, and this program's own text is full of arrows,
    bullets and accented design names; through a pipe Python defaults to the
    console code page, and one undecodable byte kills the reader thread and
    hands back `stdout=None` - which looks like a crash in the harness rather
    than what it is.
    """
    env = dict(os.environ, GCS_VIEWER_NO_GUI="1", PYTHONIOENCODING="utf-8")
    rc, failed, gui_ran = 0, [], False
    for suite in ("test_gcs_viewer.py", "test_gui.py"):
        if not os.path.exists(os.path.join(cwd, suite)):
            continue
        p = subprocess.run([sys.executable, suite], cwd=cwd, env=env,
                           capture_output=True, encoding="utf-8",
                           errors="replace", timeout=900)
        rc = rc or p.returncode
        failed += re.findall(r"^  FAIL (.+?)   ", p.stdout, re.M)
        if suite == "test_gui.py":
            # the exact banner, not the word: one of the checks is named
            # "an unreadable design is skipped, not fatal", which made a
            # perfectly good run look like it had skipped itself
            gui_ran = "skipped: Tk has no display" not in p.stdout
    return rc, failed, gui_ran


def main():
    src = os.path.join(HERE, "gcs_viewer.py")
    with open(src, encoding="utf-8") as fh:
        original = fh.read()

    tmp = tempfile.mkdtemp(prefix="gcsviewer-mutants-")
    for suite in ("test_gcs_viewer.py", "test_gui.py"):
        if os.path.exists(os.path.join(HERE, suite)):
            shutil.copy2(os.path.join(HERE, suite), tmp)
    target = os.path.join(tmp, "gcs_viewer.py")

    shutil.copy2(src, target)
    rc, failed, gui_ran = run(tmp)
    if rc != 0:
        print("the unmutated suite already fails - fix that first:")
        print("  " + "\n  ".join(failed))
        return 1
    print("baseline: suites pass%s\n"
          % ("" if gui_ran else " (no display: the windowed suite skipped)"))

    survivors, unjudged = [], []
    for label, find, repl in MUTATIONS:
        if find not in original:
            print("SKIP  %s\n      (anchor no longer in the source: %r)"
                  % (label, find[:60]))
            survivors.append(label + " [stale anchor]")
            continue
        if label in GUI_ONLY and not gui_ran:
            print("unjudged  %s\n          (needs a display)" % label)
            unjudged.append(label)
            continue
        # every occurrence, not just the first: the .gem Y mirror appears
        # twice, and mutating only one of them leaves the geometry correct -
        # which reads as a surviving mutation when it is really a weak one
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(original.replace(find, repl))
        rc, failed, _ = run(tmp)
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
    judged = len(MUTATIONS) - len(unjudged)
    print("\n%d/%d mutations caught%s"
          % (judged - len(survivors), judged,
             " (%d unjudged without a display)" % len(unjudged)
             if unjudged else ""))
    for s in survivors:
        print("  SURVIVOR: %s" % s)
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
