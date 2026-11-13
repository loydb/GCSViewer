#!/usr/bin/env python
r"""
check_commit.py - run the suites against what was COMMITTED, not the worktree.

    python scripts/check_commit.py            # HEAD
    python scripts/check_commit.py 596d9a4    # any commit

WHY
---
On 2026-11-13 a commit was made, both suites were run, an exe was built from
that commit, and every check passed - while the commit was missing half the
feature it claimed to add.  The suites had been run against the WORKING TREE,
which had the whole thing; the staging helper had quietly dropped the rest.
A suite run proves something about the files it ran against and nothing about
any other set of files.

This checks out the commit into a throwaway worktree and runs both suites
there.  It is the gate between committing and building an exe.

Untracked files are NOT copied in: that is the point.  If the committed tree
cannot pass on its own, it is not a tree anybody should build from.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*a, cwd=REPO):
    return subprocess.run(["git"] + list(a), cwd=cwd, text=True,
                          capture_output=True)


def main(argv):
    rev = argv[1] if len(argv) > 1 else "HEAD"
    sha = git("rev-parse", "--short", rev).stdout.strip()
    if not sha:
        sys.exit("no such commit: %s" % rev)
    subject = git("log", "-1", "--format=%s", sha).stdout.strip()
    print("checking commit %s  %s\n" % (sha, subject))

    tmp = tempfile.mkdtemp(prefix="gcsviewer-commit-")
    tree = os.path.join(tmp, "tree")
    r = git("worktree", "add", "--detach", tree, sha)
    if r.returncode:
        sys.exit("could not make a worktree:\n" + r.stderr)

    rc = 0
    try:
        for suite in ("test_gcs_viewer.py", "test_gui.py"):
            path = os.path.join(tree, suite)
            if not os.path.exists(path):
                print("MISSING  %s is not in this commit" % suite)
                rc = 1
                continue
            p = subprocess.run([sys.executable, suite], cwd=tree,
                               text=True, capture_output=True)
            tail = [ln for ln in p.stdout.splitlines()
                    if "checks passed" in ln or ln.startswith("  FAIL")]
            print("%-22s %s" % (suite, tail[-1].strip() if tail
                                else "NO RESULT LINE"))
            for ln in tail[:-1]:
                print("    " + ln.strip())
            if p.returncode:
                rc = 1
                err = (p.stderr or "").strip().splitlines()
                for ln in err[-6:]:
                    print("    " + ln)
    finally:
        git("worktree", "remove", "--force", tree)
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n%s" % ("the commit stands on its own" if rc == 0
                    else "THE COMMIT DOES NOT PASS - do not build from it"))
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
