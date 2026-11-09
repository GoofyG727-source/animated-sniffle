#!/usr/bin/env python3
"""Realise a flower record in three dimensions, or say why it cannot be.

derivedFrom: urn:flower-schema:1 sha256:8440941d9f0e5761111f169400b5828a132b2a4852a62bacdb0cd860a8bc31ca

A derived work, not the schema. The sealed schema checks that a record is well
formed; this checks that the flower it describes can sit in space.

  1. Consistency. Cross-field rules the schema cannot express: counts against
     listed members, distinct positions, ordered ranges and gradients, valid
     references between whorls.
  2. Construction. Every sepal and petal becomes a surface: its outline swept
     along a centreline that leaves the receptacle at the organ's elevation and
     bends by its longitudinal curve, cupped by its transverse curve, turned by
     its twist.
  3. Clearance. Surfaces are tested pairwise for intersection. Where petals
     overlap, the realiser looks for the smallest adjustment that separates
     them: layering (front petals a little more erect and inserted a little
     higher) and pitch (every organ turned the same way about its own axis, as
     in a contorted bud). Pitch is handed, so where two mirror-image petals
     overlap across the plane of symmetry one ends up in front of the other,
     as happens in living flowers.

A flower is "realised" when an arrangement with no intersections is found. If
none is found, that is a failure of this realiser's search, not a proof that
no arrangement exists. The test is made on meshes, at three resolutions; an
intersection smaller than the finest mesh can escape it. Surfaces have no
thickness; stamens and carpels are placed but not tested.

Usage: realise.py record.json [--out DIR]
       realise.py --seed N [--out DIR]
Exit status: 0 realised, 1 inconsistent record, 2 no clear arrangement found.
"""
import json, math, os, sys
import numpy as np
from render import merge, val

SEAL = "urn:flower-schema:1 sha256:8440941d9f0e5761111f169400b5828a132b2a4852a62bacdb0cd860a8bc31ca"
BLADE_KINDS = ("epicalyx", "calyx", "corolla", "perianth", "corona", "paracorolla")
NT, NS = 18, 6                    # mesh resolution along and across an organ
PROBE = (23, 5)                   # a second, different resolution for the probing edges (see clashes)
CONFIRM = ((41, 11), (53, 13))    # finer probes an arrangement must also pass before it is accepted
LAYER_OF = {"dorsal": 0, "upper-lip": 0, "standard": 0, "outer": 0, "lateral": 1, "wing": 1,
            "ventral": 2, "lower-lip": 2, "keel": 2, "labellum": 2, "inner": 2}
BEND = {"flat": 0, "incurved": 30, "inflexed": 60, "cucullate": 70, "recurved": -30, "reflexed": -70, "revolute": -110, "geniculate": -45, "sigmoid": 0}
CUP = {"flat": 0, "concave": .22, "channelled": .35, "conduplicate": .6, "involute": .4, "tubular": .7, "saccate": .5,
       "convex": -.22, "keeled": -.35, "revolute": -.4, "plicate": 0}


# ---------------------------------------------------------------- consistency

