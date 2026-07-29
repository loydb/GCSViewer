#!/usr/bin/env python
"""
GCS Viewer - render a Gemcut Studio (.gcs) faceted gem.

Author - Loyd Blankenship, but mostly Claude Code...

Shows three flat-shaded renders of the stone, tinted with the material
colour stored in the file:
  - "Table (top)" : looking straight down the optic axis at the table
  - "Side"        : the girdle profile
  - "3/4 view"    : drag to turn it left and right, arrow keys to tip it

Left/Right arrows step through the other .gcs files in the same folder
(wrapping around), like the Windows photo viewer.

Usage:
    pythonw gcs_viewer.py "path\\to\\stone.gcs"          # interactive window
    python  gcs_viewer.py "path\\to\\stone.gcs" --save [out.png]
    python  gcs_viewer.py --selftest [report.txt]        # prove a build works
    python  gcs_viewer.py --version                      # which build is this
    Options: --gray  (grayscale)   --no-labels  (hide tier names)

Set GCS_VIEWER_NO_GUI=1 to make errors print to stderr instead of opening a
message box, so unattended scripts cannot stall on a dialog.
"""

import sys
import os
import re
import math
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Bumped with the release tag; the release workflow refuses to publish a tag
# that disagrees with this.  A viewer handed out as a bare .exe has no other
# way to answer "which build is this?" - and this project has already shipped
# a binary four weeks behind its own source once.
__version__ = "1.0.22"

# ----------------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------------

_XML_DECL = re.compile(r"^\s*<\?xml[^>]*\?>")


def _read_xml(path):
    """Parse a .gcs into an element tree, tolerating what really turns up.

    Gem Cut Studio writes the file in the machine's own code page and does
    not declare an encoding, so a design whose title or author contains a
    non-ASCII character - "Fleur en reve", "Muller" - is not valid UTF-8 and
    a strict parse rejects the whole file.  Falling back through the usual
    Windows code pages recovers it; nothing else in the format is affected,
    because the geometry is all ASCII digits.
    """
    try:
        return ET.parse(path).getroot()
    except ET.ParseError:
        with open(path, "rb") as fh:
            data = fh.read()
        if not data.strip():
            raise ValueError("The file is empty (0 bytes).")
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                text = data.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
            # already decoded, so an encoding declaration would now be a lie
            # and ElementTree refuses to parse a str that carries one
            text = _XML_DECL.sub("", text, count=1)
            try:
                return ET.fromstring(text)
            except ET.ParseError:
                continue
        raise


def parse_gcs(path):
    """Return (facets, info, material).

    facets   : list of {'verts': Nx3 array, 'normal': 3-array, 'tier': str}
    info     : dict from the <info> element
    material : dict with 'color' (r,g,b in 0..1) and any render attributes
    """
    root = _read_xml(path)

    gear = 96.0
    iel = root.find("index")
    if iel is not None:
        try:
            gv = abs(float(iel.get("gear", "96")))
            if gv >= 1:
                gear = gv
        except (TypeError, ValueError):
            pass

    facets = []
    tid = 0
    for tier in root.iter("tier"):
        tname = tier.get("name", "")
        tinstr = tier.get("instructions", "") or ""
        for facet in tier.findall("facet"):
            verts = [[float(v.get("x")), float(v.get("y")), float(v.get("z"))]
                     for v in facet.findall("vertex")]
            if len(verts) < 3:
                continue
            verts = np.array(verts, dtype=float)
            try:
                n = np.array([float(facet.get("nx")), float(facet.get("ny")),
                              float(facet.get("nz"))], dtype=float)
                if not np.isfinite(n).all() or np.linalg.norm(n) < 1e-9:
                    raise ValueError
                n = n / np.linalg.norm(n)
            except (TypeError, ValueError):
                n = np.cross(verts[1] - verts[0], verts[2] - verts[0])
                nl = np.linalg.norm(n)
                n = n / nl if nl > 1e-12 else np.array([0.0, 0.0, 1.0])
            facets.append({"verts": verts, "normal": n, "tier": tname,
                           "instr": tinstr, "tid": tid})
        tid += 1

    # facets that live outside any <tier> (defensive)
    if not facets:
        for facet in root.iter("facet"):
            verts = [[float(v.get("x")), float(v.get("y")), float(v.get("z"))]
                     for v in facet.findall("vertex")]
            if len(verts) < 3:
                continue
            verts = np.array(verts, dtype=float)
            n = np.cross(verts[1] - verts[0], verts[2] - verts[0])
            nl = np.linalg.norm(n)
            n = n / nl if nl > 1e-12 else np.array([0.0, 0.0, 1.0])
            facets.append({"verts": verts, "normal": n, "tier": "",
                           "instr": "", "tid": 0})

    info = {}
    info_el = root.find("info")
    if info_el is not None:
        info = dict(info_el.attrib)
    info["gear"] = gear

    material = {"color": (0.85, 0.85, 0.85)}
    render_el = root.find("render")
    if render_el is not None:
        material.update(render_el.attrib)
        c = render_el.find("color")
        if c is not None:
            try:
                material["color"] = (max(0.0, min(1.0, float(c.get("r")))),
                                     max(0.0, min(1.0, float(c.get("g")))),
                                     max(0.0, min(1.0, float(c.get("b")))))
            except (TypeError, ValueError):
                pass
    return facets, info, material


# ----------------------------------------------------------------------------
# GemCad / Gem Cut Studio binary .gem parsing
# ----------------------------------------------------------------------------
#
# Layout (reverse-engineered): a header, then one record per facet:
#     [int32 flag][.NET 7-bit-len string "tierName\tinstructions"]
#     [vertex]*   each = [int32 flag (1)] + 3 little-endian float64 (x,y,z)
#     [normal]      one trailing group with flag 0  (we ignore it)
# Facets are delimited by the next facet's [int32][tab-string]; trailing
# strings after the last facet are the title/notes.  Vertex coordinates are
# the gcs coordinates scaled and Y-mirrored, so we un-mirror Y and recompute
# each face normal from its polygon (Newell) oriented outward.

import struct as _struct


