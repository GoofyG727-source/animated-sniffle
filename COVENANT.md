# Covenant

`flower.schema.json` was made once, on 2026-11-09, and is frozen.

    urn:flower-schema:1
    sha256 8440941d9f0e5761111f169400b5828a132b2a4852a62bacdb0cd860a8bc31ca

1. **One issue.** There is no version 2. The file is never edited, reformatted,
   re-serialised or reissued. `SEAL.sha256` records its bytes; CI fails if
   they change.
2. **No second casting.** The generator that produced the file was discarded
   and is not in this repository. The file is the only original.
3. **One proof.** `specimen/viola-tricolor.json` is the single record made
   directly against the schema, to prove it holds a real flower down to each
   petal. It is the last direct use.
4. **Derivation only.** From here the schema is source material. Anything made
   from it — a drawing, a generator, a garden of data, another schema — is a
   new work that derives from this one and names it:

       derivedFrom: urn:flower-schema:1 sha256:8440941d9f0e5761111f169400b5828a132b2a4852a62bacdb0cd860a8bc31ca

   A derivative may take any part, reshape it, or break it. It may not present
   itself as this schema or reuse the identifier `urn:flower-schema:1`.
5. **Nothing needs to change.** Every vocabulary accepts an `x:` term and
   every object accepts `ext` and `notes`, so a flower this schema did not
   foresee is still expressible without touching the file.

Verify the seal:

    sha256sum -c SEAL.sha256