def check(rec):
    """Return (errors, warnings). Errors mean the record contradicts itself."""
    errors, warnings = [], []

    def walk(node, path):
        if isinstance(node, dict):
            if "min" in node and "max" in node and isinstance(node["min"], (int, float)) and node["min"] > node["max"]:
                errors.append(f"{path}: min {node['min']} is greater than max {node['max']}")
            if "from" in node and "to" in node and isinstance(node["from"], (int, float)) and node["from"] > node["to"]:
                errors.append(f"{path}: marking runs from {node['from']} to {node['to']}, backwards")
            g = node.get("gradient")
            if isinstance(g, list):
                ats = [s["at"] for s in g]
                if ats != sorted(ats): errors.append(f"{path}.gradient: stops are not ordered base to apex")
            for k, v in node.items():
                if k != "ext": walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node): walk(v, f"{path}[{i}]")

    walk(rec, "$")
    if rec.get("unit") == "pseudanthium":
        errors.append("$: a pseudanthium is a head of many flowers; realise its florets one at a time")
    whorls = rec.get("whorls", [])
    for wi, w in enumerate(whorls):
        p, count, members = f"$.whorls[{wi}]", w.get("count"), w.get("members", [])
        n = count if isinstance(count, int) else None
        if w["kind"] in BLADE_KINDS:
            if count == "indefinite": errors.append(f"{p}: an indefinite count cannot be built; give a number")
            elif isinstance(count, dict): warnings.append(f"{p}: count is a range; built with {count_of(w)}")
            elif count is None and not members: errors.append(f"{p}: neither a count nor members, so nothing to build")
        idx = [m["index"] for m in members]
        if len(idx) != len(set(idx)): errors.append(f"{p}: two members share an index")
        if n is not None and any(i > n for i in idx): errors.append(f"{p}: member index {max(idx)} exceeds the count of {n}")
        az = [m["azimuth"] for m in members if "azimuth" in m and not m.get("absent")]
        if len(az) != len(set(az)): errors.append(f"{p}: two members occupy the same azimuth")
        if members and n is not None and w["kind"] in BLADE_KINDS and 0 < len(members) < n and any("azimuth" not in m for m in members):
            warnings.append(f"{p}: some members have no azimuth; even spacing assumed")
        for g in w.get("connation", {}).get("groups", []):
            if n is not None and any(i > n for i in g): errors.append(f"{p}.connation: group refers to member {max(g)} of {n}")
        for a in w.get("adnation", []):
            if a["toWhorl"] >= len(whorls): errors.append(f"{p}.adnation: whorl {a['toWhorl']} does not exist")
            elif a["toWhorl"] == wi: errors.append(f"{p}.adnation: a whorl cannot be fused to itself")
        m = rec.get("merosity")
        if m and n and w["kind"] in ("calyx", "corolla") and w.get("phyllotaxis") != "spiral" and n % m:
            warnings.append(f"{p}: {n} parts in a {m}-merous flower")
    return errors, warnings


def count_of(whorl):
    c = whorl.get("count")
    if isinstance(c, dict): return int(round((c["min"] + c.get("max", c["min"])) / 2))
    if isinstance(c, int): return c
    return max([m["index"] for m in whorl.get("members", [])] or [0])


def members_of(whorl):
    """Yield (index, azimuth, role, organ) for every organ present in a whorl."""
    n, proto = count_of(whorl), whorl.get("prototype", {})
    listed = {m["index"]: m for m in whorl.get("members", [])}
    step = whorl["divergence"] if whorl.get("phyllotaxis") == "spiral" and "divergence" in whorl else 360 / max(n, 1)
    for i in range(1, n + 1):
        m = listed.get(i, {})
        if m.get("absent"): continue
        az = m.get("azimuth", (whorl.get("offset", 0) + (i - 1) * step) % 360)
        yield i, az, m.get("role", ""), merge(proto, m.get("overrides", {}))


# --------------------------------------------------------------- construction

def half_width(t, width, blade):
    """Same outline family the front-view renderer uses, as a function of position along the organ."""
    w = min(max(blade.get("widestAt", {"lanceolate": .3, "ovate": .35}.get(blade.get("outline"), .6)), .15), .85)
    a = math.log(.5) / math.log(w)
    b = 1.6 if blade.get("apex") in ("acute", "acuminate") else .75
    return width / 2 * np.sin(np.pi * np.clip(t, 0, 1) ** a) ** b