def _newell(V):
    n = np.zeros(3)
    m = len(V)
    for i in range(m):
        a, b = V[i], V[(i + 1) % m]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    ln = np.linalg.norm(n)
    return n / ln if ln > 1e-12 else np.array([0.0, 0.0, 1.0])


def parse_gem(path):
    B = open(path, "rb").read()
    if not B:
        raise ValueError("The file is empty (0 bytes).")

    def str_at(p):
        if p < 0 or p >= len(B):
            return None
        L = B[p]
        if not (1 <= L < 128) or p + 1 + L > len(B):
            return None
        ch = B[p + 1:p + 1 + L]
        if all(c == 9 or 32 <= c < 127 for c in ch):   # tab or printable only
            try:
                return ch.decode("ascii")
            except UnicodeDecodeError:
                return None
        return None

    def is_facet(s):
        return s is not None and "\t" in s

    def facet_at(p):
        # p = a facet's leading int32 flag, then a "name\tinstr" string, then
        # a valid vertex group.  The trailing group test rejects tab-strings
        # that merely appear inside vertex byte data.
        if not (0 <= p and p + 5 < len(B)):
            return False
        if not is_facet(str_at(p + 4)):
            return False
        a = p + 5 + B[p + 4]                  # past flag(4) + lenbyte(1) + chars
        if a + 28 > len(B):
            return True                       # last facet, no following group
        if _struct.unpack_from("<i", B, a)[0] not in (0, 1):
            return False
        d = _struct.unpack_from("<3d", B, a + 4)
        return all(math.isfinite(v) and abs(v) < 1e4 for v in d)

    # locate the first facet
    S = 0
    while S < len(B) and not facet_at(S):
        S += 1
    if S >= len(B):
        raise ValueError("No facets found in .gem file.")

    pos = S
    raw, prev = [], ""
    while facet_at(pos):
        s = str_at(pos + 4)
        pos += 4                              # facet flag int32
        pos += 1 + B[pos]                     # the "name\tinstr" string
        parts = s.split("\t", 1)
        name = parts[0] or prev
        instr = parts[1] if len(parts) > 1 else ""
        prev = name
        verts = []
        while pos + 28 <= len(B):
            if facet_at(pos):                 # next facet begins
                break
            flag = _struct.unpack_from("<i", B, pos)[0]
            if flag not in (0, 1):
                break
            d = _struct.unpack_from("<3d", B, pos + 4)
            if not all(math.isfinite(v) and abs(v) < 1e4 for v in d):
                break
            if flag == 1:                     # flag-0 group is the stored normal
                verts.append(d)
            pos += 28
        if len(verts) >= 3:
            raw.append((name, instr, verts))
    if not raw:
        raise ValueError("No facets parsed from .gem file.")

    # trailing strings after the last facet: title, designer line, notes...
    # (.NET 7-bit varint length prefix - long notes exceed 127 chars)
    def varint_str(p):
        L, shift, q = 0, 0, p
        while q < len(B):
            b = B[q]; q += 1
            L |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
            if shift > 21:
                return None, p
        if L < 1 or L > 4000 or q + L > len(B):
            return None, p
        ch = B[q:q + L]
        if not all(c in (9, 10, 13) or 32 <= c < 127 for c in ch):
            return None, p
        return ch.decode("ascii", "replace"), q + L
    # The exact gap between the last vertex group and the strings varies, so
    # try every start offset and keep the chain that parses the most strings.
    def chain_at(p):
        out = []
        while p < len(B):
            s, p2 = varint_str(p)
            if s is None:
                break
            out.append(s); p = p2
        return out
    trailing = []
    for start in range(pos, len(B)):
        c = chain_at(start)
        if len(c) > len(trailing):
            trailing = c
    info = {}
    if trailing:
        info["title"] = trailing[0].strip()
        if len(trailing) > 1:
            info["notes"] = " / ".join(t.strip() for t in trailing[1:] if t.strip())

    allv = np.array([v for _, _, vs in raw for v in vs]) * np.array([1.0, -1.0, 1.0])
    center = allv.mean(axis=0)
    facets = []
    tid, prev_name = -1, None
    for name, instr, vs in raw:
        if name != prev_name:
            tid += 1
            prev_name = name
        V = np.array(vs) * np.array([1.0, -1.0, 1.0])
        n = _newell(V)
        if np.dot(n, V.mean(axis=0) - center) < 0:
            n = -n
        facets.append({"verts": V, "normal": n, "tier": name,
                       "instr": instr, "tid": tid})

    # .gem doesn't reliably store a display colour -> neutral pale stone
    return facets, info, {"color": (0.82, 0.82, 0.86)}


def load_design(path):
    """Parse a .gcs or .gem file -> (facets, info, material)."""
    if os.path.splitext(path)[1].lower() == ".gem":
        return parse_gem(path)
    return parse_gcs(path)


