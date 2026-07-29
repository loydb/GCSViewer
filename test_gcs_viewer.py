#!/usr/bin/env python
"""
test_gcs_viewer.py - self-contained checks for the GCS Viewer.

    python test_gcs_viewer.py

No fixtures on disk and no third-party design files: every stone used here is
synthesised in the test, including the .gem binaries, which are written by a
miniature encoder built from the format notes in gcs_viewer.parse_gem.  That
is deliberate - a parser tested only against files it already parses proves
nothing about the format, whereas round-tripping through an independent
encoder pins the layout down.

The parsing half matters beyond the viewer: ~290 solver scripts in the Gram
Task 30 pipeline import parse_gcs / parse_gem / write_gcs / load_design from
this module, so these checks are the contract for that shared surface.
"""

import io
import math
import os
import struct
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gcs_viewer as gv

PASS = 0
FAIL = []


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL.append(name)
        print("  FAIL %s   %s" % (name, detail))


def near(a, b, tol=1e-9):
    return abs(float(a) - float(b)) <= tol


# ---------------------------------------------------------------------------
# Synthetic stones
# ---------------------------------------------------------------------------

def cone_facets(n, angle_deg, r=1.0, z0=0.0, down=True, tier="P1",
                instr="Cut to center point"):
    """A ring of n triangles from a girdle circle to a point on the axis -
    the pavilion (or crown) of a round brilliant, in the viewer's own dict
    format.  Normals are computed, not assumed, so the geometry is honest.

    Two details make this a real stone rather than an approximation of one.
    The apex sits at apothem*tan(angle) rather than r*tan(angle): a facet is
    flat, so its cutting angle is set by the perpendicular distance to its
    chord, not by the radius to the chord's ends - using r would cut a 43
    degree pavilion that measures 49 degrees.  And the ring is rotated by
    half a step so each facet is *centred* on an index position, which is
    what a faceting machine actually does and what makes the index list come
    out as 00-12-24 rather than 06-18-30.
    """
    out = []
    a = math.radians(angle_deg)
    apothem = r * math.cos(math.pi / n)
    h = apothem * math.tan(a)
    apex_z = z0 - h if down else z0 + h
    for i in range(n):
        t0 = 2 * math.pi * (i - 0.5) / n
        t1 = 2 * math.pi * (i + 0.5) / n
        v = np.array([
            [r * math.sin(t0), r * math.cos(t0), z0],
            [r * math.sin(t1), r * math.cos(t1), z0],
            [0.0, 0.0, apex_z],
        ])
        nrm = np.cross(v[1] - v[0], v[2] - v[0])
        nrm = nrm / np.linalg.norm(nrm)
        if (nrm[2] > 0) == down:            # point it away from the body
            nrm = -nrm
        out.append({"verts": v, "normal": nrm, "tier": tier, "instr": instr,
                    "tid": 0})
    return out


def table_facet(r=0.6, z=0.5, tier="T", instr="Table"):
    n = 8
    v = np.array([[r * math.sin(2 * math.pi * i / n),
                   r * math.cos(2 * math.pi * i / n), z] for i in range(n)])
    return [{"verts": v, "normal": np.array([0.0, 0.0, 1.0]), "tier": tier,
             "instr": instr, "tid": 1}]


def girdle_facets(n=8, r=1.0, z0=0.0, z1=0.12, tier="g1",
                  instr="Cut to equal depth"):
    out = []
    for i in range(n):
        t0 = 2 * math.pi * (i - 0.5) / n
        t1 = 2 * math.pi * (i + 0.5) / n
        v = np.array([
            [r * math.sin(t0), r * math.cos(t0), z0],
            [r * math.sin(t1), r * math.cos(t1), z0],
            [r * math.sin(t1), r * math.cos(t1), z1],
            [r * math.sin(t0), r * math.cos(t0), z1],
        ])
        mid = 0.5 * (t0 + t1)
        out.append({"verts": v,
                    "normal": np.array([math.sin(mid), math.cos(mid), 0.0]),
                    "tier": tier, "instr": instr, "tid": 2})
    return out


def synthetic_stone():
    """Pavilion + girdle + crown + table, in cutting order."""
    f = cone_facets(8, 43.0, tier="P1", instr="Cut to center point")
    f += girdle_facets()
    f += cone_facets(8, 42.0, r=1.0, z0=0.12, down=False, tier="C1",
                     instr="Meet P1.g1")
    f += table_facet(z=0.5)
    return f


GCS_XML = """<GemCutStudio version="1000">
  <index gear="80" base="0" symmetry="0" mirror="0" />
  <tier angle="137.0" depth="1.0" name="P1" instructions="Cut to center point">
    <facet nx="0.0" ny="-0.68" nz="-0.73" index_angle="0">
      <vertex x="-1.0" y="0.0" z="0.0" />
      <vertex x="1.0" y="0.0" z="0.0" />
      <vertex x="0.0" y="0.0" z="-1.07" />
    </facet>
  </tier>
  <tier angle="0.0" depth="0.5" name="T" instructions="Table">
    <facet index_angle="0">
      <vertex x="-0.5" y="-0.5" z="0.5" />
      <vertex x="0.5" y="-0.5" z="0.5" />
      <vertex x="0.5" y="0.5" z="0.5" />
      <vertex x="-0.5" y="0.5" z="0.5" />
    </facet>
  </tier>
  <render material="Quartz" refractive_index="1.54">
    <color r="0.20" g="0.55" b="0.90" />
  </render>
  <info title="Synthetic" author="Test Suite" date="2026-07-28" />
</GemCutStudio>
"""


