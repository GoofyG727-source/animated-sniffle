# Covenant

`flower.schema.json` was made on 2026-11-09.

    urn:flower-schema:1
    sha256 8440941d9f0e5761111f169400b5828a132b2a4852a62bacdb0cd860a8bc31ca

One rule: **don't make the same thing twice.**

- The schema is made once. It is not remade or reissued; `SEAL.sha256`
  records its bytes and CI fails if they change.
- Use it freely. Records, drawings, generators and anything else built with it
  are welcome, as long as each is a new thing and not a copy of one that
  already exists.
- A work built from it says so:

      derivedFrom: urn:flower-schema:1 sha256:8440941d9f0e5761111f169400b5828a132b2a4852a62bacdb0cd860a8bc31ca

Every vocabulary accepts an `x:` term and every object accepts `ext` and
`notes`, so a flower the schema did not foresee can still be described
without changing the file.

Verify the seal:

    sha256sum -c SEAL.sha256
