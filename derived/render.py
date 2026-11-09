#!/usr/bin/env python3
"""Front-view SVG of a flower record.

derivedFrom: urn:flower-schema:1 sha256:8440941d9f0e5761111f169400b5828a132b2a4852a62bacdb0cd860a8bc31ca

A derived work, not the schema. It reads calyx, corolla and the organs at the
centre, and makes its own choices about how each botanical term becomes a curve.
Usage: render.py record.json out.svg
"""
import json, math, sys

PX = 22          # pixels per millimetre
SIZE = 640

def merge(base, over):
    out = dict(base)
    for k, v in over.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out

def val(m, default=0.0):
    if isinstance(m, dict):
        return m.get("typical", (m["min"] + m.get("max", m["min"])) / 2)
    return default if m is None or m == "indefinite" else m

def outline(length, width, blade, n=48):
    """Half-width profile peaking at widestAt; apex notch for emarginate/obcordate tips."""
    w = min(max(blade.get("widestAt", {"lanceolate": 0.3, "ovate": 0.35}.get(blade.get("outline"), 0.6)), 0.15), 0.85)
    a = math.log(0.5) / math.log(w)
    b = 1.6 if blade.get("apex") in ("acute", "acuminate") else 0.75
    notch = 0.14 * length if blade.get("apex") in ("emarginate", "retuse") or blade.get("outline") == "obcordate" else 0
    side = []
    for i in range(n + 1):
        t = i / n
        h = width / 2 * math.sin(math.pi * t ** a) ** b
        x = length * t - notch * math.exp(-(h / (0.2 * width)) ** 2) * t ** 6
        side.append((x, h))
    pts = side + [(x, -h) for x, h in reversed(side)]
    return "M" + " L".join(f"{x * PX:.1f},{y * PX:.1f}" for x, y in pts) + "Z"

def organs(whorl):
    proto, count = whorl.get("prototype", {}), int(val(whorl.get("count"), 0))
    listed = {m["index"]: m for m in whorl.get("members", [])}
    for i in range(1, count + 1):
        m = listed.get(i, {})
        if m.get("absent"):
            continue
        az = m.get("azimuth", (whorl.get("offset", 0) + (i - 1) * 360 / count) % 360)
        yield az, m.get("role", ""), merge(proto, m.get("overrides", {}))

def draw_blade(az, organ, uid, defs, out, fallback="#888888"):
    blade = organ.get("blade", {})
    L, W = val(organ.get("length"), 8), val(organ.get("width"), val(organ.get("length"), 8) * 0.3)
    ground = blade.get("adaxial", {}).get("color", organ.get("color", {"srgb": fallback}))["srgb"]
    fill = ground
    if "gradient" in blade:
        stops = "".join(f'<stop offset="{s["at"]}" stop-color="{s["color"]["srgb"]}"/>' for s in blade["gradient"])
        defs.append(f'<linearGradient id="g{uid}" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{L * PX:.1f}" y2="0">{stops}</linearGradient>')
        fill = f"url(#g{uid})"
    path = outline(L, W, blade)
    defs.append(f'<clipPath id="c{uid}"><path d="{path}"/></clipPath>')
    g = [f'<g transform="rotate({az - 90:.1f})">', f'<path d="{path}" fill="{fill}" stroke="#00000030" stroke-width="1"/>', f'<g clip-path="url(#c{uid})">']
    ven = blade.get("venation", {})
    if ven:
        for k in range(-4, 5):
            ang = k * 0.13
            g.append(f'<path d="M0,0 Q{L * PX * .5:.1f},{math.sin(ang) * L * PX * .3:.1f} {L * PX:.1f},{math.sin(ang) * W * PX * 1.1:.1f}" fill="none" stroke="#000" stroke-opacity="{0.25 * ven.get("prominence", 0.3):.2f}" stroke-width="1"/>')
    for mk in blade.get("markings", []):
        col = mk.get("color", {"srgb": "#000000"})["srgb"]
        if mk["type"] == "eye":
            r = 0.3 * L * PX
            defs.append(f'<radialGradient id="e{uid}"><stop offset="0" stop-color="{col}"/><stop offset="1" stop-color="{col}" stop-opacity="0"/></radialGradient>')
            g.append(f'<ellipse cx="{0.12 * L * PX:.1f}" cy="0" rx="{r:.1f}" ry="{r * .9:.1f}" fill="url(#e{uid})" opacity="{mk.get("coverage", 1)}"/>')
        elif mk["type"] in ("nectar-guide", "stripe", "streak"):
            n = max(1, round(val(mk.get("count"), 3)))
            f0, f1 = mk.get("from", 0) * L * PX, mk.get("to", 0.5) * L * PX
            for k in range(n):
                ang = (k - (n - 1) / 2) * 0.16
                reach = f1 * (1 - 0.25 * abs(k - (n - 1) / 2) / max(1, (n - 1) / 2))
                g.append(f'<path d="M{f0 + 4:.1f},{math.sin(ang) * 6:.1f} Q{reach * .55:.1f},{math.sin(ang) * reach * .5:.1f} {reach:.1f},{math.sin(ang * 1.5) * reach * .75:.1f}" fill="none" stroke="{col}" stroke-width="2.2" stroke-linecap="round"/>')
    if blade.get("adaxial", {}).get("indumentum") == "bearded":
        for k in range(14):
            y = (k - 6.5) * 2.2
            g.append(f'<line x1="{0.1 * L * PX:.1f}" y1="{y:.1f}" x2="{0.2 * L * PX:.1f}" y2="{y * 1.6:.1f}" stroke="#fff" stroke-opacity=".8" stroke-width="1"/>')
    out.append("".join(g) + "</g></g>")