def write_gem(path, tiers, title=None, notes=None):
    """Encode a .gem the way gcs_viewer.parse_gem documents it.

    tiers: [(tier_name, instruction, [(x, y, z), ...]), ...] - the coordinates
    are what a reader should see AFTER the Y mirror, so they are negated on
    the way in, which is what makes the round-trip meaningful.
    """
    buf = io.BytesIO()
    for name, instr, verts in tiers:
        s = ("%s\t%s" % (name, instr)).encode("ascii")
        assert 1 <= len(s) < 128
        buf.write(struct.pack("<i", 1))
        buf.write(bytes([len(s)]))
        buf.write(s)
        for (x, y, z) in verts:
            buf.write(struct.pack("<i", 1))
            buf.write(struct.pack("<3d", x, -y, z))
        # the stored face normal - flag 0, which the parser skips
        buf.write(struct.pack("<i", 0))
        buf.write(struct.pack("<3d", 0.0, 0.0, 1.0))

    def varint(s):
        b = s.encode("ascii")
        n, out = len(b), bytearray()
        while n >= 0x80:
            out.append((n & 0x7F) | 0x80)
            n >>= 7
        out.append(n)
        return bytes(out) + b

    trailing = [title] if title else []
    if isinstance(notes, str):
        trailing.append(notes)
    elif notes:
        trailing.extend(notes)
    for s in trailing:
        buf.write(varint(s))
    with open(path, "wb") as fh:
        fh.write(buf.getvalue())


# ---------------------------------------------------------------------------
# 1. .gcs parsing
# ---------------------------------------------------------------------------

def test_parse_gcs(tmp):
    p = os.path.join(tmp, "synthetic.gcs")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(GCS_XML)
    facets, info, material = gv.parse_gcs(p)

    check("gcs: facet count", len(facets) == 2, len(facets))
    check("gcs: tier names", [f["tier"] for f in facets] == ["P1", "T"])
    check("gcs: tier ids distinct", [f["tid"] for f in facets] == [0, 1])
    check("gcs: instructions carried",
          facets[0]["instr"] == "Cut to center point")
    check("gcs: gear read from <index>", near(info["gear"], 80.0))
    check("gcs: title/author from <info>",
          info.get("title") == "Synthetic" and info.get("author") == "Test Suite")
    check("gcs: material colour",
          all(near(a, b, 1e-6) for a, b in zip(material["color"],
                                               (0.20, 0.55, 0.90))),
          material["color"])
    check("gcs: stored normal is normalised",
          near(np.linalg.norm(facets[0]["normal"]), 1.0, 1e-12))

    # the table facet carries no nx/ny/nz - the parser must derive one
    n = facets[1]["normal"]
    check("gcs: missing normal derived from polygon",
          near(abs(n[2]), 1.0, 1e-12) and near(np.linalg.norm(n), 1.0, 1e-12), n)

    # vertices survive verbatim, in file order
    v = facets[1]["verts"]
    check("gcs: vertex count and order",
          v.shape == (4, 3) and near(v[0][0], -0.5) and near(v[2][1], 0.5))


def test_parse_gcs_encodings(tmp):
    """Gem Cut Studio writes the file in the machine's code page without
    declaring one, so a design titled in anything but ASCII is not valid
    UTF-8.  One file in the reference collection - a Vietnamese designer's
    "Fleur en reve" - failed to open at all because of a single byte in the
    title."""
    title = "Viet Gems 216 - Fleur en rêve"
    xml = GCS_XML.replace('title="Synthetic"', 'title="%s"' % title)

    p = os.path.join(tmp, "cp1252.gcs")
    with open(p, "wb") as fh:
        fh.write(xml.encode("cp1252"))
    try:
        facets, info, _ = gv.parse_gcs(p)
    except Exception as e:                     # noqa: BLE001
        check("encoding: a code-page title no longer rejects the whole file",
              False, "%s: %s" % (type(e).__name__, e))
        facets, info = [], {}
    check("encoding: a code-page title no longer rejects the whole file",
          len(facets) == 2, len(facets))
    check("encoding: the accented title is recovered intact",
          info.get("title") == title, info.get("title"))

    p = os.path.join(tmp, "utf8.gcs")
    with open(p, "wb") as fh:
        fh.write(xml.encode("utf-8"))
    _, info8, _ = gv.parse_gcs(p)
    check("encoding: plain UTF-8 still reads as before",
          info8.get("title") == title, info8.get("title"))

    p = os.path.join(tmp, "bom.gcs")
    with open(p, "wb") as fh:                      # BOM first, then the decl
        fh.write(b"\xef\xbb\xbf" +
                 b'<?xml version="1.0" encoding="utf-8"?>\n' +
                 xml.encode("utf-8"))
    _, infob, _ = gv.parse_gcs(p)
    check("encoding: a BOM and an XML declaration are both tolerated",
          infob.get("title") == title, infob.get("title"))


def test_empty_files(tmp):
    """Twelve zero-byte files sit in the reference collection.  Nothing can
    be done with them, but the reason should say so rather than talking
    about line 1, column 0."""
    for name in ("empty.gcs", "empty.gem"):
        p = os.path.join(tmp, name)
        open(p, "wb").close()
        try:
            gv.load_design(p)
            check("empty %s: raises" % name, False, "no exception")
        except Exception as e:                 # noqa: BLE001
            check("empty %s: says the file is empty" % name,
                  "empty" in str(e).lower(), str(e))


def test_parse_gcs_bad_normal(tmp):
    """A zero or non-finite normal must fall back to the polygon's own."""
    p = os.path.join(tmp, "bad_normal.gcs")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(GCS_XML.replace('nx="0.0" ny="-0.68" nz="-0.73"',
                                 'nx="0.0" ny="0.0" nz="0.0"'))
    facets, _, _ = gv.parse_gcs(p)
    check("gcs: degenerate normal falls back",
          near(np.linalg.norm(facets[0]["normal"]), 1.0, 1e-12),
          facets[0]["normal"])


# ---------------------------------------------------------------------------
# 2. write_gcs round-trip  (the solver writes stones through this)
# ---------------------------------------------------------------------------

