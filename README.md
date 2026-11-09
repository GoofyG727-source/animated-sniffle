# animated-sniffle

A sealed schema for flowers.

- `flower.schema.json` — JSON Schema (draft 2020-12) describing one flower to
  the individual petal. Frozen; see `COVENANT.md`.
- `SEAL.sha256` — the seal. `sha256sum -c SEAL.sha256` verifies it.
- `specimen/viola-tricolor.json` — the one proof specimen, a wild pansy.
- `COVENANT.md` — the terms: made once, never changed, derived from only.

## Shape

A record is one flower at one moment. Its `whorls` run from the outside
inward (calyx, corolla, androecium, gynoecium, and any others). Each whorl has
a `prototype` organ and, where organs differ, `members`: individual organs
with a position (`index`, `azimuth`) and `overrides` merged over the
prototype. A petal's `blade` carries outline, apex, base, margin, claw, spur,
curvature, twist, venation, both surfaces, a colour gradient and markings.

Flower heads such as daisies are `unit: "pseudanthium"`, and their apparent
petals are whole flowers listed under `inflorescence.florets`.

Lengths are millimetres, angles are degrees, fractions run 0 (base) to 1
(apex). Azimuth 0 is adaxial, increasing clockwise seen from the front.

## Derived works

`derived/` holds works made from the schema. They cite it by hash and never
change it.

- `render.py record.json out.svg` — draws a flower record from the front.
- `generate.py SEED [SEED ...] --out DIR` — invents a flower per seed and draws
  it. The same seed always gives the same flower. `--check` validates each
  invented record against the sealed schema (needs `jsonschema`); `--records`
  also writes the record as JSON.
- `garden/` — seeds 1 to 12.
