#!/usr/bin/env python
"""
corpus_scan.py - parse every design under one or more folders and report what
the readers cannot handle.

    python scripts/corpus_scan.py "D:\\some\\designs" [more folders...]
    python scripts/corpus_scan.py --render 200 "D:\\some\\designs"

The test suite proves the readers against stones built to exercise the format.
This proves them against reality: thousands of files written by different
programs over twenty-odd years, including ones that were truncated, hand-
edited, or exported by something nobody has a copy of any more.

Every file is parsed and its result classified, and the per-file rows are
appended and flushed as they are produced, so a run that is interrupted - or
that hits a file which hangs - still leaves everything it had already learned
on disk.  Only counts come back to the console; the detail lives in the CSV.

--render N additionally renders N evenly-spaced designs to a scratch folder,
which exercises the shading, the tier table and the PNG writer rather than
just the parsers.  It is much slower per file, which is why it samples.

Single process on purpose.  Parsing is I/O-bound and quick, and this machine
has a hard six-core budget shared across every session; a sweep like this is
not worth spending it.
"""

import argparse
import csv
import math
import os
import sys
import time
import traceback

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ.setdefault("GCS_VIEWER_NO_GUI", "1")
import gcs_viewer as gv

FIELDS = ["path", "ext", "verdict", "facets", "tiers", "gear", "vertices",
          "min_facet_verts", "degenerate_normals", "zero_area", "extent",
          "title", "detail"]


def classify(path):
    """Parse one design and describe it, without ever raising."""
    row = {k: "" for k in FIELDS}
    row["path"] = path
    row["ext"] = os.path.splitext(path)[1].lower()
    try:
        facets, info, material = gv.load_design(path)
    except Exception as e:                     # noqa: BLE001 - that is the point
        row["verdict"] = "PARSE-ERROR"
        row["detail"] = "%s: %s" % (type(e).__name__, str(e)[:160])
        return row

    if not facets:
        row["verdict"] = "NO-FACETS"
        return row

    verts = [np.asarray(f["verts"], float) for f in facets]
    allv = np.vstack(verts)
    normals = np.asarray([f["normal"] for f in facets], float)

    row["facets"] = len(facets)
    row["tiers"] = len({f.get("tid", f.get("tier", "")) for f in facets})
    row["gear"] = info.get("gear", "")
    row["vertices"] = int(sum(len(v) for v in verts))
    row["min_facet_verts"] = int(min(len(v) for v in verts))
    row["title"] = (info.get("title") or "")[:60]

    lengths = np.linalg.norm(normals, axis=1)
    row["degenerate_normals"] = int(((lengths < 0.999) | (lengths > 1.001) |
                                     ~np.isfinite(lengths)).sum())

    # a facet with no area is geometry that exists in the file and cannot be
    # seen - worth counting, because it is the shape a collapsed tier takes
    zero = 0
    for V in verts:
        n = gv._newell(V)
        a = 0.0
        for i in range(len(V)):
            a += np.dot(n, np.cross(V[i], V[(i + 1) % len(V)]))
        if abs(a) / 2.0 < 1e-9:
            zero += 1
    row["zero_area"] = zero

    extent = float(np.abs(allv).max())
    row["extent"] = round(extent, 4)

    problems = []
    if not np.isfinite(allv).all():
        problems.append("non-finite vertex")
    if row["min_facet_verts"] < 3:
        problems.append("facet with < 3 vertices")
    if extent <= 0 or not math.isfinite(extent):
        problems.append("zero or non-finite extent")
    if row["degenerate_normals"]:
        problems.append("%d unnormalised normals" % row["degenerate_normals"])

    if problems:
        row["verdict"] = "SUSPECT"
        row["detail"] = "; ".join(problems)
    elif zero:
        row["verdict"] = "ZERO-AREA"
        row["detail"] = "%d facet(s) with no area" % zero
    else:
        row["verdict"] = "OK"
    return row


RT_FIELDS = ["path", "ext", "verdict", "facets_in", "facets_out",
             "worst_vertex", "worst_normal", "detail"]


def roundtrip(path, tmpdir):
    """Parse, write_gcs, parse again, and compare.

    This is the path the solver's gem-to-gcs conversion actually takes, and
    the one place where a viewer bug would not just misdraw something but
    write a wrong file to disk.  The suite checks it against stones it built
    itself; this checks it against everything anyone ever wrote.
    """
    row = {k: "" for k in RT_FIELDS}
    row["path"] = path
    row["ext"] = os.path.splitext(path)[1].lower()
    try:
        facets, info, material = gv.load_design(path)
        if not facets:
            row["verdict"] = "SKIP-NO-FACETS"
            return row
        out = os.path.join(tmpdir, "rt.gcs")
        gv.write_gcs(out, facets, info, material, gear=info.get("gear", 96))
        back, _, _ = gv.parse_gcs(out)
    except Exception as e:                     # noqa: BLE001
        row["verdict"] = "ERROR"
        row["detail"] = "%s: %s" % (type(e).__name__, str(e)[:160])
        return row

    row["facets_in"], row["facets_out"] = len(facets), len(back)
    if len(facets) != len(back):
        row["verdict"] = "FACET-COUNT"
        return row

    wv = wn = 0.0
    tier_bad = instr_bad = 0
    for a, b in zip(facets, back):
        va, vb = np.asarray(a["verts"], float), np.asarray(b["verts"], float)
        if va.shape != vb.shape:
            row["verdict"] = "VERTEX-COUNT"
            row["detail"] = "%s vs %s" % (va.shape, vb.shape)
            return row
        wv = max(wv, float(np.abs(va - vb).max()))
        wn = max(wn, float(np.abs(np.asarray(a["normal"], float) -
                                  np.asarray(b["normal"], float)).max()))
        if (a.get("tier", "") or "") != (b.get("tier", "") or ""):
            tier_bad += 1
        if (a.get("instr", "") or "") != (b.get("instr", "") or ""):
            instr_bad += 1

    row["worst_vertex"] = "%.3g" % wv
    row["worst_normal"] = "%.3g" % wn
    problems = []
    if wv != 0.0:
        problems.append("vertices moved by %.3g" % wv)
    if wn > 1e-12:
        problems.append("normals moved by %.3g" % wn)
    if tier_bad:
        problems.append("%d tier names changed" % tier_bad)
    if instr_bad:
        problems.append("%d instructions changed" % instr_bad)
    row["verdict"] = "OK" if not problems else "MISMATCH"
    row["detail"] = "; ".join(problems)
    return row