def test_write_gcs_roundtrip(tmp):
    facets = synthetic_stone()
    p = os.path.join(tmp, "roundtrip.gcs")
    gv.write_gcs(p, facets, {"title": "Round Trip"}, {"color": (0.3, 0.4, 0.5)},
                 gear=96)
    back, info, material = gv.parse_gcs(p)

    check("roundtrip: facet count preserved", len(back) == len(facets),
          "%d -> %d" % (len(facets), len(back)))
    check("roundtrip: tier sequence preserved",
          [f["tier"] for f in back] == [f["tier"] for f in facets])
    check("roundtrip: instructions preserved",
          [f["instr"] for f in back] == [f["instr"] for f in facets])
    check("roundtrip: title preserved", info.get("title") == "Round Trip")
    check("roundtrip: colour preserved",
          all(near(a, b, 1e-6) for a, b in zip(material["color"],
                                               (0.3, 0.4, 0.5))))
    check("roundtrip: gear preserved", near(info["gear"], 96.0))

    worst_v = max(float(np.abs(np.asarray(a["verts"]) -
                               np.asarray(b["verts"])).max())
                  for a, b in zip(facets, back))
    worst_n = max(float(np.abs(np.asarray(a["normal"]) -
                               np.asarray(b["normal"])).max())
                  for a, b in zip(facets, back))
    check("roundtrip: vertices bit-exact (repr float)", worst_v == 0.0, worst_v)
    # normals are written with repr() too, but the reader re-normalises what it
    # reads, so a normal whose length was 1-1ulp comes back one ulp different.
    # Bit-exactness is the wrong bar here; anything above float noise is not.
    check("roundtrip: normals survive to float precision", worst_n < 1e-15,
          worst_n)

    # the <tier angle=""> attribute is how Gem Cut Studio decides Pavilion vs
    # Crown, so a wrong sign here silently mis-sections an imported stone
    import xml.etree.ElementTree as ET
    tiers = {t.get("name"): float(t.get("angle")) for t in ET.parse(p).iter("tier")}
    check("roundtrip: pavilion tier angle > 90", tiers["P1"] > 90.0, tiers)
    check("roundtrip: girdle tier angle == 90", near(tiers["g1"], 90.0, 1e-6),
          tiers)
    check("roundtrip: crown tier angle < 90", 0.0 < tiers["C1"] < 90.0, tiers)
    check("roundtrip: table tier angle == 0", near(tiers["T"], 0.0, 1e-9), tiers)


def test_write_gcs_same_named_tiers(tmp):
    """Two <tier> elements are allowed to carry the same name, and four
    designs in the reference collection do.  Grouping the output by name
    alone rewrote one of them - seven tiers - as a single tier."""
    facets = []
    for tid, (angle, instr) in enumerate([(43.0, "Cut to a center point"),
                                          (41.0, "Meet 1.g1.1"),
                                          (39.0, "Meet 1.1.2")]):
        for f in cone_facets(8, angle, tier="P1", instr=instr):
            f["tid"] = tid
            facets.append(f)

    p = os.path.join(tmp, "samename.gcs")
    gv.write_gcs(p, facets, {"title": "Same Name"}, {"color": (.5, .5, .5)})
    import xml.etree.ElementTree as ET
    tiers = list(ET.parse(p).iter("tier"))
    check("same-named tiers: three tiers written, not one", len(tiers) == 3,
          len(tiers))
    check("same-named tiers: each keeps its own instruction",
          [t.get("instructions") for t in tiers] ==
          ["Cut to a center point", "Meet 1.g1.1", "Meet 1.1.2"],
          [t.get("instructions") for t in tiers])
    check("same-named tiers: each keeps its own facets",
          [len(t.findall("facet")) for t in tiers] == [8, 8, 8],
          [len(t.findall("facet")) for t in tiers])

    back, _, _ = gv.parse_gcs(p)
    check("same-named tiers: survive a round trip", len(back) == len(facets))
    check("same-named tiers: re-read as three tiers",
          len({f["tid"] for f in back}) == 3)

    # a caller that supplies no tid must get exactly the old behaviour, since
    # every solver script that writes through here builds facets without one
    plain = [{k: v for k, v in f.items() if k != "tid"} for f in facets]
    q = os.path.join(tmp, "notid.gcs")
    gv.write_gcs(q, plain, {"title": "No Tid"}, {"color": (.5, .5, .5)})
    check("no-tid callers still group by name, unchanged",
          len(list(ET.parse(q).iter("tier"))) == 1,
          len(list(ET.parse(q).iter("tier"))))

    # and a tid that says nothing must not be allowed to merge real tiers
    flat = [dict(f, tid=0) for f in facets]
    r = os.path.join(tmp, "flattid.gcs")
    gv.write_gcs(r, flat, {"title": "Flat Tid"}, {"color": (.5, .5, .5)})
    check("a constant tid cannot merge what the names separate",
          len(list(ET.parse(r).iter("tier"))) == 1,
          len(list(ET.parse(r).iter("tier"))))


# ---------------------------------------------------------------------------
# 3. .gem parsing  (reverse-engineered binary)
# ---------------------------------------------------------------------------

GEM_TIERS = [
    ("P1", "Cut to center point",
     [(-1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.5, -1.07)]),
    ("P1", "Cut to center point",
     [(1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.5, -1.07)]),
    ("T", "Table",
     [(-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)]),
]