def surface(organ, az, r0, z0, elevation, pitch, NT=NT, NS=NS):
    """Vertices (NT+1, NS+1, 3) of one blade, and its adaxial normals (NT+1, 3)."""
    blade = organ.get("blade", {})
    L = val(organ.get("length"), 8)
    W = val(organ.get("width"), L * .3)
    bend = blade.get("longitudinalCurveAngle", BEND.get(blade.get("longitudinalCurve"), 0))
    cup = CUP.get(blade.get("transverseCurve"), 0)
    twist = blade.get("twist", 0)
    t = np.linspace(0, 1, NT + 1)
    theta = np.radians(elevation - bend * t)                    # angle between centreline and floral axis
    dt = 1 / NT
    rho = r0 + np.concatenate([[0], np.cumsum(L * np.sin((theta[:-1] + theta[1:]) / 2) * dt)])
    z = z0 + np.concatenate([[0], np.cumsum(L * np.cos((theta[:-1] + theta[1:]) / 2) * dt)])
    a = math.radians(az)
    radial, lateral, axis = np.array([math.sin(a), math.cos(a), 0]), np.array([math.cos(a), -math.sin(a), 0]), np.array([0, 0, 1.0])
    centre = rho[:, None] * radial + z[:, None] * axis
    normal = -np.cos(theta)[:, None] * radial + np.sin(theta)[:, None] * axis     # adaxial side
    phi = np.radians(pitch + twist * t)
    across = np.cos(phi)[:, None] * lateral + np.sin(phi)[:, None] * normal
    up = -np.sin(phi)[:, None] * lateral + np.cos(phi)[:, None] * normal
    h = half_width(t, W, blade)
    s = np.linspace(-1, 1, NS + 1)
    verts = (centre[:, None, :] + (h[:, None] * s[None, :])[..., None] * across[:, None, :]
             + (cup * h[:, None] * (s[None, :] ** 2))[..., None] * up[:, None, :])
    return verts, up


def triangles(verts):
    a, b, c, d = verts[:-1, :-1], verts[1:, :-1], verts[1:, 1:], verts[:-1, 1:]
    return np.concatenate([np.stack([a, b, c], -2).reshape(-1, 3, 3), np.stack([a, c, d], -2).reshape(-1, 3, 3)])


def edges(verts):
    along = np.stack([verts[:-1], verts[1:]], -2).reshape(-1, 2, 3)
    across = np.stack([verts[:, :-1], verts[:, 1:]], -2).reshape(-1, 2, 3)
    e = np.concatenate([along, across])
    return e[np.linalg.norm(e[:, 1] - e[:, 0], axis=1) > 1e-9]


def crossings(edge, tri):
    """Number of mesh edges of one surface that pass through triangles of another."""
    p, d = edge[:, 0][:, None, :], (edge[:, 1] - edge[:, 0])[:, None, :]
    v0, e1, e2 = tri[:, 0][None], (tri[:, 1] - tri[:, 0])[None], (tri[:, 2] - tri[:, 0])[None]
    h = np.cross(d, e2)
    det = (e1 * h).sum(-1)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
    s = p - v0
    u = inv * (s * h).sum(-1)
    q = np.cross(s, e1)
    v = inv * (d * q).sum(-1)
    w = inv * (e2 * q).sum(-1)
    eps = 1e-6
    return int((ok & (u > eps) & (v > eps) & (u + v < 1 - eps) & (w > eps) & (w < 1 - eps)).sum())


def build(rec, layer_step, pitch):
    """All blade surfaces for one candidate arrangement."""
    blades = [w for w in rec["whorls"] if w["kind"] in BLADE_KINDS]
    span = max([val(o.get("length"), 8) for w in blades for _, _, _, o in members_of(w)] or [10])
    r0 = max(val(rec.get("receptacle", {}).get("diameter"), 0) / 2, span * .04)
    out, depth = [], 0
    for w in blades:
        sepal = w["kind"] in ("calyx", "epicalyx")
        spiral = w.get("phyllotaxis") == "spiral"
        if not sepal: depth += 1
        for i, az, role, organ in members_of(w):
            layer = (0 if sepal else depth) + (LAYER_OF.get(role, 1) if role else 0) + (i - 1 if spiral and not sepal else 0) * .5
            base = organ.get("blade", {}).get("elevation", 100 if sepal else 80)
            turn = pitch
            place = (organ, az, r0, layer * span * .012 - (span * .03 if sepal else 0), max(base - layer_step * layer, 3), turn)
            verts, up = surface(*place)
            out.append({"whorl": w["kind"], "index": i, "azimuth": az, "role": role, "organ": organ, "verts": verts, "up": up,
                        "place": place,
                        "elevation": max(base - layer_step * layer, 3), "pitch": turn})
    return out, span