def write_gcs(path, facets, info, material, gear=96):
    """Serialize parsed facets to Gem Cut Studio .gcs XML."""
    import xml.etree.ElementTree as ET

    def fmt(x):
        return repr(float(x))

    try:
        gear_s = str(int(round(float(gear)))) if float(gear) >= 1 else "96"
    except (TypeError, ValueError):
        gear_s = "96"

    root = ET.Element("GemCutStudio", version="1000")
    ET.SubElement(root, "index", gear=gear_s, base="0", symmetry="0", mirror="0")

    # Tiers are delimited by consecutive facets sharing a tier name.  That is
    # wrong for the handful of designs that give two different <tier> elements
    # the same name - four of the 8,128 files in the reference collection do,
    # and one of them rewrote seven tiers as one.  Where the facets carry the
    # tid parse_gcs assigns per element, that is the better key.
    #
    # It is only adopted when it produces MORE tiers than the names do, so
    # this can split a tier that should never have been merged and can never
    # merge two that belong apart.  Callers that build facets without a tid -
    # every solver script that writes through here does - are unaffected.
    def runs(key):
        out, prev = [], object()
        for f in facets:
            k = key(f)
            if k != prev:
                out.append(0)
                prev = k
            out[-1] += 1
        return out

    by_name = runs(lambda f: f.get("tier", "") or "")
    boundaries = by_name
    if all("tid" in f for f in facets):
        by_tid = runs(lambda f: (f["tid"], f.get("tier", "") or ""))
        if len(by_tid) > len(by_name):
            boundaries = by_tid

    i = 0
    for run_len in boundaries:
        tier = facets[i].get("tier", "") or ""
        # Every distinct step in the tier, not just the one the tier opens
        # with.  A .gem puts the instruction on the facet that *begins* a
        # cutting step and a tier can hold several, so taking facets[i] alone
        # dropped later steps on conversion - 332 of the .gem files in the
        # reference collection lost at least one.  Repeats collapse, so a
        # .gcs (one instruction repeated across its tier) is unchanged.
        steps = []
        for f in facets[i:i + run_len]:
            s = (f.get("instr", "") or "").strip()
            if s and s not in steps:
                steps.append(s)
        instr = " · ".join(steps)
        # Tier angle/depth tell Gem Cut Studio which section a tier belongs to:
        #   angle > 90 -> Pavilion (normal points down), < 90 -> Crown,
        #   == 90 -> Girdle, 0 -> Table.  angle = arccos(nz); depth = |v . n|.
        n0 = np.asarray(facets[i]["normal"], float)
        ln = np.linalg.norm(n0)
        nz = n0[2] / ln if ln > 1e-12 else 0.0
        t_angle = math.degrees(math.acos(max(-1.0, min(1.0, nz))))
        v0 = np.asarray(facets[i]["verts"][0], float)
        t_depth = abs(float(v0 @ (n0 / ln))) if ln > 1e-12 else 0.0
        te = ET.SubElement(root, "tier", angle=repr(t_angle), depth=repr(t_depth),
                           name=tier, instructions=instr, visible="true",
                           guide="false")
        for _ in range(run_len):
            f = facets[i]
            n = f["normal"]
            fe = ET.SubElement(te, "facet", nx=fmt(n[0]), ny=fmt(n[1]),
                               nz=fmt(n[2]), index_angle="0")
            for v in f["verts"]:
                ET.SubElement(fe, "vertex", x=fmt(v[0]), y=fmt(v[1]), z=fmt(v[2]))
            i += 1

    c = material.get("color", (0.82, 0.82, 0.86))
    rnd = ET.SubElement(root, "render", material="(converted from GemCad)",
                        refractive_index="1.76", dispersion="0", clarity="95",
                        density="1", lighting_model="Random")
    ET.SubElement(rnd, "color", r=fmt(c[0]), g=fmt(c[1]), b=fmt(c[2]))
    title = (info.get("title") if info else None) or \
        os.path.splitext(os.path.basename(path))[0]
    ET.SubElement(root, "info", title=title, author="", date="")

    ET.indent(root)
    # Written through a file opened here rather than by handing ElementTree a
    # path.  Given a path with encoding="unicode" it opens the file itself,
    # in text mode with the machine's locale encoding: newlines come out CRLF
    # on Windows and LF elsewhere, so the same stone converts to different
    # bytes on different machines, and a title outside the local code page
    # raises rather than being written.  The reader already falls back
    # through the code pages for files other programs wrote (see _read_xml);
    # what this program writes is simply UTF-8 with LF, everywhere.
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        ET.ElementTree(root).write(fh, encoding="unicode",
                                   xml_declaration=False)


# ----------------------------------------------------------------------------
# Geometry / shading
# ----------------------------------------------------------------------------

LIGHT = np.array([-0.45, -0.35, 0.82])
LIGHT = LIGHT / np.linalg.norm(LIGHT)
AMBIENT = 0.20
DIFFUSE = 0.80
SPEC_K = 0.55
SHININESS = 26.0


def view_basis(az_deg, el_deg):
    """Return (right, up, forward, cam_dir) for a camera orbiting the origin.

    az=0, el=0  -> side view (camera on -Y looking toward +Y)
    el=90       -> top view  (camera above, looking down -Z)
    """
    a = math.radians(az_deg)
    e = math.radians(el_deg)
    cam_dir = np.array([math.cos(e) * math.sin(a),
                        -math.cos(e) * math.cos(a),
                        math.sin(e)])            # origin -> camera
    forward = -cam_dir                           # into the scene
    up_world = np.array([0.0, 0.0, 1.0])
    right = np.cross(forward, up_world)
    if np.linalg.norm(right) < 1e-6:             # looking straight down/up
        # az rotates the straight-down/up view in-plane (az=0 keeps the
        # legacy orientation; az=180 gives the BOOK convention with gear
        # index 0 at the bottom -- Loyd validation feedback 2026-07-14)
        ca, sa = math.cos(a), math.sin(a)
        right = np.array([ca, sa, 0.0])
        up = np.array([-sa, ca, 0.0]) * (1 if el_deg > 0 else -1)
    else:
        right = right / np.linalg.norm(right)
        up = np.cross(right, forward)
        up = up / np.linalg.norm(up)
    return right, up, forward, cam_dir


def world_scale(facets):
    allv = np.vstack([f["verts"] for f in facets])
    half = np.max(np.abs(allv), axis=0)
    return float(max(half))


def _poly_area(px, py):
    return 0.5 * abs(np.dot(px, np.roll(py, -1)) - np.dot(py, np.roll(px, -1)))


def _load_font(px):
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default()


# ----------------------------------------------------------------------------
# Rendering one panel
# ----------------------------------------------------------------------------