def test_parse_gem(tmp):
    p = os.path.join(tmp, "synthetic.gem")
    write_gem(p, GEM_TIERS, title="Alcyone Clone",
              notes="Designed by the test suite / two lines worth")
    facets, info, material = gv.parse_gem(p)

    check("gem: facet count", len(facets) == 3, len(facets))
    check("gem: tier names", [f["tier"] for f in facets] == ["P1", "P1", "T"])
    check("gem: repeated tier shares one tid",
          [f["tid"] for f in facets] == [0, 0, 1],
          [f["tid"] for f in facets])
    check("gem: instruction split on the tab",
          facets[0]["instr"] == "Cut to center point", facets[0]["instr"])
    check("gem: flag-0 normal group not read as a vertex",
          all(len(f["verts"]) == len(t[2])
              for f, t in zip(facets, GEM_TIERS)),
          [len(f["verts"]) for f in facets])

    # Y is mirrored on the way in; the encoder negated it, so it must return
    v = np.asarray(facets[0]["verts"])
    check("gem: Y un-mirrored on read", near(v[2][1], 0.5, 1e-12), v[2])
    check("gem: X and Z untouched",
          near(v[0][0], -1.0, 1e-12) and near(v[2][2], -1.07, 1e-12), v)

    # this is the 2026-07-13 addition - before it, .gem had no title at all
    check("gem: title from trailing varint strings",
          info.get("title") == "Alcyone Clone", info.get("title"))
    check("gem: notes from trailing varint strings",
          "test suite" in (info.get("notes") or ""), info.get("notes"))
    check("gem: neutral material colour when the file stores none",
          len(material["color"]) == 3)

    # a normal must point away from the body, not into it
    ctr = np.vstack([f["verts"] for f in facets]).mean(axis=0)
    outward = [float(np.dot(f["normal"], np.asarray(f["verts"]).mean(axis=0) - ctr))
               for f in facets]
    check("gem: Newell normals oriented outward", all(o > 0 for o in outward),
          outward)


def test_parse_gem_long_notes(tmp):
    """Notes over 127 chars need the multi-byte varint length, which is why
    the trailing-string reader is not the same code as the facet reader.

    Real .gem files store the note block as one string per line, and the
    reader exploits that: the exact gap before the strings varies, so it
    tries every start offset and keeps whichever chain yields the *most*
    strings.  This writes the same shape - a title and several lines, one of
    them long enough to need a two-byte length - because a single 300-byte
    blob of one repeated character is a degenerate case that the
    longest-chain heuristic can lose to a false start inside the blob.
    """
    p = os.path.join(tmp, "longnotes.gem")
    lines = [
        "Designed by the test suite, 2026-07-28",
        "Second line of the note block",
        "A deliberately long third line: " + "detail, " * 25,   # > 127 chars
        "Fourth line",
        "Fifth line",
    ]
    write_gem(p, GEM_TIERS, title="Long Notes", notes=lines)
    _, info, _ = gv.parse_gem(p)
    notes = info.get("notes") or ""
    check("gem: title read ahead of a multi-line note block",
          info.get("title") == "Long Notes", info.get("title"))
    check("gem: every note line recovered",
          all(l.strip() in notes for l in lines),
          [l[:20] for l in lines if l.strip() not in notes])
    check("gem: 200-char line survives the two-byte varint length",
          ("detail, " * 25).strip(",") in notes.replace(" /", ""),
          len(notes))
    check("gem: note lines joined with the separator",
          notes.count(" / ") == len(lines) - 1, notes.count(" / "))


def test_parse_gem_no_trailing(tmp):
    p = os.path.join(tmp, "notitle.gem")
    write_gem(p, GEM_TIERS)
    facets, info, _ = gv.parse_gem(p)
    check("gem: parses with no trailing strings at all", len(facets) == 3)
    check("gem: no title invented when the file has none",
          not (info.get("title") or "").strip(), info.get("title"))


def test_load_design_dispatch(tmp):
    g = os.path.join(tmp, "synthetic.gcs")
    m = os.path.join(tmp, "synthetic.gem")
    a, _, _ = gv.load_design(g)
    b, _, _ = gv.load_design(m)
    check("load_design: .gcs routed to parse_gcs", len(a) == 2)
    check("load_design: .gem routed to parse_gem", len(b) == 3)
    up = os.path.join(tmp, "upper.GEM")
    write_gem(up, GEM_TIERS)
    c, _, _ = gv.load_design(up)
    check("load_design: extension match is case-insensitive", len(c) == 3)


# ---------------------------------------------------------------------------
# 4. Cutting instructions table
# ---------------------------------------------------------------------------

def test_tier_table():
    rows = gv.tier_table(synthetic_stone(), gear=96)
    by = {r["name"]: r for r in rows}

    check("tiers: one row per tier", len(rows) == 4, [r["name"] for r in rows])
    check("tiers: cutting order preserved",
          [r["name"] for r in rows] == ["P1", "g1", "C1", "T"])
    check("tiers: pavilion angle from the normal",
          near(by["P1"]["angle"], 43.0, 1e-6), by["P1"]["angle"])
    check("tiers: girdle reads 90 degrees",
          near(by["g1"]["angle"], 90.0, 1e-6), by["g1"]["angle"])
    check("tiers: table reads 0 degrees", near(by["T"]["angle"], 0.0, 1e-9))
    check("tiers: girdle sections as Pavilion",
          by["g1"]["section"] == "Pavilion")
    check("tiers: crown sections as Crown", by["C1"]["section"] == "Crown")
    check("tiers: table sections as Crown", by["T"]["section"] == "Crown")
    check("tiers: table has no index list", by["T"]["index"] == "Table",
          by["T"]["index"])
    check("tiers: 8 facets on a 96 gear land 12 apart",
          by["P1"]["index"] == "00-12-24-36-48-60-72-84", by["P1"]["index"])
    check("tiers: instruction text carried through",
          by["P1"]["instr"] == "Cut to center point")

    r64 = {r["name"]: r for r in gv.tier_table(synthetic_stone(), gear=64)}
    check("tiers: index list follows the gear",
          r64["P1"]["index"] == "00-08-16-24-32-40-48-56", r64["P1"]["index"])
    r0 = gv.tier_table(synthetic_stone(), gear=0)
    check("tiers: a zero gear falls back to 96 instead of dividing by it",
          {r["name"]: r for r in r0}["P1"]["index"] == "00-12-24-36-48-60-72-84")