def clashes(surfs, first_only=False, probe=PROBE):
    """Pairs of surfaces that pass through each other.

    Edges of one surface are tested against triangles of the other. The edges
    come from a mesh of a different resolution than the triangles: in a
    symmetric flower two equal petals meet exactly along each other's mesh
    lines, and an edge that lands on a triangle's boundary would go uncounted.
    """
    hits = []
    boxes = [(s["verts"].reshape(-1, 3).min(0), s["verts"].reshape(-1, 3).max(0)) for s in surfs]
    tris, eds = [triangles(s["verts"]) for s in surfs], [edges(surface(*s["place"], *probe)[0]) for s in surfs]
    for i in range(len(surfs)):
        for j in range(i + 1, len(surfs)):
            if (boxes[i][0] > boxes[j][1]).any() or (boxes[j][0] > boxes[i][1]).any(): continue
            n = crossings(eds[i], tris[j]) + crossings(eds[j], tris[i])
            if n:
                hits.append((i, j, n))
                if first_only: return hits
    return hits


def realise(rec):
    """Search for the gentlest arrangement with no intersecting surfaces."""
    candidates = sorted(((ls, p) for ls in range(0, 19, 3) for p in range(0, 37, 4)), key=lambda c: (c[0] + c[1], c[1]))
    for ls, p in candidates:
        surfs, span = build(rec, ls, p)
        if not clashes(surfs, first_only=True) and not any(clashes(surfs, first_only=True, probe=c) for c in CONFIRM):
            return {"realised": True, "layerStep": ls, "pitch": p, "surfaces": surfs, "span": span, "clashes": []}
    best = None                                   # nothing clear: report the least bad of a few arrangements
    for ls, p in ((0, 0), (0, 16), (9, 16), (18, 36)):
        surfs, span = build(rec, ls, p)
        hits = clashes(surfs)
        if best is None or len(hits) < len(best["clashes"]):
            best = {"realised": False, "layerStep": ls, "pitch": p, "surfaces": surfs, "span": span, "clashes": hits}
    return best


# --------------------------------------------------------------------- output

def rgb(c): return np.array([int(c["srgb"][i:i + 2], 16) for i in (1, 3, 5)], float)

def colour_along(organ, t, fallback):
    blade = organ.get("blade", {})
    g = blade.get("gradient")
    if not g: return rgb(blade.get("adaxial", {}).get("color", organ.get("color", {"srgb": fallback})))
    for a, b in zip(g, g[1:]):
        if t <= b["at"]:
            k = 0 if b["at"] == a["at"] else (t - a["at"]) / (b["at"] - a["at"])
            return rgb(a["color"]) * (1 - min(max(k, 0), 1)) + rgb(b["color"]) * min(max(k, 0), 1)
    return rgb(g[-1]["color"])


def centre_parts(rec, span):
    """Stamens and style as simple lines with tips. Placed, not tested for clearance."""
    parts = []
    for w in rec["whorls"]:
        if w["kind"] == "androecium":
            for i, az, _, organ in members_of(w):
                st = organ.get("stamen", {})
                fl = max(val(st.get("filament", {}).get("length"), span * .1), span * .03)
                a, lean = math.radians(az), math.radians(22)
                tip = np.array([math.sin(a) * math.sin(lean), math.cos(a) * math.sin(lean), math.cos(lean)]) * fl
                parts.append((np.zeros(3), tip, st.get("filament", {}).get("color", {"srgb": "#E8E4C8"}),
                              st.get("anther", {}).get("color", {"srgb": "#E9D48A"}), max(val(st.get("anther", {}).get("length"), 1), .4) * .45))
        elif w["kind"] == "gynoecium":
            c = w.get("prototype", {}).get("carpel", {})
            h = val(c.get("ovary", {}).get("length"), span * .1) + val(c.get("style", {}).get("length"), span * .1)
            parts.append((np.zeros(3), np.array([0, 0, h]), c.get("ovary", {}).get("color", {"srgb": "#7FA05A"}),
                          c.get("stigma", {}).get("color", {"srgb": "#C9D98A"}), span * .03))
    return parts