def render_view(facets, basis, scale, color, size=620, ss=2,
                gray=False, labels=True, light=None):
    """Render one orthographic, flat-shaded panel as an RGB PIL image.
    light: optional unit vector overriding the global LIGHT -- pass an
    angled headlight (cam_dir tilted) so bottom/side views read as well
    as the top (Loyd validation feedback 2026-07-14)."""
    right, up, forward, cam_dir = basis
    base_col = np.array((0.82, 0.82, 0.82) if gray else color, dtype=float)

    S = size * ss
    M = int(46 * ss)
    draw_extent = S - 2 * M
    px_per_unit = draw_extent / (2.0 * scale * 1.05)

    bg = (14, 14, 16)
    img = Image.new("RGB", (S, S), bg)
    d = ImageDraw.Draw(img)

    lgt = LIGHT if light is None else \
        np.asarray(light, float) / np.linalg.norm(light)
    halfway = lgt + cam_dir
    halfway = halfway / np.linalg.norm(halfway)

    drawables = []
    for f in facets:
        n = f["normal"]
        if float(np.dot(n, forward)) >= -1e-6:     # back-facing -> skip
            continue
        verts = f["verts"]
        sx = verts @ right
        sy = verts @ up
        depth = float(np.mean(verts @ forward))

        lam = max(0.0, float(np.dot(n, lgt)))
        spec = SPEC_K * (max(0.0, float(np.dot(n, halfway))) ** SHININESS)
        rgb = base_col * (AMBIENT + DIFFUSE * lam) + spec
        rgb = tuple(int(np.clip(c * 255, 0, 255)) for c in rgb)
        drawables.append((depth, sx, sy, rgb, f["tier"]))

    if not drawables:
        # Not necessarily a fault.  A preform is cut girdle-first and has no
        # crown yet, so from straight above nothing faces the camera and the
        # panel is legitimately empty - four designs in the reference
        # collection are exactly this.  Say so, rather than showing a black
        # square that reads as a broken viewer.
        d.text((S / 2, S / 2), "no facets face this view",
               fill=(120, 120, 128), font=_load_font(int(15 * ss)),
               anchor="mm")
        return img.resize((size, size), Image.LANCZOS)

    allx = np.concatenate([t[1] for t in drawables])
    ally = np.concatenate([t[2] for t in drawables])
    cx = 0.5 * (allx.min() + allx.max())
    cy = 0.5 * (ally.min() + ally.max())

    def to_px(sx, sy):
        px = S / 2 + (sx - cx) * px_per_unit
        py = S / 2 - (sy - cy) * px_per_unit
        return px, py

    drawables.sort(key=lambda t: -t[0])            # farthest first
    edge = max(1, int(round(1.1 * ss)))

    # facet whose name we will print: largest visible facet per tier
    best = {}   # tier -> (area, cx_px, cy_px)
    for _, sx, sy, rgb, tier in drawables:
        px, py = to_px(sx, sy)
        d.polygon(list(zip(px.tolist(), py.tolist())), fill=rgb,
                  outline=tuple(max(0, c - 70) for c in rgb), width=edge)
        if labels and tier:
            area = _poly_area(px, py)
            if tier not in best or area > best[tier][0]:
                best[tier] = (area, float(px.mean()), float(py.mean()))

    if labels and best:
        font = _load_font(int(17 * ss))
        for tier, (_, lx, ly) in best.items():
            d.text((lx, ly), tier, fill=(245, 245, 245), font=font,
                   anchor="mm", stroke_width=max(1, int(2 * ss)),
                   stroke_fill=(0, 0, 0))

    return img.resize((size, size), Image.LANCZOS)


# ----------------------------------------------------------------------------
# Composite of the three panels
# ----------------------------------------------------------------------------

PANEL_LABELS = ("Table (top)", "Side", "3/4 view")


def _footer_text(info):
    """The line under the sheet: what the file itself says about the design.

    It carries no copyright notice.  The viewer does not own what it draws -
    a rendered sheet belongs to whoever cut or designed the stone - so it
    puts nothing of its own on the page.  A file that states none of these
    gets no footer at all rather than an empty rule.

    The notes come last and are usually the whole line, because a .gem is
    where they come from and a .gem states none of the rest.  They were being
    read out of the file and then thrown away: the designer's own account of
    the stone - what it is for, what material suits it, where the rest of
    their work lives - parsed and never shown.
    """
    info = info or {}
    parts = [info.get("shape", ""), info.get("date", "")]
    ri_min, ri_max = info.get("ri_min"), info.get("ri_max")
    if ri_min and ri_max:
        parts.append("RI %s-%s" % (ri_min, ri_max))
    notes = (info.get("notes") or "").strip()
    if notes:
        parts.append(notes)
    return "   |   ".join(str(p) for p in parts if p)


_FIT_CACHE = {}


def _fit_text(font, text, maxw, keep=8):
    """Trim `text` until it fits `maxw`, with an ellipsis if anything went.

    Memoised: the footer is redrawn on every frame of a drag, and a .gem note
    block runs to a few hundred characters, so the trimming loop would run
    per frame on exactly the files that need it.
    """
    key = (id(font), text, int(maxw))
    hit = _FIT_CACHE.get(key)
    if hit is not None:
        return hit
    out = text
    if font.getlength(out) > maxw:
        while out and font.getlength(out + "…") > maxw:
            out = out[:-1]
        out = out.rstrip(" ,;/-") + "…"
    _FIT_CACHE[key] = out
    if len(_FIT_CACHE) > keep:
        for k in list(_FIT_CACHE)[:-keep]:
            del _FIT_CACHE[k]
    return out


def make_panels(facets, scale, color, angles34, size, ss, gray, labels):
    bases = [view_basis(0, 90), view_basis(0, 0), view_basis(*angles34)]
    return [render_view(facets, b, scale, color, size=size, ss=ss,
                        gray=gray, labels=labels) for b in bases]


# ----------------------------------------------------------------------------
# Instructions / cutting-sequence table  (mirrors the Gem Cut Studio panel)
# ----------------------------------------------------------------------------

# section band -> (band bg, band text).  Both sections use burnt orange.
_SECTION_BAND = (191, 87, 0)          # #BF5700
_SECTION_TEXT = (245, 245, 245)
_SECTION_STYLE = {
    "Pavilion": (_SECTION_BAND, _SECTION_TEXT),
    "Crown":    (_SECTION_BAND, _SECTION_TEXT),
}