def test_tier_table_multi_instruction():
    """A .gem puts the instruction on the facet that begins a cutting step,
    and one tier can hold several steps - so the table has to collect them,
    not read the first facet and stop.  Across the reference collection that
    was 144 dropped lines in 56 of 245 .gem files."""
    facets = synthetic_stone()
    pav = [f for f in facets if f["tier"] == "P1"]
    pav[0]["instr"] = "Cut to a center point"
    for f in pav[1:]:
        f["instr"] = ""                       # the shape a .gem actually has
    pav[4]["instr"] = "Meet 1.g1.1"           # a second step in the same tier

    by = {r["name"]: r for r in gv.tier_table(facets, gear=96)}
    check("tiers: both steps in one tier are kept",
          by["P1"]["instr"] == "Cut to a center point · Meet 1.g1.1",
          by["P1"]["instr"])
    check("tiers: the first step still leads",
          by["P1"]["instr"].startswith("Cut to a center point"))

    # a .gcs repeats one instruction across every facet of its tier; that must
    # collapse to a single line rather than being echoed once per facet
    for f in pav:
        f["instr"] = "Cut to a center point"
    by = {r["name"]: r for r in gv.tier_table(facets, gear=96)}
    check("tiers: a repeated instruction is not duplicated",
          by["P1"]["instr"] == "Cut to a center point", by["P1"]["instr"])

    for f in pav:
        f["instr"] = ""
    by = {r["name"]: r for r in gv.tier_table(facets, gear=96)}
    check("tiers: a tier with no instruction stays empty",
          by["P1"]["instr"] == "", repr(by["P1"]["instr"]))


# ---------------------------------------------------------------------------
# 5. Camera
# ---------------------------------------------------------------------------

def test_view_basis():
    for az, el in ((0, 0), (35, 28), (137, -61), (0, 90), (180, 90), (0, -90)):
        right, up, forward, cam = gv.view_basis(az, el)
        ok = (near(np.linalg.norm(right), 1, 1e-9) and
              near(np.linalg.norm(up), 1, 1e-9) and
              near(np.linalg.norm(forward), 1, 1e-9) and
              near(np.dot(right, up), 0, 1e-9) and
              near(np.dot(right, forward), 0, 1e-9) and
              near(np.dot(up, forward), 0, 1e-9))
        check("camera: orthonormal basis at az=%s el=%s" % (az, el), ok)
        check("camera: forward is -cam_dir at az=%s el=%s" % (az, el),
              np.allclose(forward, -cam, atol=1e-12))

    # the top view is the degenerate case - az now rotates it in plane, and
    # az=0 must still reduce to the legacy fixed basis or every saved PNG
    # from before 2026-07-13 would silently change orientation
    right, up, _, cam = gv.view_basis(0, 90)
    check("camera: top view at az=0 matches the legacy basis",
          np.allclose(right, [1, 0, 0], atol=1e-12) and
          np.allclose(up, [0, 1, 0], atol=1e-12), (right, up))
    check("camera: top view looks straight down",
          np.allclose(cam, [0, 0, 1], atol=1e-12), cam)

    r180, u180, _, _ = gv.view_basis(180, 90)
    check("camera: az=180 flips the top view (book convention)",
          np.allclose(r180, [-1, 0, 0], atol=1e-12) and
          np.allclose(u180, [0, -1, 0], atol=1e-12), (r180, u180))

    # side view: camera on -Y, up is +Z
    right, up, _, cam = gv.view_basis(0, 0)
    check("camera: side view has world up on screen",
          np.allclose(up, [0, 0, 1], atol=1e-9), up)
    check("camera: side view sits on -Y", np.allclose(cam, [0, -1, 0], atol=1e-9),
          cam)

    _, _, _, cam_dn = gv.view_basis(0, -90)
    check("camera: el=-90 looks up from below",
          np.allclose(cam_dn, [0, 0, -1], atol=1e-12), cam_dn)


# ---------------------------------------------------------------------------
# 6. Rendering
# ---------------------------------------------------------------------------