def render(rec):
    defs, body, uid = [], [], 0
    front = {"dorsal": 0, "upper-lip": 0, "standard": 0, "lateral": 1, "wing": 1, "ventral": 2, "lower-lip": 2, "keel": 2, "labellum": 2}
    centre = []
    for whorl in rec["whorls"]:
        kind, items = whorl["kind"], list(organs(whorl))
        if kind in ("calyx", "epicalyx", "corolla", "perianth"):
            items.sort(key=lambda o: front.get(o[1], 1))
            for az, role, organ in items:
                uid += 1
                if kind in ("calyx", "epicalyx"):
                    organ = merge(organ, {"length": val(organ.get("length"), 6)})
                draw_blade(az, organ, uid, defs, body, "#5E8C3A")
        elif kind == "androecium":
            for az, _, organ in items:
                an = organ.get("stamen", {}).get("anther", {})
                r, col = val(an.get("length"), 1.5) * PX, an.get("color", {"srgb": "#E9D48A"})["srgb"]
                centre.append(f'<ellipse transform="rotate({az - 90:.1f})" cx="{r * .45:.1f}" cy="0" rx="{r * .5:.1f}" ry="{r * .28:.1f}" fill="{col}" stroke="#00000040"/>')
        elif kind == "gynoecium":
            st = whorl.get("prototype", {}).get("carpel", {}).get("stigma", {})
            centre.append(f'<circle r="{0.45 * PX:.1f}" fill="{st.get("color", {"srgb": "#C9D98A"})["srgb"]}" stroke="#00000050"/>')
    label = rec["identity"]["label"]
    tx = rec["identity"].get("taxon", {})
    sci = " ".join(filter(None, [tx.get("genus"), tx.get("species")]))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" width="{SIZE}" height="{SIZE}">'
            f'<!-- derivedFrom: urn:flower-schema:1 sha256:8440941d9f0e5761111f169400b5828a132b2a4852a62bacdb0cd860a8bc31ca -->'
            f'<defs>{"".join(defs)}</defs><rect width="100%" height="100%" fill="#F6F2E8"/>'
            f'<g transform="translate({SIZE / 2},{SIZE / 2 - 20})">{"".join(body)}{"".join(centre)}</g>'
            f'<text x="{SIZE / 2}" y="{SIZE - 44}" text-anchor="middle" font-family="Georgia,serif" font-size="22" fill="#3a3327">{label}</text>'
            f'<text x="{SIZE / 2}" y="{SIZE - 20}" text-anchor="middle" font-family="Georgia,serif" font-style="italic" font-size="15" fill="#7a7060">{sci}</text></svg>\n')

if __name__ == "__main__":
    open(sys.argv[2], "w").write(render(json.load(open(sys.argv[1]))))
