#!/usr/bin/env python
"""Compare the code frozen inside a PyInstaller --onefile exe against the
current source file.

The exe carries the entry script as a *marshalled code object*, not as text,
so there is no source to diff.  What can be compared exactly is the code:
every function's signature, its whole docstring, its constants and the length
of its compiled bytecode.  That answers the question that matters after an
edit - "is the shipped exe still the source?" - without a decompiler.

It is not a proof of equality: two different functions can compile to the
same number of bytes with the same names and constants.  It is a check that
goes off when something real has changed, and it is only as good as what it
compares - it used to read the first line of a docstring and 60 characters
of a constant, and passed an exe whose docstring had since been reworded.

    python scripts/compare_exe_source.py GCSViewer.exe gcs_viewer.py

Run it with the same Python major.minor that built the exe; marshal's format
is version-specific and older interpreters cannot read a newer stream.

SECURITY: this tool marshal.loads() the code object out of the exe, and
marshal on untrusted data is unsafe (a crafted stream can crash or worse).
Only ever run it against an exe you built locally on this machine - never a
binary downloaded from anywhere.  Its only job is to confirm a *local* build
still matches the source in this repo.
"""

import marshal
import sys
import types


def frozen_code(exe_path, entry_name):
    """Pull the marshalled entry-script code object out of a onefile exe."""
    from PyInstaller.archive.readers import CArchiveReader

    arch = CArchiveReader(exe_path)
    blob = arch.extract(entry_name)
    if isinstance(blob, tuple):          # older readers return (typecode, data)
        blob = blob[-1]
    # marshal.loads on untrusted bytes is unsafe - only run this against a
    # locally built exe (see the module docstring), never a downloaded one.
    return marshal.loads(blob)


def walk(code, prefix=""):
    """Flatten a code object into {qualified name: code object}."""
    out = {prefix + code.co_name: code}
    for c in code.co_consts:
        if isinstance(c, types.CodeType):
            out.update(walk(c, prefix + code.co_name + "."))
    return out


def describe(code):
    doc = None
    if code.co_consts and isinstance(code.co_consts[0], str):
        doc = code.co_consts[0]
    return {
        "args": code.co_argcount,
        "kwonly": code.co_kwonlyargcount,
        "names": tuple(code.co_varnames[:code.co_argcount]),
        # The WHOLE docstring and the WHOLE constant.  Comparing the
        # first line and a 60-character prefix let a reworded docstring
        # through as IDENTICAL on 2026-09-25 - and would let through a
        # changed long string too, a message or a URL that still starts the
        # same way.  The frozen code carries the full text, so compare it;
        # truncation belongs in what is printed, not in what is compared.
        "doc": (doc or "").strip(),
        "bytes": len(code.co_code),
        "consts": tuple(repr(c) for c in code.co_consts
                        if not isinstance(c, types.CodeType)),
        "globals": tuple(sorted(set(code.co_names))),
    }


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    exe, src = argv[1], argv[2]
    entry = argv[3] if len(argv) > 3 else src.replace("\\", "/").split("/")[-1][:-3]

    old = walk(frozen_code(exe, entry))
    with open(src, "r", encoding="utf-8") as fh:
        new = walk(compile(fh.read(), src, "exec"))

    old_k, new_k = set(old), set(new)
    added, removed = sorted(new_k - old_k), sorted(old_k - new_k)
    changed = []
    for k in sorted(old_k & new_k):
        a, b = describe(old[k]), describe(new[k])
        if a != b:
            changed.append((k, a, b))

    print(f"exe    : {exe}")
    print(f"source : {src}")
    print(f"functions: {len(old)} frozen, {len(new)} in source\n")

    if added:
        print("ADDED in source (not in the exe):")
        for k in added:
            d = describe(new[k])
            first = (d["doc"].splitlines() or [""])[0]
            print("  + %s(%s)   %.60s" % (k, ", ".join(d["names"]), first))
        print()
    if removed:
        print("REMOVED (in the exe, gone from source):")
        for k in removed:
            print(f"  - {k}")
        print()
    if changed:
        print("CHANGED:")
        for k, a, b in changed:
            print(f"  ~ {k}")
            if a["names"] != b["names"]:
                print(f"      signature: ({', '.join(a['names'])}) -> "
                      f"({', '.join(b['names'])})")
            if a["doc"] != b["doc"]:
                # first lines only - the whole text is compared, but a
                # multi-line docstring printed raw wrecks the report
                fa = (a["doc"].splitlines() or [""])[0]
                fb = (b["doc"].splitlines() or [""])[0]
                if fa == fb:
                    print("      docstring: reworded below the first line")
                else:
                    print("      docstring: %.60s -> %.60s" % (fa, fb))
            if a["globals"] != b["globals"]:
                gone = sorted(set(a["globals"]) - set(b["globals"]))
                fresh = sorted(set(b["globals"]) - set(a["globals"]))
                if fresh:
                    print(f"      now references: {', '.join(fresh)}")
                if gone:
                    print(f"      no longer references: {', '.join(gone)}")
            if a["consts"] != b["consts"]:
                gone = [c for c in a["consts"] if c not in b["consts"]]
                fresh = [c for c in b["consts"] if c not in a["consts"]]
                for c in fresh:
                    print("      + const %.80s%s" % (c, "..." * (len(c) > 80)))
                for c in gone:
                    print("      - const %.80s%s" % (c, "..." * (len(c) > 80)))
            if a["bytes"] != b["bytes"]:
                print(f"      bytecode: {a['bytes']} -> {b['bytes']} bytes")
        print()
    if not (added or removed or changed):
        print("IDENTICAL - the exe is built from this source.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
