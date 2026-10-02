# Symmetry and selection rules: what must vanish, what must match, and how to use it as a test

Worked example: graphene/hBN (point group 3m unstrained, m under uniaxial x strain) and MoS2 (-6m2 unstrained, m under
a general strain). Response: second-order DC conductivity sigma_abc with finite broadening Gamma. BCD =
Berry-curvature dipole; B = its clean-limit coefficient (conventions_and_units.md C3).

Principle: every exact symmetry statement is also a free numerical test. Compute the forbidden components and the
symmetry partners on purpose, and treat a residual as a measured model or integration error, not as physics.

## S1. Determine and record the point group of every structure you integrate

- Use a symmetry finder on the actual POSCAR of each strain and record space group, point group and allowed BCD
  components in a JSON next to the structure.
- Example: s = 0: P3m1 (156), point group 3m, D_x and D_y forbidden. s = 0.5-2 %: Cm (8), point group m, D_x allowed,
  D_y forbidden, TR = True. Strained MoS2: Pm, point group m with only the horizontal mirror (acceptance: mirrors <= 1,
  no vertical mirror).
- Record why the strain is there (here: a threefold axis forbids the BCD; the strain breaks C3 so the BCD can be
  nonzero). A reviewer will ask, and the answer decides which components are physical.
- **Source**: the project's methods record (a symmetry JSON per strain).

## S2. Know what a strain tensor actually is before describing it

- **Symptom**: text says "1 % uniaxial strain", file says otherwise.
- **Check**: diagonalise eps(s)/s. MoS2 used eps(s) = s [[1, 0.31], [0.31, -0.17]]: principal strains +1.077 s and
  -0.247 s, tensile axis 13.96 deg from x (zigzag). Not uniaxial, not along a high-symmetry direction.
- **Fix**: write the tensor (or deformation gradient F) and its principal axes in the methods; say whether atoms were
  relaxed at fixed lattice. If the provenance of coefficients is unknown, write UNKNOWN; do not invent a rationale
  (in the example the origin of the tensor coefficients was never documented and stayed UNKNOWN; the strain
  magnitude was fixed before any response was computed).
- **Source**: the project's methods record; the project's paper handoff notes.

## S3. Components that vanish identically

| statement | why | numerical check used |
| --- | --- | --- |
| a contribution that an analytic selection rule of your theory forbids for some components | analytic selection rule | the scans returned abs(value) <= 1e-29 A m V^-2, i.e. numerical zero |
| BCD = 0 in a 2D crystal with C3 | no in-plane vector invariant under C3 | B at s = 0 was 0.4 % of B at the production strain |
| point group m with mirror x -> -x: D_y = 0 | D_a = int f d_a Omega_z; M_x flips Omega_z and d_x, so D_x is even and D_y odd | only D_x computed and nonzero |
| components odd under a mirror of the unstrained point group (e.g. an odd number of x indices under x -> -x) vanish without strain | parity under the mirror | include the unstrained structure as a control |

Run the forbidden component (or the unstrained structure) at least once with the same engine and integration settings
as production. A value that is not small compared with the allowed one means a bug or a symmetry-broken model.

## S4. Relations between allowed components

- With C3 and the mirror x -> -x (3m), sigma_yxx = -sigma_yyy (Neumann's principle); at s = 0 use it as a residual
  check (S5).
- A strain along x keeps the mirror and breaks C3; the relation then no longer holds and the two components carry
  independent information. Decide before computing which relations hold at which strain, and use the unstrained
  structure, where the relation is exact, as a residual check (S5).
- Claims about how a quantity depends on strain: check them on a strain series that includes s = 0 and both small
  and large strains, with the same engine and settings.
- Do not transfer conclusions between materials with different symmetry content: a relation that is exact in one
  point group can be absent in another.

## S5. Symmetry partners as numerical checks: the list used

| check | expected | obtained | reading |
| --- | --- | --- | --- |
| E(k) vs E(-k), all bands, whole BZ | equal (TRS) | 1.4e-7 eV | model real (wannierization.md W6) |
| B at s = 0 | 0 | 0.4 % of B at the production strain | numerical C3 breaking of the Wannier model |
| 3m relation sigma_yxx = -sigma_yyy at s = 0 (Wannier model) | exact | violated by 2.3 % | symmetry error of the interpolated model |
| same relation, exactly symmetric two-band honeycomb model | exact | satisfied to 1e-7 | engine is exact; the 2.3 % is the Wannier model |
| B over K and K' boxes | equal | equal | valley bookkeeping right |
| Gamma x (the integrand term whose clean limit is B) / B as Gamma -> 0 | 1 | 0.99999 at 1e-4 eV (B by an independent integral) | term and BCD integrals consistent |

Rule: when a symmetry relation is violated by a few percent, build the smallest exactly symmetric model that has the
same physics (here a two-band honeycomb model, 887,776-point nested grids, B rechecked adaptively to 1e-11) and see
whether it satisfies the relation exactly. If yes, the residual is a model error: report it as an uncertainty of the
same order as the manifold uncertainty (~2 %), and say so.

## S6. Do not enforce symmetry on the model to make a check pass

- Same reasoning as wannierization.md W7: symmetrising H(R) hides the symptom. The ~2 % residual is information about
  interpolation accuracy (off-grid error ~1.2 meV against a 10 meV filling).
- If a symmetric model is needed, fix the construction (better manifold, finer mesh, symmetry-adapted Wannier
  functions) and re-run every gate. This project did not use symmetry-adapted Wannier functions; do not claim it.

## S7. Symmetric zeros can be expensive

- **Symptom**: at s = 0 each pocket sub-box took ~12 min. Some target quantities vanish by symmetry there (e.g. B),
  but their integrands are not small pointwise; they cancel only between C3-related regions.
- **Cause**: error scales set from a near-zero net value ask for absolute accuracy on a cancelling sum.
- **Fix**: take the error scales from a comparable nonzero case (the production-strain run). Here the switch came after
  156 of 239 boxes; finished boxes were kept (their error bounds are conservative).
- **Source**: the strain-series section of the project's methods record; the scale file of the s = 0 run.

## S8. Which components to compute

- Compute the full symmetry-allowed set that the interpretation needs, plus one forbidden partner as a control; plan
  the set from the symmetry analysis (S1-S4).
- For a strain series, compute s = 0 too: it is the cheapest symmetry test and the reference point of the series.

## Checklist

- [ ] Point group of every structure recorded (file + tool), allowed components listed.
- [ ] Strain tensor diagonalised; text matches the tensor.
- [ ] One forbidden component or the unstrained structure computed with production settings.
- [ ] Symmetry partner relations evaluated; residuals tabulated and interpreted (model vs engine) with a minimal model.
- [ ] Error scales for symmetric zeros taken from a nonzero comparable case.
- [ ] Conclusions stated with the symmetry content they depend on (strain magnitude, material class).