def tier_table(facets, gear=96.0):
    """Group facets into tiers and derive the cutting-sequence rows:
    name, faceting angle, section (Pavilion/Crown), index list, instruction.

    Angle, section and indices are derived from geometry (so they appear for
    every file); the instruction text is whatever the file stored per tier."""
    try:
        gear = float(gear) or 96.0
    except (TypeError, ValueError):
        gear = 96.0
    gi = int(round(gear))

    groups = []
    for f in facets:
        key = f.get("tid", f.get("tier", ""))
        if not groups or key != groups[-1][0]:
            groups.append((key, []))
        groups[-1][1].append(f)

    rows = []
    for _, grp in groups:
        nz = float(max(-1.0, min(1.0, grp[0]["normal"][2])))
        angle = math.degrees(math.acos(min(1.0, abs(nz))))
        section = "Pavilion" if nz < 1e-3 else "Crown"   # girdle->Pav, table->Crown
        idxs = []
        for f in grp:
            nx, ny = float(f["normal"][0]), float(f["normal"][1])
            if math.hypot(nx, ny) < 1e-6:
                continue
            ang = math.atan2(nx, ny) % (2 * math.pi)
            idxs.append(int(round(ang / (2 * math.pi) * gear)) % gi)
        idxs = sorted(set(idxs))
        if idxs:
            idx_str = "-".join("%02d" % k for k in idxs)
        else:
            idx_str = "Table" if angle < 1.0 else ""
        # A .gem stores the instruction on the facet that starts a cutting
        # step, and a tier can contain several steps - "Match g1, establish
        # upper girdle line" and then "Meet g1.a.a.g1" both live in tier a of
        # Alcyone.  Taking only the first facet's text dropped 144 lines
        # across 56 of the 245 .gem files in the collection.  Order is
        # preserved and repeats collapse, so a .gcs - which repeats one tier
        # instruction across every facet - is unaffected.
        instrs = []
        for f in grp:
            s = (f.get("instr", "") or "").strip()
            if s and s not in instrs:
                instrs.append(s)
        rows.append({"name": str(grp[0].get("tier", "") or ""), "angle": angle,
                     "section": section, "index": idx_str,
                     "instr": " · ".join(instrs)})
    return rows