def view(result, rec, tilt, size, ox):
    """One orthographic view as SVG fragments: painter's order, two-sided shading."""
    t = math.radians(tilt)
    R = np.array([[1, 0, 0], [0, math.cos(t), -math.sin(t)], [0, math.sin(t), math.cos(t)]])
    scale = .42 * size / (result["span"] * 1.15)
    light = np.array([-.35, .5, .8]); light /= np.linalg.norm(light)
    items = []
    for s in result["surfaces"]:
        v = s["verts"] @ R.T
        up = s["up"] @ R.T
        sepal = s["whorl"] in ("calyx", "epicalyx")
        back = rgb(s["organ"].get("blade", {}).get("abaxial", {}).get("color", {"srgb": "#000000"})) if "abaxial" in s["organ"].get("blade", {}) else None
        for i in range(NT):
            base = colour_along(s["organ"], (i + .5) / NT, "#5E8C3A" if sepal else "#888888")
            for j in range(NS):
                quad = np.array([v[i, j], v[i + 1, j], v[i + 1, j + 1], v[i, j + 1]])
                n = np.cross(quad[2] - quad[0], quad[3] - quad[1])
                ln = np.linalg.norm(n)
                if ln < 1e-12: continue
                n /= ln
                if n @ up[i] < 0: n = -n                     # orient to the adaxial side
                facing = n[2] > 0                            # adaxial side towards the viewer
                col = base if facing or back is None else back
                if not facing and back is None: col = base * .72
                shade = .55 + .45 * abs(n @ light)
                items.append((quad[:, 2].mean(), "poly", quad, np.clip(col * shade, 0, 255)))
    for p0, p1, stem, tip, r in centre_parts(rec, result["span"]):
        a, b = R @ p0, R @ p1
        items.append(((a[2] + b[2]) / 2 + .01, "line", (a, b), rgb(stem)))
        items.append((b[2] + .02, "dot", (b, r), rgb(tip)))
    items.sort(key=lambda it: it[0])
    hexc = lambda c: "#%02X%02X%02X" % tuple(int(round(x)) for x in c)
    X = lambda p: ox + size / 2 + p[0] * scale
    Y = lambda p: size / 2 - p[1] * scale
    out = []
    for _, kind, geo, col in items:
        if kind == "poly":
            pts = " ".join(f"{X(p):.1f},{Y(p):.1f}" for p in geo)
            out.append(f'<polygon points="{pts}" fill="{hexc(col)}" stroke="{hexc(col)}" stroke-width=".6"/>')
        elif kind == "line":
            out.append(f'<line x1="{X(geo[0]):.1f}" y1="{Y(geo[0]):.1f}" x2="{X(geo[1]):.1f}" y2="{Y(geo[1]):.1f}" stroke="{hexc(col)}" stroke-width="1.6"/>')
        else:
            out.append(f'<circle cx="{X(geo[0]):.1f}" cy="{Y(geo[0]):.1f}" r="{max(geo[1] * scale, 2):.1f}" fill="{hexc(col)}" stroke="#00000040"/>')
    return "".join(out)