def test_render():
    facets = synthetic_stone()
    scale = gv.world_scale(facets)
    expect = float(np.abs(np.vstack([f["verts"] for f in facets])).max())
    check("render: world_scale is the largest half-extent on any axis",
          near(scale, expect, 1e-12), (scale, expect))
    # it is the extent that matters, not the girdle radius: an 8-sided ring of
    # radius 1 never reaches x=1, and a tall crown can out-reach the girdle
    doubled = [dict(f, verts=np.asarray(f["verts"]) * 2.0) for f in facets]
    check("render: world_scale tracks the stone, not a fixed radius",
          near(gv.world_scale(doubled), 2 * scale, 1e-12),
          (gv.world_scale(doubled), scale))

    img = gv.render_view(facets, gv.view_basis(0, 90), scale, (0.2, 0.55, 0.9),
                         size=200, ss=2, labels=False)
    check("render: panel is square at the requested size", img.size == (200, 200),
          img.size)

    px = np.asarray(img).astype(int)
    check("render: something was actually drawn", px.max() > 40, px.max())
    check("render: the stone is centred, not clipped to a corner",
          px[100, 100].sum() > px[4, 4].sum())

    # back-face culling: from above, the pavilion points away and must not
    # paint over the crown.  Compare against a run where only the crown exists.
    crown_only = [f for f in facets if f["tier"] in ("C1", "T")]
    a = np.asarray(gv.render_view(facets, gv.view_basis(0, 90), scale,
                                  (0.2, 0.55, 0.9), size=200, ss=2, labels=False))
    b = np.asarray(gv.render_view(crown_only, gv.view_basis(0, 90), scale,
                                  (0.2, 0.55, 0.9), size=200, ss=2, labels=False))
    check("render: back faces are culled (pavilion invisible from the table)",
          int(np.abs(a.astype(int) - b.astype(int)).max()) == 0,
          int(np.abs(a.astype(int) - b.astype(int)).max()))

    # painter's algorithm: from the side the near girdle facet must win over
    # the far one.  Draw the same stone with the far facets removed; the
    # centre band of the image must be unchanged.
    grey = np.asarray(gv.render_view(facets, gv.view_basis(0, 90), scale,
                                     (0.2, 0.55, 0.9), size=200, ss=2,
                                     gray=True, labels=False)).astype(int)
    colour = a.astype(int)
    check("render: --gray drops the material tint",
          abs(int(grey[:, :, 0].sum()) - int(grey[:, :, 2].sum())) <
          abs(int(colour[:, :, 0].sum()) - int(colour[:, :, 2].sum())))

    # lighting: the light comes from the upper left, so on the side view the
    # left flank must out-shine the right
    side = np.asarray(gv.render_view(facets, gv.view_basis(0, 0), scale,
                                     (0.8, 0.8, 0.8), size=200, ss=2,
                                     labels=False)).astype(int)
    left = side[90:110, 40:80].sum()
    right = side[90:110, 120:160].sum()
    check("render: fixed light makes the left flank brighter", left > right,
          (left, right))

    # the light= override added 2026-07-13 must actually change the shading,
    # and its absence must leave the legacy result untouched
    lit = np.asarray(gv.render_view(facets, gv.view_basis(0, 0), scale,
                                    (0.8, 0.8, 0.8), size=200, ss=2,
                                    labels=False, light=(0.9, -0.2, 0.3)))
    same = np.asarray(gv.render_view(facets, gv.view_basis(0, 0), scale,
                                     (0.8, 0.8, 0.8), size=200, ss=2,
                                     labels=False, light=None))
    check("render: light= override changes the shading",
          int(np.abs(lit.astype(int) - side).max()) > 8)
    check("render: light=None is identical to the legacy path",
          int(np.abs(same.astype(int) - side).max()) == 0)

    check("render: no facets renders an empty panel, not a crash",
          gv.render_view([], gv.view_basis(0, 0), 1.0, (0.5, 0.5, 0.5),
                         size=64, ss=1).size == (64, 64))

    # a real preform - girdle and pavilion cut, no crown yet - has nothing
    # facing the table view at all, and four designs in the collection are
    # exactly that
    preform = [f for f in facets if f["tier"] in ("P1", "g1")]
    top = np.asarray(gv.render_view(preform, gv.view_basis(0, 90), scale,
                                    (0.8, 0.8, 0.8), size=200, ss=2,
                                    labels=False)).astype(int)
    ink = (np.abs(top - np.array([14, 14, 16])).max(axis=2) > 8).sum()
    check("render: a crownless preform's table view is annotated, not blank",
          0 < ink < 200 * 200 * 0.2, ink)

    labelled = np.asarray(gv.render_view(facets, gv.view_basis(0, 90), scale,
                                         (0.2, 0.55, 0.9), size=200, ss=2,
                                         labels=True)).astype(int)
    check("render: tier labels are drawn when asked",
          int(np.abs(labelled - colour).max()) > 0)


def _expected_shade(normal, base, cam_dir):
    """The colour render_view must produce for a facet, from its own model:
    ambient + lambert + a Blinn-Phong highlight, clipped to 8-bit."""
    n = np.asarray(normal, float)
    lgt = np.asarray(gv.LIGHT, float)
    half = lgt + np.asarray(cam_dir, float)
    half /= np.linalg.norm(half)
    lam = max(0.0, float(np.dot(n, lgt)))
    spec = gv.SPEC_K * (max(0.0, float(np.dot(n, half))) ** gv.SHININESS)
    rgb = np.asarray(base, float) * (gv.AMBIENT + gv.DIFFUSE * lam) + spec
    return np.clip(rgb * 255, 0, 255).astype(int)


def test_depth_order_and_culling():
    """Two facts a convex stone cannot prove on its own.

    A convex solid hides its own back faces, and its front faces tile the
    silhouette without overlapping - so on a real gem both the back-face cull
    and the painter's sort can be broken without changing a single pixel.
    These two scenes are built to be non-convex on purpose, so each of those
    defects has somewhere to show.
    """
    base = (0.8, 0.8, 0.8)
    cam = gv.view_basis(0, 90)[3]                 # straight down: (0, 0, 1)
    bg = np.array([14, 14, 16])

    # 1. a lone facet whose normal points away from the camera
    away = [{"verts": np.array([[-1., -1., 0.], [1., -1., 0.],
                                [1., 1., 0.], [-1., 1., 0.]]),
             "normal": np.array([0., 0., -1.]), "tier": "", "instr": "",
             "tid": 0}]
    # Rendered at the size the application uses.  render_view reserves a
    # fixed 46*ss pixel margin, so on a small panel the facet lands in a box
    # barely bigger than the notice and the two cannot be told apart.
    P = 460
    img = np.asarray(gv.render_view(away, gv.view_basis(0, 90), 1.0, base,
                                    size=P, ss=2, labels=False)).astype(int)
    # The facet must not be painted.  Sampled where the facet *would* be but
    # the notice is not - the notice is one short line across the middle, and
    # its antialiased edges pass through the very shade an unlit facet has,
    # so a colour test would report itself.
    band = img[60:100, :]
    check("cull: a back-facing facet paints nothing",
          int(np.abs(band - bg).max()) == 0, int(np.abs(band - bg).max()))
    lit = (np.abs(img - bg).max(axis=2) > 8).sum()
    check("cull: an empty view explains itself instead of going black",
          0 < lit < P * P * 0.1, lit)

    toward = [dict(away[0], normal=np.array([0., 0., 1.]))]
    img2 = np.asarray(gv.render_view(toward, gv.view_basis(0, 90), 1.0, base,
                                     size=P, ss=2, labels=False)).astype(int)
    check("cull: the same facet turned around does paint",
          int(np.abs(img2[80, 230] - bg).max()) > 20, img2[80, 230])

    # 2. a small facet floating above a larger tilted one.  Both face the
    #    camera, they overlap in plan, and their normals differ - so which one
    #    owns the centre pixel is decided purely by the draw order.
    far_v = np.array([[-1., -1., -0.3], [1., -1., 0.3],
                      [1., 1., 0.3], [-1., 1., -0.3]])
    far_n = np.cross(far_v[1] - far_v[0], far_v[2] - far_v[0])
    far_n = far_n / np.linalg.norm(far_n)
    if far_n[2] < 0:
        far_n = -far_n
    near_v = np.array([[-.4, -.4, 1.], [.4, -.4, 1.], [.4, .4, 1.],
                       [-.4, .4, 1.]])
    scene = [{"verts": far_v, "normal": far_n, "tier": "", "instr": "",
              "tid": 0},
             {"verts": near_v, "normal": np.array([0., 0., 1.]), "tier": "",
              "instr": "", "tid": 1}]

    got = np.asarray(gv.render_view(scene, gv.view_basis(0, 90), 1.0, base,
                                    size=120, ss=2,
                                    labels=False)).astype(int)[60, 60]
    want_near = _expected_shade([0., 0., 1.], base, cam)
    want_far = _expected_shade(far_n, base, cam)
    check("paint order: the two facets do shade differently",
          int(np.abs(want_near - want_far).max()) > 12,
          (want_near, want_far))
    check("paint order: the nearer facet owns the pixel they share",
          int(np.abs(got - want_near).max()) <= 2, (got, want_near, want_far))
    check("paint order: the farther facet does not",
          int(np.abs(got - want_far).max()) > 8, (got, want_far))