def render_instructions(rows, width=1412, gray=False):
    """Draw the tier table as a wide PIL panel (placed below the renders),
    styled like Gem Cut Studio. Height is sized to the content."""
    W = int(width)
    margin = 6

    # group consecutive rows into section runs (Pavilion / Crown)
    secs = []
    for r in rows:
        if not secs or secs[-1][0] != r["section"]:
            secs.append((r["section"], []))
        secs[-1][1].append(r)
    total = sum(1 + len(g) for _, g in secs) or 1
    gap = 14                                     # blank space before each new section
    n_gaps = max(0, len(secs) - 1)

    row_h = min(26, max(15, 540 // total))      # bound total height ~540px
    H = total * row_h + n_gaps * gap + 2 * margin
    img = Image.new("RGB", (W, H), (22, 22, 26))
    d = ImageDraw.Draw(img)
    if not rows:
        d.text((10, 10), "(no tier data)", fill=(150, 150, 155),
               font=_load_font(15))
        return img

    fs = max(11, int(row_h * 0.56))
    font = _load_font(fs)

    x_name = margin + 4
    x_ang = x_name + int(0.05 * W)
    x_idx = x_ang + int(0.06 * W)
    x_com = x_idx + int(0.42 * W)
    idx_maxw = x_com - x_idx - 12
    com_maxw = W - x_com - 8

    def fit_idx(s):
        if font.getlength(s) <= idx_maxw:
            return s
        parts = s.split("-")
        out = parts[0]
        for p in parts[1:]:
            if font.getlength(out + "-" + p + "+") > idx_maxw:
                return out + "+"
            out += "-" + p
        return out

    def fit_txt(s):
        if font.getlength(s) <= com_maxw:
            return s
        while s and font.getlength(s + "…") > com_maxw:
            s = s[:-1]
        return s + "…"

    y = margin
    for si, (sec, grp) in enumerate(secs):
        if si > 0:
            y += gap                             # space between sections
        bg, fg = _SECTION_STYLE.get(sec, (_SECTION_BAND, _SECTION_TEXT))
        d.rectangle([0, y, W, y + row_h], fill=bg)
        d.text((x_name, y + row_h * 0.5), sec, fill=fg, font=font, anchor="lm")
        y += row_h
        for i, r in enumerate(grp):
            if i % 2:
                d.rectangle([0, y, W, y + row_h], fill=(31, 31, 36))
            cy = y + row_h * 0.5
            d.text((x_name, cy), r["name"][:8], fill=(226, 226, 230),
                   font=font, anchor="lm")
            d.text((x_ang, cy), "%.2f°" % r["angle"], fill=(202, 202, 150),
                   font=font, anchor="lm")
            d.text((x_idx, cy), fit_idx(r["index"]), fill=(176, 200, 222),
                   font=font, anchor="lm")
            if r["instr"]:
                d.text((x_com, cy), fit_txt(r["instr"]), fill=(206, 206, 212),
                       font=font, anchor="lm")
            y += row_h
    return img


_INSTR_CACHE = []          # [(key, image)], most recent last


def render_instructions_cached(rows, width, gray=False, keep=4):
    """render_instructions, memoised on what it draws.

    The table is redrawn on every frame of a drag even though nothing in it
    changes - it costs about 40% of a frame on an ordinary stone, and two
    thirds of one on the heaviest design in the reference collection (4,200
    facets, hundreds of tier rows, 167 ms of a 249 ms frame).  Keying on the
    row contents rather than on the file means a redundant redraw is caught
    however the caller arrived at it.

    A handful of entries are kept, so arrowing back and forth between two
    designs stays warm without the cache growing with the folder.
    """
    key = (int(width), bool(gray),
           tuple((r["name"], round(float(r["angle"]), 6), r["section"],
                  r["index"], r["instr"]) for r in rows))
    for k, img in _INSTR_CACHE:
        if k == key:
            return img
    img = render_instructions(rows, width=width, gray=gray)
    _INSTR_CACHE.append((key, img))
    del _INSTR_CACHE[:-keep]
    return img


def compose(panels, info, src_name, panel, instr_img=None,
            pad=16, header=54, footer=30):
    n = len(panels)
    W = panel * n + pad * (n + 1)
    py = header + pad + 14                      # top of the render panels
    instr_top = py + panel + pad + 34           # clearance for the "Instructions" label
    if instr_img is not None:
        H = instr_top + instr_img.height + pad + footer
    else:
        H = py + panel + pad + footer
    canvas = Image.new("RGB", (W, H), (26, 26, 30))
    d = ImageDraw.Draw(canvas)

    title_font = _load_font(26)
    label_font = _load_font(20)
    small_font = _load_font(15)

    title = info.get("title") or os.path.splitext(os.path.basename(src_name))[0]
    author = info.get("author", "")
    head = title if not author else f"{title}    —  {author}"
    d.text((pad, 12), head, fill=(235, 235, 235), font=title_font)

    y0 = header
    for i, p in enumerate(panels):
        x = pad + i * (panel + pad)
        canvas.paste(p, (x, py))
        d.text((x + 6, y0 - 2), PANEL_LABELS[i], fill=(205, 205, 210),
               font=label_font)

    if instr_img is not None:
        d.text((pad + 6, py + panel + pad + 2), "Instructions",
               fill=(205, 205, 210), font=label_font)
        canvas.paste(instr_img, (pad, instr_top))

    text = _footer_text(info)
    if text:
        d.text((pad, H - footer + 4), _fit_text(small_font, text, W - 2 * pad),
               fill=(165, 165, 170), font=small_font)
    return canvas


# ----------------------------------------------------------------------------
# Interactive window
# ----------------------------------------------------------------------------

_FOLDER_CACHE = {}         # normcased folder -> (mtime_ns, [paths])


def natural_key(p):
    """Explorer's sort: gem2 before gem10."""
    name = os.path.basename(p).lower()
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]


def folder_designs(path, keep=8):
    """Every design file beside `path`, in Explorer's order.

    Called on each arrow press, and twice per press before this was hoisted
    out of the viewer - once to step the file and once to write the position
    into the status line.  On a 996-design folder that was 52 ms of stat calls
    per keystroke, more than the parse and render it was wrapping.

    scandir carries the directory entry's own type, so no separate stat per
    file is needed, and the result is cached against the directory's
    modification time - which NTFS bumps when a file is added, removed or
    renamed, so adding a design while the viewer is open still shows up.
    """
    folder = os.path.dirname(path) or "."
    key = os.path.normcase(folder)
    try:
        stamp = os.stat(folder).st_mtime_ns
    except OSError:
        return [path]

    hit = _FOLDER_CACHE.get(key)
    if hit is not None and hit[0] == stamp:
        return hit[1]

    try:
        files = [e.path for e in os.scandir(folder)
                 if e.name.lower().endswith((".gcs", ".gem")) and e.is_file()]
    except OSError:
        return [path]
    files.sort(key=natural_key)
    files = files or [path]

    _FOLDER_CACHE[key] = (stamp, files)
    if len(_FOLDER_CACHE) > keep:
        for k in list(_FOLDER_CACHE)[:-keep]:
            del _FOLDER_CACHE[k]
    return files


class ViewerApp:
    def __init__(self, path, gray=False, labels=True):
        import tkinter as tk
        from PIL import ImageTk
        self.tk = tk
        self.ImageTk = ImageTk

        self.gray = gray
        self.labels = labels
        self.show_instr = True
        self.az, self.el = 35.0, 28.0

        self.panel = 460          # on-screen panel size
        self.ss_static = 2        # quality for top/side and idle 3/4
        self.ss_drag = 1          # quality while dragging

        # load the first stone (raises on failure - caught by caller)
        self._load_data(path)

        self.root = tk.Tk()
        self.root.title(f"Gem Viewer {__version__}  -  "
                        f"{os.path.basename(self.path)}")
        self.root.configure(bg="#1a1a1e")
        self.label = tk.Label(self.root, bg="#1a1a1e")
        self.label.pack()
        self.status = tk.Label(self.root, bg="#1a1a1e", fg="#9a9aa2",
                               font=("Segoe UI", 10), pady=4)
        self.status.pack(fill="x")

        self._render_static()
        self._render_dynamic(self.ss_static)
        self._composite_and_show()
        self._set_status()

        self.label.bind("<Button-1>", self._press)
        self.label.bind("<B1-Motion>", self._drag)
        self.label.bind("<ButtonRelease-1>", self._release)
        self.root.bind("<Left>",  lambda e: self._step_file(-1))
        self.root.bind("<Right>", lambda e: self._step_file(1))
        self.root.bind("<Up>",    lambda e: self._nudge(0, 6))
        self.root.bind("<Down>",  lambda e: self._nudge(0, -6))
        self.root.bind("<Prior>", lambda e: self._step_file(-1))  # PageUp
        self.root.bind("<Next>",  lambda e: self._step_file(1))   # PageDown
        self.root.bind("g", lambda e: self._toggle("gray"))
        self.root.bind("l", lambda e: self._toggle("labels"))
        self.root.bind("i", lambda e: self._toggle_instr())
        self.root.bind("s", lambda e: self._save())
        self.root.bind("r", lambda e: self._reset())
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("q", lambda e: self.root.destroy())

        self.root.update_idletasks()
        self._center()

    # -- data loading / folder navigation --
    def _load_data(self, path):
        facets, info, material = load_design(path)
        if not facets:
            raise ValueError("No facets found in file.")
        self.path = os.path.abspath(path)
        self.facets = facets
        self.info = info
        self.color = material["color"]
        self.scale = world_scale(facets)

    _natural_key = staticmethod(natural_key)

    def _siblings(self):
        """All .gcs / .gem files in the current folder, Explorer-sorted."""
        return folder_designs(self.path)

    def _step_file(self, direction):
        files = self._siblings()
        n = len(files)
        cur = os.path.normcase(self.path)
        idx = next((i for i, f in enumerate(files)
                    if os.path.normcase(os.path.abspath(f)) == cur), 0)
        if n <= 1:
            self._set_status("Only one .gcs file in this folder")
            return
        # advance with wrap-around, skipping any unreadable files
        for k in range(1, n + 1):
            cand = files[(idx + direction * k) % n]
            try:
                self._load_data(cand)
                break
            except Exception:
                continue
        else:
            self._set_status("No readable .gcs files in this folder")
            return
        self.root.title(f"Gem Viewer {__version__}  -  "
                        f"{os.path.basename(self.path)}")
        self._render_static()
        self._render_dynamic(self.ss_static)
        self._composite_and_show()
        self._set_status()

    # -- rendering helpers --
    def _render_static(self):
        self.p_top = render_view(self.facets, view_basis(0, 90), self.scale,
                                 self.color, self.panel, self.ss_static,
                                 self.gray, self.labels)
        self.p_side = render_view(self.facets, view_basis(0, 0), self.scale,
                                  self.color, self.panel, self.ss_static,
                                  self.gray, self.labels)

    def _render_dynamic(self, ss):
        self.p_34 = render_view(self.facets, view_basis(self.az, self.el),
                                self.scale, self.color, self.panel, ss,
                                self.gray, self.labels)

    def _composite_and_show(self):
        instr_img = None
        if getattr(self, "show_instr", True):
            rows = tier_table(self.facets, gear=self.info.get("gear", 96.0))
            instr_img = render_instructions_cached(rows, self.panel * 3 + 32,
                                                   gray=self.gray)
        canvas = compose([self.p_top, self.p_side, self.p_34],
                         self.info, self.path, self.panel, instr_img=instr_img)
        self._canvas = canvas
        photo = self.ImageTk.PhotoImage(canvas)
        self.label.configure(image=photo)
        self.label.image = photo

    def _set_status(self, message=None):
        if message is None:
            files = self._siblings()
            cur = os.path.normcase(self.path)
            idx = next((i for i, f in enumerate(files)
                        if os.path.normcase(os.path.abspath(f)) == cur), 0)
            pos = f"file {idx + 1} / {len(files)}"
            message = (f"{pos}   ← → prev / next file   •   "
                       "drag to spin   •   ↑ ↓ tilt   •   "
                       "I instructions   G gray   L labels   S save   R reset   Esc quit")
        self.status.configure(text=message)

    # -- event handlers --
    def _press(self, e):
        self._lx, self._ly = e.x, e.y

    def _drag(self, e):
        dx, dy = e.x - self._lx, e.y - self._ly
        self._lx, self._ly = e.x, e.y
        self.az = (self.az + dx * 0.6) % 360
        self.el = max(-88.0, min(88.0, self.el + dy * 0.6))
        self._render_dynamic(self.ss_drag)
        self._composite_and_show()

    def _release(self, e):
        self._render_dynamic(self.ss_static)
        self._composite_and_show()

    def _nudge(self, daz, dele):
        self.az = (self.az + daz) % 360
        self.el = max(-88.0, min(88.0, self.el + dele))
        self._render_dynamic(self.ss_static)
        self._composite_and_show()

    def _toggle(self, what):
        setattr(self, what, not getattr(self, what))
        self._render_static()
        self._render_dynamic(self.ss_static)
        self._composite_and_show()

    def _toggle_instr(self):
        # only the composite changes (no re-render); window width changes
        self.show_instr = not self.show_instr
        self._composite_and_show()
        self.root.update_idletasks()
        self._center()

    def _reset(self):
        self.az, self.el = 35.0, 28.0
        self._render_dynamic(self.ss_static)
        self._composite_and_show()

    def _save(self):
        out = os.path.splitext(self.path)[0] + "_views.png"
        panels = make_panels(self.facets, self.scale, self.color,
                             (self.az, self.el), size=680, ss=3,
                             gray=self.gray, labels=self.labels)
        instr_img = None
        if self.show_instr:
            rows = tier_table(self.facets, gear=self.info.get("gear", 96.0))
            instr_img = render_instructions(rows, width=680 * 3 + 32,
                                            gray=self.gray)
        compose(panels, self.info, self.path, 680, instr_img=instr_img).save(out)
        self._set_status(f"Saved  {out}")

    def _center(self):
        w, h = self._canvas.size
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2 - 30
        self.root.geometry(f"+{max(0, x)}+{max(0, y)}")

    def run(self):
        self.root.mainloop()


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------

def version_string():
    """What build this is, and whether it is the frozen one or the source.

    Reported by --version and written into the window title, because the
    usual way to be wrong about a viewer's behaviour is to be looking at an
    executable older than the .py you are reading.
    """
    kind = "exe" if getattr(sys, "frozen", False) else "source"
    return "GCS Viewer %s (%s, Python %d.%d.%d)" % (
        __version__, kind, *sys.version_info[:3])


def _attach_console():
    """Borrow the console that launched us, if there was one.

    A --windowed build is linked without one, so `GCSViewer.exe --version`
    typed at a prompt has nowhere to answer.  Windows will attach the parent
    process's console on request, and CONOUT$ then writes to it.
    """
    if os.name != "nt":
        return False
    try:
        import ctypes
        ATTACH_PARENT_PROCESS = -1
        if not ctypes.windll.kernel32.AttachConsole(ATTACH_PARENT_PROCESS):
            return False
        sys.stdout = open("CONOUT$", "w", buffering=1)
        sys.stderr = sys.stdout
        return True
    except Exception:
        return False


def _tell(text):
    """Say something to whoever ran the program, wherever they can hear it.

    Three cases, because a --windowed build has no console of its own and
    CPython's print() returns *silently* when sys.stdout is None rather than
    raising: output redirected to a file still prints, a prompt gets the text
    through the parent's console, and a double-click - which has neither -
    gets a message box.
    """
    if getattr(sys, "stdout", None) is not None:
        print(text)
        return
    if _attach_console():
        print(text)
        return
    if os.environ.get("GCS_VIEWER_NO_GUI"):
        return
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk(); r.withdraw()
        messagebox.showinfo("GCS Viewer", text)
        r.destroy()
    except Exception:
        pass


def _error_window(msg):
    # A modal dialog is right for a double-click, and wrong for anything
    # driven by a script: the process would sit forever waiting for an OK
    # nobody is there to click.  GCS_VIEWER_NO_GUI=1 opts out.
    if os.environ.get("GCS_VIEWER_NO_GUI"):
        print(msg, file=sys.stderr)
        return
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk(); r.withdraw()
        messagebox.showerror("GCS Viewer", msg)
        r.destroy()
    except Exception:
        print(msg, file=sys.stderr)


def _ask_for_design():
    """Ask which design to open, for a launch that named no file.

    The installer puts a "GCS Viewer" shortcut in the Start Menu - it has to,
    or Windows 11's Open-With list will not offer the program - and clicking
    it runs the viewer with no arguments.  That printed usage to a console a
    --windowed build does not have and exited 2: from the user's side, a
    Start Menu entry that does nothing at all.

    Returns "" if the dialog is cancelled or cannot be opened.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        r = tk.Tk()
        r.withdraw()
        path = filedialog.askopenfilename(
            title="Open a faceting design",
            filetypes=[("Faceting designs", "*.gcs *.gem"),
                       ("Gemcut Studio", "*.gcs"),
                       ("GemCad", "*.gem"),
                       ("All files", "*.*")])
        r.destroy()
        return path or ""
    except Exception:
        return ""


def _selftest(report_path=None):
    """Render a stone built in memory and write it out as a PNG.

    This exists for the frozen .exe, which can look perfectly healthy and
    still be missing Pillow's PNG encoder or its font handling.  It touches
    the whole chain - write_gcs, parse_gcs, tier_table, render_view, compose,
    save - without needing a design file on disk.
    """
    import tempfile
    import traceback

    log = []

    def say(s):
        log.append(s)

    ok = True
    try:
        n, ang = 8, 43.0
        apex = -1.0 / math.tan(math.radians(ang))
        facets = []
        for i in range(n):
            t0, t1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            V = np.array([[math.sin(t0), math.cos(t0), 0.0],
                          [math.sin(t1), math.cos(t1), 0.0],
                          [0.0, 0.0, apex]])
            nrm = np.cross(V[1] - V[0], V[2] - V[0])
            nrm = nrm / np.linalg.norm(nrm)
            if nrm[2] > 0:
                nrm = -nrm
            facets.append({"verts": V, "normal": nrm, "tier": "P1",
                           "instr": "Cut to center point", "tid": 0})
        r = 0.6
        V = np.array([[r * math.sin(2 * math.pi * i / n),
                       r * math.cos(2 * math.pi * i / n), 0.35]
                      for i in range(n)])
        facets.append({"verts": V, "normal": np.array([0.0, 0.0, 1.0]),
                       "tier": "T", "instr": "Table", "tid": 1})
        say("built %d facets" % len(facets))

        tmp = tempfile.mkdtemp(prefix="gcsviewer-selftest-")
        gcs = os.path.join(tmp, "selftest.gcs")
        write_gcs(gcs, facets, {"title": "Self test"}, {"color": (.3, .5, .9)})
        back, info, material = load_design(gcs)
        say("wrote and re-read %s (%d facets back)" % (gcs, len(back)))
        if len(back) != len(facets):
            ok = False
            say("MISMATCH: %d facets in, %d out" % (len(facets), len(back)))

        rows = tier_table(back, gear=info.get("gear", 96.0))
        say("tier table: " + ", ".join("%s %.2f" % (r["name"], r["angle"])
                                       for r in rows))

        scale = world_scale(back)
        panels = make_panels(back, scale, material["color"], (35, 28),
                             size=240, ss=1, gray=False, labels=True)
        instr = render_instructions(rows, width=240 * 3 + 32)
        png = os.path.join(tmp, "selftest.png")
        compose(panels, info, gcs, 240, instr_img=instr).save(png)
        size = os.path.getsize(png)
        say("wrote %s (%d bytes)" % (png, size))
        if size < 3000:
            ok = False
            say("SUSPICIOUS: PNG is too small to be a real render")
    except Exception:
        ok = False
        say(traceback.format_exc())

    say("SELFTEST %s" % ("PASSED" if ok else "FAILED"))
    text = "\n".join(log) + "\n"
    if report_path:
        try:
            with open(report_path, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as e:
            ok = False
            print("could not write %s: %s" % (report_path, e), file=sys.stderr)
    try:
        print(text)
    except Exception:                     # --windowed builds have no stdout
        pass
    return 0 if ok else 1


def main(argv):
    flags = [a for a in argv[1:] if a.startswith("--")]
    args = [a for a in argv[1:] if not a.startswith("--")]

    if "--version" in flags:
        _tell(version_string())
        return 0

    if "--selftest" in flags:
        return _selftest(args[0] if args else None)

    if not args:
        # Scripted callers keep the old contract: usage on stdout, exit 2.
        # A person who launched it from the Start Menu gets a file picker
        # rather than silence.
        if os.environ.get("GCS_VIEWER_NO_GUI"):
            print(__doc__)
            return 2
        chosen = _ask_for_design()
        if not chosen:
            return 0
        args = [chosen]

    path = args[0]
    if not os.path.isfile(path):
        _error_window(f"File not found:\n{path}")
        return 1

    gray = "--gray" in flags
    labels = "--no-labels" not in flags

    if "--save" in flags:
        try:
            facets, info, material = load_design(path)
            if not facets:
                raise ValueError("No facets found in file.")
        except Exception as e:
            _error_window(f"Could not read:\n{os.path.basename(path)}\n\n{e}")
            return 1
        out = args[1] if len(args) > 1 else os.path.splitext(path)[0] + "_views.png"
        scale = world_scale(facets)
        panels = make_panels(facets, scale, material["color"], (35, 28),
                             size=680, ss=3, gray=gray, labels=labels)
        rows = tier_table(facets, gear=info.get("gear", 96.0))
        instr_img = render_instructions(rows, width=680 * 3 + 32, gray=gray)
        compose(panels, info, path, 680, instr_img=instr_img).save(out)
        print("Saved", out)
        return 0

    try:
        ViewerApp(path, gray=gray, labels=labels).run()
    except Exception as e:
        _error_window(f"Could not read:\n{os.path.basename(path)}\n\n{e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