def walk(roots):
    seen = set()
    for root in roots:
        for dirpath, _, names in os.walk(root):
            for n in sorted(names):
                if n.lower().endswith((".gcs", ".gem")):
                    p = os.path.join(dirpath, n)
                    key = os.path.normcase(p)
                    if key not in seen:
                        seen.add(key)
                        yield p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--out", default=os.path.join(HERE, "corpus_scan.csv"))
    ap.add_argument("--render", type=int, default=0,
                    help="also render this many evenly-spaced designs")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--roundtrip", action="store_true",
                    help="also write each design back out through write_gcs "
                         "and re-read it, comparing the two")
    ap.add_argument("--parse", dest="parse", action="store_true", default=True)
    ap.add_argument("--no-parse", dest="parse", action="store_false")
    args = ap.parse_args()

    files = list(walk(args.roots))
    if args.limit:
        files = files[:args.limit]
    print("%d design files under %d root(s)" % (len(files), len(args.roots)))

    done = set()
    if os.path.exists(args.out):                     # resume rather than redo
        with open(args.out, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                done.add(os.path.normcase(r["path"]))
        print("%d already scanned, skipping those" % len(done))

    counts, t0 = {}, time.time()
    if args.parse:
        fresh = not os.path.exists(args.out)
        with open(args.out, "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            if fresh:
                w.writeheader()
            for i, p in enumerate(files, 1):
                if os.path.normcase(p) in done:
                    continue
                row = classify(p)
                w.writerow(row)
                fh.flush()                           # never bank a whole run
                counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
                if i % 500 == 0:
                    print("  %d/%d  %.0fs  %s" % (i, len(files),
                                                  time.time() - t0, counts))

        print("\nparse results over %d files in %.0fs:" % (len(files),
                                                           time.time() - t0))
        for k in sorted(counts):
            print("  %-12s %d" % (k, counts[k]))
        print("detail: %s" % args.out)

    if args.roundtrip:
        import tempfile
        rt_out = os.path.splitext(args.out)[0] + ".roundtrip.csv"
        rt_done = set()
        if os.path.exists(rt_out):
            with open(rt_out, newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    rt_done.add(os.path.normcase(r["path"]))
        rt_counts, t2 = {}, time.time()
        tmpdir = tempfile.mkdtemp(prefix="corpus-roundtrip-")
        fresh = not os.path.exists(rt_out)
        with open(rt_out, "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=RT_FIELDS)
            if fresh:
                w.writeheader()
            for i, p in enumerate(files, 1):
                if os.path.normcase(p) in rt_done:
                    continue
                row = roundtrip(p, tmpdir)
                w.writerow(row)
                fh.flush()
                rt_counts[row["verdict"]] = rt_counts.get(row["verdict"], 0) + 1
                if i % 500 == 0:
                    print("  roundtrip %d/%d  %.0fs  %s"
                          % (i, len(files), time.time() - t2, rt_counts))
        print("\nwrite_gcs round-trip over %d files in %.0fs:"
              % (len(files), time.time() - t2))
        for k in sorted(rt_counts):
            print("  %-14s %d" % (k, rt_counts[k]))
        print("detail: %s" % rt_out)

    if args.render:
        import tempfile
        step = max(1, len(files) // args.render)
        sample = files[::step][:args.render]
        out = tempfile.mkdtemp(prefix="corpus-render-")
        bad = []
        t1 = time.time()
        for i, p in enumerate(sample, 1):
            png = os.path.join(out, "%04d.png" % i)
            try:
                if gv.main(["gcs_viewer.py", p, "--save", png]) != 0 or \
                        os.path.getsize(png) < 3000:
                    bad.append((p, "no usable PNG"))
            except Exception:
                bad.append((p, traceback.format_exc().splitlines()[-1]))
            if i % 25 == 0:
                print("  rendered %d/%d  %.0fs" % (i, len(sample),
                                                   time.time() - t1))
        print("\nrendered %d designs in %.0fs, %d failed"
              % (len(sample), time.time() - t1, len(bad)))
        for p, why in bad[:20]:
            print("  %s\n    %s" % (p, why))
        print("renders in %s" % out)

    return 0


if __name__ == "__main__":
    sys.exit(main())