def test_footer():
    """The sheet carries no copyright line.  The viewer does not own what it
    draws, and it renders other people's designs as readily as your own."""
    text = gv._footer_text({"shape": "Round", "date": "2026-07-28",
                            "ri_min": "1.54", "ri_max": "1.55",
                            "title": "Someone Else's Stone",
                            "author": "Someone Else"})
    check("footer: no copyright notice", "copyright" not in text.lower(), text)
    check("footer: no name of the tool's author",
          "blankenship" not in text.lower(), text)
    check("footer: carries what the file says",
          "Round" in text and "2026-07-28" in text and "RI 1.54-1.55" in text,
          text)
    check("footer: a file that says nothing gets no footer",
          gv._footer_text({}) == "" and gv._footer_text(None) == "",
          repr(gv._footer_text({})))
    check("footer: a partial file gets only what it has",
          gv._footer_text({"shape": "Oval"}) == "Oval",
          gv._footer_text({"shape": "Oval"}))
    check("footer: a half-stated RI is not printed",
          gv._footer_text({"ri_min": "1.54"}) == "",
          gv._footer_text({"ri_min": "1.54"}))


def test_compose():
    facets = synthetic_stone()
    scale = gv.world_scale(facets)
    panels = gv.make_panels(facets, scale, (0.2, 0.55, 0.9), (35, 28),
                            size=160, ss=1, gray=False, labels=False)
    check("compose: three panels", len(panels) == 3)

    rows = gv.tier_table(facets, gear=96)
    instr = gv.render_instructions(rows, width=160 * 3 + 32)
    check("compose: instruction panel spans the three renders",
          instr.width == 160 * 3 + 32, instr.width)
    check("compose: instruction panel has height for every row",
          instr.height > len(rows) * 12, (instr.height, len(rows)))

    sheet = gv.compose(panels, {"title": "Synthetic"}, "synthetic.gcs", 160,
                       instr_img=instr)
    check("compose: sheet is wide enough for three panels",
          sheet.width >= 160 * 3, sheet.size)
    check("compose: sheet is taller with the table than without",
          sheet.height > gv.compose(panels, {}, "x.gcs", 160).height)

    empty = gv.render_instructions([], width=400)
    check("compose: an empty tier table renders a placeholder, not a crash",
          empty.size[0] == 400)


def test_folder_listing(tmp):
    """Walking a folder happens on every arrow press, twice, and on a
    996-design folder the stat calls cost more than the parse and render
    they were wrapping."""
    d = os.path.join(tmp, "folder")
    os.makedirs(d, exist_ok=True)
    names = ["gem10.gcs", "gem2.gcs", "gem1.gem", "notes.txt", "GEM3.GCS"]
    for n in names:
        with open(os.path.join(d, n), "w", encoding="utf-8") as fh:
            fh.write("x")
    os.makedirs(os.path.join(d, "sub.gcs"), exist_ok=True)   # a directory

    got = [os.path.basename(p) for p in
           gv.folder_designs(os.path.join(d, "gem1.gem"))]
    check("folder: natural sort, so gem2 precedes gem10",
          got == ["gem1.gem", "gem2.gcs", "GEM3.GCS", "gem10.gcs"], got)
    check("folder: other file types are ignored", "notes.txt" not in got)
    check("folder: a directory named like a design is not listed",
          "sub.gcs" not in got, got)

    again = gv.folder_designs(os.path.join(d, "gem1.gem"))
    check("folder: an unchanged folder is not re-scanned",
          again is gv.folder_designs(os.path.join(d, "gem2.gcs")))

    # the cache is keyed on the directory's mtime, which NTFS and POSIX both
    # bump when a file appears - so a design added while the viewer is open
    # still shows up
    import time as _t
    _t.sleep(0.01)
    with open(os.path.join(d, "gem4.gcs"), "w", encoding="utf-8") as fh:
        fh.write("x")
    fresh = [os.path.basename(p) for p in
             gv.folder_designs(os.path.join(d, "gem1.gem"))]
    check("folder: a design added afterwards is picked up",
          "gem4.gcs" in fresh, fresh)

    empty = os.path.join(tmp, "empty")
    os.makedirs(empty, exist_ok=True)
    lone = os.path.join(empty, "nothing.gcs")
    check("folder: an empty folder falls back to the file itself",
          gv.folder_designs(lone) == [lone], gv.folder_designs(lone))
    check("folder: a missing folder does not raise",
          gv.folder_designs(os.path.join(tmp, "nope", "x.gcs")) ==
          [os.path.join(tmp, "nope", "x.gcs")])


