# Architecture Language

Use these words consistently in architecture reviews.

## Terms

**Module**: anything with an interface and an implementation: function, class, package, or workflow slice.

**Interface**: everything a caller must know to use the module correctly: types, invariants, ordering, error modes, config, I/O, and performance expectations.

**Implementation**: the code inside a module.

**Depth**: leverage at the interface. A deep module puts significant behavior behind a small interface. A shallow module exposes nearly as much complexity as it hides.

**Seam**: a place where behavior can be altered without editing in that place.

**Adapter**: a concrete thing satisfying an interface at a seam.

**Leverage**: what callers get from depth: more behavior per unit of interface they must learn.

**Locality**: what maintainers get from depth: change, bugs, and verification concentrated in one place.

## Principles

- Depth is a property of the interface, not implementation size.
- The deletion test: if deleting a module only spreads its complexity across callers, it was earning its keep. If complexity disappears, it was pass-through code.
- The interface is the test surface.
- One adapter means a hypothetical seam. Two adapters means a real seam.
- Avoid exposing internal seams only because tests want them.

## Rejected Framing

- Do not use "interface" only to mean a Python protocol or type signature.
- Avoid "component" and "service" in architecture suggestions unless naming existing code.
- Prefer "seam" over "boundary" when discussing where behavior can vary.
