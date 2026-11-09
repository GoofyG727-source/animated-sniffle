#!/usr/bin/env python3
"""Invent a flower from a seed.

derivedFrom: urn:flower-schema:1 sha256:8440941d9f0e5761111f169400b5828a132b2a4852a62bacdb0cd860a8bc31ca

A derived work, not the schema. One seed gives one flower, always the same one.
Each flower is built as a record in the shape the sealed schema describes, then
drawn by render.py.

Rules the generator holds itself to, which the schema alone does not enforce:
  - every whorl's count equals the organs it places, at distinct azimuths;
  - a zygomorphic flower is mirror-symmetric about its vertical plane;
  - petal width is tied to the arc available at its widest point, so petals
    touch or overlap by a bounded amount and never exceed 1.6x their share;
  - inner whorls are shorter than outer ones; gradients run base to apex.

Usage: generate.py SEED [SEED ...] [--out DIR] [--records] [--check]
"""
import colorsys, json, math, os, random, sys
from render import render

URN = "urn:flower-schema:1"
PHI = 137.5

def hexcol(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h % 1, min(max(l, 0), 1), min(max(s, 0), 1))
    return {"srgb": "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))}

class Dice:
    """Only random() is used, so a seed maps to the same flower on any Python."""
    def __init__(self, seed): self.r = random.Random(f"flower:{seed}")
    def u(self, a=0.0, b=1.0): return a + (b - a) * self.r.random()
    def pick(self, items): return items[int(self.r.random() * len(items))]
    def weighted(self, pairs):
        x, acc = self.r.random() * sum(w for _, w in pairs), 0
        for item, w in pairs:
            acc += w
            if x < acc: return item
        return pairs[-1][0]
    def chance(self, p): return self.r.random() < p

def name(d):
    a = ["Ael", "Bry", "Cal", "Dor", "Eri", "Fen", "Gal", "Hes", "Ily", "Jun", "Kor", "Lum", "Mer", "Nyx", "Oro", "Pel", "Quil", "Ros", "Syl", "Tha", "Umb", "Ves", "Wis", "Xan", "Yar", "Zeph"]
    b = ["ant", "ell", "id", "or", "un", "yth", "ar", "en", "ios", "ul"]
    c = ["ia", "ea", "ium", "ella", "ina", "anthe", "ora", "is"]
    e = ["aurea", "nocturna", "minor", "regalis", "velutina", "stellata", "picta", "mirabilis", "pallida", "ignea", "lunaris", "sylvatica", "maculata", "tenella", "grandiflora", "serena"]
    return d.pick(a) + d.pick(b) + d.pick(c), d.pick(e)

def petal_blade(d, pal, zyg):
    outline = d.weighted([("obovate", 4), ("elliptic", 3), ("ovate", 2), ("spatulate", 2), ("lanceolate", 2), ("obcordate", 1.5), ("orbicular", 1.5), ("oblanceolate", 1)])
    widest = {"ovate": d.u(.3, .42), "lanceolate": d.u(.25, .38), "elliptic": d.u(.45, .55), "orbicular": d.u(.48, .58)}.get(outline, d.u(.6, .75))
    apex = "emarginate" if outline == "obcordate" else d.weighted([("rounded", 4), ("obtuse", 2), ("acute", 2.5 if outline in ("lanceolate", "ovate", "elliptic") else .5), ("emarginate", 1)])
    blade = {"outline": outline, "widestAt": round(widest, 2), "apex": apex,
             "base": "clawed" if outline == "spatulate" else "cuneate",
             "margin": d.weighted([("entire", 5), ("undulate", 2), ("ruffled", 1), ("erose", 1)]),
             "texture": d.pick(["velvety", "satiny", "waxy", "silky", "crepe", "papery"]),
             "translucency": round(d.u(0, .35), 2), "elevation": round(d.u(60, 95)),
             "venation": {"pattern": d.pick(["flabellate", "parallel", "palmate", "reticulate"]), "prominence": round(d.u(.05, .6), 2)},
             "adaxial": {"color": pal["ground"], "gloss": round(d.u(0, .5), 2), "epidermis": d.pick(["conical", "flat", "papillate"])},
             "abaxial": {"color": pal["back"]}}
    style = d.weighted([("plain", 2), ("throat", 4), ("tip", 2), ("three", 2)])
    if style == "throat":
        blade["gradient"] = [{"at": 0, "color": pal["throat"]}, {"at": round(d.u(.25, .5), 2), "color": pal["ground"]}, {"at": 1, "color": pal["ground"]}]
    elif style == "tip":
        blade["gradient"] = [{"at": 0, "color": pal["ground"]}, {"at": round(d.u(.5, .7), 2), "color": pal["ground"]}, {"at": 1, "color": pal["tip"]}]
    elif style == "three":
        blade["gradient"] = [{"at": 0, "color": pal["throat"]}, {"at": round(d.u(.3, .45), 2), "color": pal["ground"]}, {"at": 1, "color": pal["tip"]}]
    marks = []
    if not zyg and d.chance(.35):
        marks.append({"type": "nectar-guide", "color": pal["ink"], "region": "base", "from": 0, "to": round(d.u(.3, .6), 2), "count": d.pick([1, 3, 3, 5]), "visibleIn": "both"})
    if d.chance(.2):
        marks.append({"type": "spot", "color": pal["ink"], "region": "limb", "from": round(d.u(.1, .25), 2), "to": round(d.u(.45, .75), 2), "count": int(d.u(6, 22)), "visibleIn": "human-visible"})
    if d.chance(.18):
        marks.append({"type": "picotee", "color": pal["tip"], "region": "margin", "coverage": round(d.u(.04, .1), 3), "visibleIn": "human-visible"})
    if marks: blade["markings"] = marks
    return blade

def fit_width(d, length, widest, n, lo=.75, hi=1.6):
    """Width as a multiple of the arc one petal owns at its widest point."""
    share = 2 * math.pi * widest * length / n
    return round(min(share * d.u(lo, hi), length * 1.15), 1)

def flower(seed):
    d = Dice(seed)
    genus, species = name(d)
    hue = d.u()
    light = d.weighted([(.32, 2), (.5, 4), (.68, 3), (.86, 2)])
    sat = d.u(.45, .95)
    pal = {"ground": hexcol(hue, sat, light), "back": hexcol(hue, sat * .7, min(light + .12, .92)),
           "throat": hexcol(hue + d.pick([.08, -.08, .45, .5, .55, .15]), d.u(.6, 1), d.pick([.55, .7, .9])),
           "tip": hexcol(hue + d.u(-.08, .08), sat, d.pick([light * .55, min(light + .28, .95)])),
           "ink": hexcol(hue + d.u(-.05, .05), .6, d.u(.08, .2)),
           "green": hexcol(d.u(.24, .36), d.u(.3, .55), d.u(.3, .45))}
    zyg = d.chance(.3)
    spiral = (not zyg) and d.chance(.18)
    n = d.pick([8, 13, 21]) if spiral else d.weighted([(3, 1.5), (4, 2), (5, 6), (6, 2.5), (7, .5), (8, 1)])
    if zyg: n = d.pick([3, 5, 5, 5])
    L = round(d.u(7, 32), 1)
    blade = petal_blade(d, pal, zyg)
    W = fit_width(d, L, blade["widestAt"], n, *((.9, 1.6) if not spiral else (1.2, 1.6)))
    step = 360 / n

    whorls = [{"kind": "calyx", "organName": "sepal", "phyllotaxis": "whorled", "count": min(n, 5) if spiral else n,
               "offset": round(step / 2 % 360, 2) if not spiral else 0, "aestivation": d.pick(["valvate", "imbricate", "quincuncial"]),
               "connation": {"degree": d.pick(["free", "free", "basal"])},
               "prototype": {"length": round(L * d.u(.3, .6), 1), "color": pal["green"], "persistence": d.pick(["persistent", "deciduous"]),
                             "blade": {"outline": d.pick(["lanceolate", "ovate"]), "apex": "acute", "margin": "entire", "texture": "herbaceous"}}}]
    whorls[0]["prototype"]["width"] = round(whorls[0]["prototype"]["length"] * d.u(.28, .45), 1)

    corolla = {"kind": "corolla", "organName": "petal", "count": n, "aestivation": d.pick(["imbricate", "contorted", "valvate", "cochlear"]),
               "connation": {"degree": "free"}, "prototype": {"length": L, "width": W, "blade": blade}}
    if spiral:
        corolla.update(phyllotaxis="spiral", divergence=PHI, offset=0)
    elif zyg:
        corolla["phyllotaxis"] = "whorled"
        lip = {"outline": d.pick(["obcordate", "obovate", "orbicular"]), "widestAt": round(d.u(.6, .72), 2),
               "gradient": [{"at": 0, "color": pal["throat"]}, {"at": round(d.u(.3, .5), 2), "color": pal["throat"]}, {"at": round(d.u(.6, .8), 2), "color": pal["tip"]}, {"at": 1, "color": pal["tip"]}],
               "markings": [{"type": "nectar-guide", "color": pal["ink"], "region": "base", "from": 0, "to": round(d.u(.35, .6), 2), "count": d.pick([3, 5, 7]), "visibleIn": "both"}]}
        if lip["outline"] == "obcordate": lip["apex"] = "emarginate"
        lipL = round(L * d.u(1.05, 1.35), 1)
        lip_over = {"length": lipL, "width": fit_width(d, lipL, lip["widestAt"], n, 1.1, 1.6), "blade": lip}
        side = {"length": round(L * d.u(.75, .95), 1), "blade": {"adaxial": {"color": pal["tip"]}}}
        side["width"] = fit_width(d, side["length"], blade["widestAt"], n, .8, 1.2)
        members = []
        for i in range(n):
            az = round((180 + i * step) % 360, 2)
            off = min(az, 360 - az)                      # angular distance from the top
            m = {"index": i + 1, "azimuth": az, "role": "ventral" if az == 180 else "dorsal" if off <= 60 else "lateral"}
            if m["role"] == "ventral": m["overrides"] = lip_over
            elif m["role"] == "lateral": m["overrides"] = side
            members.append(m)
        corolla["members"] = members
    else:
        corolla.update(phyllotaxis="whorled", offset=0)
    whorls.append(corolla)

    doubling = "single"
    if not zyg and not spiral and d.chance(.3):
        inner = json.loads(json.dumps(corolla))
        k = d.u(.55, .8)
        inner["prototype"].update(length=round(L * k, 1), width=round(W * k, 1))
        inner["offset"] = round(step / 2, 2)
        if d.chance(.5): inner["prototype"]["blade"]["adaxial"]["color"] = pal["tip"]; inner["prototype"]["blade"].pop("gradient", None)
        whorls.append(inner); doubling = "semi-double"

    many = d.chance(.3)
    ns = int(d.u(18, 40)) if many else n * d.pick([1, 1, 2]) if not spiral else int(d.u(13, 34))
    anther = hexcol(d.pick([.12, .14, .08, .1, hue + .5]), d.u(.6, .95), d.u(.45, .7))
    whorls.append({"kind": "androecium", "organName": "stamen", "phyllotaxis": "spiral" if many or spiral else "whorled", "count": ns,
                   **({"divergence": PHI} if many or spiral else {"offset": round(step / 2, 2)}),
                   "connation": {"degree": "free"},
                   "prototype": {"stamen": {"fertile": True,
                       "filament": {"length": round(L * d.u(.08, .3), 1), "color": hexcol(hue, .3, .85), "form": "filiform"},
                       "anther": {"length": round(max(L * d.u(.05, .1), .6), 1), "color": anther, "attachment": d.pick(["basifixed", "dorsifixed", "versatile"]), "dehiscence": "longitudinal", "facing": "introrse", "thecae": 2},
                       "pollen": {"color": anther, "presentation": "monad"}, "exserted": True}}})
    nc = d.pick([1, 2, 3, 3, 5, n if n <= 8 else 5])
    whorls.append({"kind": "gynoecium", "organName": "carpel", "count": nc, "connation": {"degree": "complete" if nc > 1 else "free"},
                   "prototype": {"carpel": {"ovary": {"length": round(L * .12, 1), "color": pal["green"], "locules": nc, "placentation": "axile" if nc > 1 else "marginal"},
                                            "style": {"length": round(L * d.u(.1, .3), 1), "position": "terminal", "form": "filiform"},
                                            "stigma": {"form": "lobed" if nc > 1 else "capitate", "lobes": nc, "color": hexcol(d.u(.15, .3), .5, .7), "surface": d.pick(["wet", "dry"])}}}})

    span = max([L] + [m.get("overrides", {}).get("length", 0) for m in corolla.get("members", [])])
    return {"schema": URN, "id": f"seed-{seed}",
            "identity": {"label": f"{genus} {species}", "reality": "imagined", "taxon": {"genus": genus, "species": species},
                         "source": f"generate.py seed {seed}"},
            "unit": "flower", "inflorescence": {"type": "solitary"},
            "sexuality": "bisexual", "symmetry": "zygomorphic" if zyg else "spiral" if spiral else "actinomorphic",
            "symmetryPlanes": 1 if zyg else 0 if spiral else n, "merosity": 0 if spiral else n,
            "form": "bilabiate" if zyg else d.pick(["rotate", "stellate", "cupped", "bowl"]), "doubling": doubling,
            "diameter": round(2 * span * math.sin(math.radians(min(blade["elevation"], 90))), 1),
            "orientation": d.pick(["erect", "ascending", "horizontal", "nodding"]),
            "receptacle": {"form": d.pick(["flat", "convex", "conical"]), "ovaryPosition": "superior", "insertion": "hypogynous"},
            "whorls": whorls,
            "scent": {"present": d.chance(.6), "intensity": round(d.u(), 2)},
            "phenology": {"stage": "anthesis", "openness": 1}}

def self_check(rec):
    """The generator's own physical rules (see module docstring)."""
    prev = None
    for w in rec["whorls"]:
        ms = w.get("members")
        if ms:
            assert len(ms) == w["count"] and len({m["azimuth"] for m in ms}) == len(ms)
            by_az = {m["azimuth"]: json.dumps(m.get("overrides"), sort_keys=True) for m in ms}
            assert all(by_az.get(round((360 - a) % 360, 2)) == o for a, o in by_az.items()), "not mirror-symmetric"
        if w["kind"] == "corolla":
            p = w["prototype"]
            share = 2 * math.pi * p["blade"]["widestAt"] * p["length"] / w["count"]
            assert p["width"] <= 1.6 * share + .06 and (prev is None or p["length"] < prev)
            prev = p["length"]
        g = w["prototype"].get("blade", {}).get("gradient")
        assert not g or [s["at"] for s in g] == sorted(s["at"] for s in g)

if __name__ == "__main__":
    args, out = sys.argv[1:], "."
    if "--out" in args: out = args.pop(args.index("--out") + 1); args.remove("--out")
    records, check = "--records" in args, "--check" in args
    validator = None
    if check:
        from jsonschema import Draft202012Validator
        validator = Draft202012Validator(json.load(open(os.path.join(os.path.dirname(__file__), "..", "flower.schema.json"))))
    os.makedirs(out, exist_ok=True)
    for seed in [a for a in args if not a.startswith("--")]:
        rec = flower(seed)
        self_check(rec)
        if validator: validator.validate(rec)
        open(os.path.join(out, f"seed-{seed}.svg"), "w").write(render(rec))
        if records: json.dump(rec, open(os.path.join(out, f"seed-{seed}.json"), "w"), indent=2)
        print(f"seed {seed}: {rec['identity']['label']}")