def svg(result, rec):
    size = 560
    verdict = (f"realised · layering {result['layerStep']}° · pitch {result['pitch']}°" if result["realised"]
               else f"not realised · {len(result['clashes'])} pairs of surfaces still intersect")
    cap = lambda x, text: f'<text x="{x}" y="{size - 14}" text-anchor="middle" font-family="Georgia,serif" font-size="13" fill="#7a7060">{text}</text>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size * 3} {size + 70}" width="{size * 3}" height="{size + 70}">'
            f'<!-- derivedFrom: {SEAL} -->'
            f'<rect width="100%" height="100%" fill="#F6F2E8"/>'
            f'{view(result, rec, 0, size, 0)}{view(result, rec, -55, size, size)}{view(result, rec, -90, size, size * 2)}'
            f'{cap(size / 2, "front")}{cap(size * 1.5, "three-quarter")}{cap(size * 2.5, "side")}'
            f'<text x="{size * 1.5}" y="{size + 30}" text-anchor="middle" font-family="Georgia,serif" font-size="22" fill="#3a3327">{rec["identity"]["label"]}</text>'
            f'<text x="{size * 1.5}" y="{size + 54}" text-anchor="middle" font-family="Georgia,serif" font-style="italic" font-size="14" fill="#7a7060">{verdict}</text></svg>\n')


def obj(result, rec):
    lines, base = [f"# {rec['identity']['label']}", f"# derivedFrom: {SEAL}", "# units: millimetres; +z is the floral axis; +y is adaxial (azimuth 0)"], 1
    for s in result["surfaces"]:
        lines.append(f"g {s['whorl']}_{s['index']}")
        flat = s["verts"].reshape(-1, 3)
        lines += [f"v {x:.4f} {y:.4f} {z:.4f}" for x, y, z in flat]
        for i in range(NT):
            for j in range(NS):
                a = base + i * (NS + 1) + j
                lines.append(f"f {a} {a + NS + 1} {a + NS + 2} {a + 1}")
        base += len(flat)
    return "\n".join(lines) + "\n"


def report(rec, errors, warnings, result):
    r = {"flower": rec["identity"]["label"], "id": rec.get("id"), "derivedFrom": SEAL, "consistent": not errors, "errors": errors, "warnings": warnings}
    if result:
        r.update(realised=result["realised"], layerStepDegrees=result["layerStep"], pitchDegrees=result["pitch"],
                 surfaces=len(result["surfaces"]),
                 intersectingPairs=[{"a": f"{result['surfaces'][i]['whorl']} {result['surfaces'][i]['index']}",
                                     "b": f"{result['surfaces'][j]['whorl']} {result['surfaces'][j]['index']}", "crossings": n} for i, j, n in result["clashes"]],
                 organs=[{"whorl": s["whorl"], "index": s["index"], "azimuth": s["azimuth"], "elevation": round(s["elevation"], 1), "pitch": s["pitch"]} for s in result["surfaces"]])
    return r


if __name__ == "__main__":
    args, out = sys.argv[1:], "."
    if "--out" in args: out = args.pop(args.index("--out") + 1); args.remove("--out")
    if "--seed" in args:
        from generate import flower
        rec = flower(args[args.index("--seed") + 1])
    else:
        rec = json.load(open(args[0]))
    os.makedirs(out, exist_ok=True)
    stem = os.path.join(out, rec.get("id", "flower"))
    errors, warnings = check(rec)
    for w in warnings: print("warning:", w)
    for e in errors: print("error:  ", e)
    result = None if errors else realise(rec)
    json.dump(report(rec, errors, warnings, result), open(stem + ".realised.json", "w"), indent=2)
    if errors:
        print(f"{rec['identity']['label']}: inconsistent, not built"); sys.exit(1)
    open(stem + ".realised.svg", "w").write(svg(result, rec))
    if result["realised"]:
        open(stem + ".obj", "w").write(obj(result, rec))
        print(f"{rec['identity']['label']}: realised with layering {result['layerStep']} deg, pitch {result['pitch']} deg, {len(result['surfaces'])} surfaces clear")
        sys.exit(0)
    print(f"{rec['identity']['label']}: no clear arrangement found; {len(result['clashes'])} pairs still intersect")
    sys.exit(2)