def test_instruction_cache():
    """The table is identical on every frame of a drag, and redrawing it is
    40% of a frame on an ordinary stone - two thirds of one on a 4,200-facet
    design.  The cache keys on what would be drawn, not on the file."""
    del gv._INSTR_CACHE[:]
    rows = gv.tier_table(synthetic_stone(), gear=96)
    a = gv.render_instructions_cached(rows, 800)
    b = gv.render_instructions_cached(gv.tier_table(synthetic_stone(), gear=96),
                                      800)
    check("cache: an identical table is not redrawn", a is b)

    c = gv.render_instructions_cached(rows, 900)
    check("cache: a different width is a different image", c is not a)
    d = gv.render_instructions_cached(rows, 800, gray=True)
    check("cache: grayscale is a different image", d is not a)

    changed = [dict(r) for r in rows]
    changed[0]["instr"] = "Something else entirely"
    e = gv.render_instructions_cached(changed, 800)
    check("cache: changed instructions redraw", e is not a)
    changed2 = [dict(r) for r in rows]
    changed2[0]["angle"] = rows[0]["angle"] + 0.01
    check("cache: a changed angle redraws",
          gv.render_instructions_cached(changed2, 800) is not a)

    check("cache: stays bounded", len(gv._INSTR_CACHE) <= 4,
          len(gv._INSTR_CACHE))
    for i in range(10):
        r2 = [dict(x) for x in rows]
        r2[0]["name"] = "T%d" % i
        gv.render_instructions_cached(r2, 800)
    check("cache: still bounded after ten different tables",
          len(gv._INSTR_CACHE) <= 4, len(gv._INSTR_CACHE))

    # what it returns must be what render_instructions would have drawn
    fresh = gv.render_instructions(rows, width=800)
    cached = gv.render_instructions_cached(rows, 800)
    check("cache: returns the same picture as drawing it directly",
          int(np.abs(np.asarray(fresh).astype(int) -
                     np.asarray(cached).astype(int)).max()) == 0)


def test_save_cli(tmp):
    """The --save path is what the exe runs headless, and what CI can check."""
    src = os.path.join(tmp, "synthetic.gcs")
    out = os.path.join(tmp, "sheet.png")
    rc = gv.main(["gcs_viewer.py", src, "--save", out])
    check("cli: --save exits 0", rc == 0, rc)
    check("cli: --save wrote a PNG", os.path.getsize(out) > 5000,
          os.path.getsize(out) if os.path.exists(out) else "missing")

    from PIL import Image
    with Image.open(out) as im:
        check("cli: PNG opens and is a sane size",
              im.width > 600 and im.height > 400, im.size)

    # A missing file normally pops a modal message box.  Unattended, that is a
    # hang, not an error - so the failure path is checked twice: once with the
    # dialog suppressed by the environment variable the viewer honours, and
    # once with _error_window replaced outright, which also proves it is the
    # only thing standing between a script and a stuck process.
    seen = []
    real, gv._error_window = gv._error_window, seen.append
    try:
        missing = gv.main(["gcs_viewer.py", os.path.join(tmp, "nope.gcs"),
                           "--save"])
    finally:
        gv._error_window = real
    check("cli: a missing file exits non-zero", missing == 1, missing)
    check("cli: the missing file is reported, not swallowed",
          any("nope.gcs" in s for s in seen), seen)

    os.environ["GCS_VIEWER_NO_GUI"] = "1"
    try:
        quiet = gv.main(["gcs_viewer.py", os.path.join(tmp, "nope.gcs"),
                         "--save"])
    finally:
        del os.environ["GCS_VIEWER_NO_GUI"]
    check("cli: GCS_VIEWER_NO_GUI keeps the error headless", quiet == 1, quiet)

    corrupt = os.path.join(tmp, "corrupt.gcs")
    with open(corrupt, "w", encoding="utf-8") as fh:
        fh.write("<GemCutStudio>this is not xml")
    os.environ["GCS_VIEWER_NO_GUI"] = "1"
    try:
        bad = gv.main(["gcs_viewer.py", corrupt, "--save"])
    finally:
        del os.environ["GCS_VIEWER_NO_GUI"]
    check("cli: a corrupt file exits non-zero instead of raising", bad == 1, bad)


def test_selftest(tmp):
    """The frozen exe runs exactly this to prove its bundle is complete."""
    report = os.path.join(tmp, "selftest.txt")
    rc = gv._selftest(report)
    check("selftest: exits 0", rc == 0, rc)
    with open(report, encoding="utf-8") as fh:
        text = fh.read()
    check("selftest: writes a report", "SELFTEST PASSED" in text, text[-200:])
    check("selftest: the report names the PNG it wrote", ".png" in text)


# ---------------------------------------------------------------------------

def main():
    print("gcs_viewer self-checks\n")
    with tempfile.TemporaryDirectory() as tmp:
        test_parse_gcs(tmp)
        test_parse_gcs_encodings(tmp)
        test_empty_files(tmp)
        test_parse_gcs_bad_normal(tmp)
        test_write_gcs_roundtrip(tmp)
        test_write_gcs_same_named_tiers(tmp)
        test_parse_gem(tmp)
        test_parse_gem_long_notes(tmp)
        test_parse_gem_no_trailing(tmp)
        test_load_design_dispatch(tmp)
        test_tier_table()
        test_tier_table_multi_instruction()
        test_view_basis()
        test_render()
        test_depth_order_and_culling()
        test_footer()
        test_compose()
        test_folder_listing(tmp)
        test_instruction_cache()
        test_save_cli(tmp)
        test_selftest(tmp)

    print("\n%d checks passed, %d failed" % (PASS, len(FAIL)))
    for f in FAIL:
        print("  FAILED: %s" % f)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
