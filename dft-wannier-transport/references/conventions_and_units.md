# Conventions and units: factors of 2, signs, sheet units, Fermi-surface scales, mobility

The authority for formulas is the manuscript; the project kept a convention file and quoted equations as
"manuscript Eq. (n) = label". Adapt the symbols to your response function; keep the discipline: one written definition
per quantity, numeric residual checks, the conversion factor tested to full precision.

## C1. Second-order DC conductivity and the single 1/2

- j_a = sum_bc sigma_abc E_b E_c (real fields).
- If the BZ integrand K^abc already contains both input orderings b <-> c, then sigma_abc = (q^3 / 2) int_k K^abc with
  q = -e (signed electron charge): exactly **one** overall 1/2. Do not halve the individual contributions as well.
- State whether a symmetrised index pair `a(bc)` means the exchange **sum** K_abc + K_acb or the average. In the
  example the paper used the sum while an older convention file wrote the average; mixing them gives factors of 2.
- A second-order derivation can contain several distinct factors of 1/2 (index-exchange symmetrisation, second-order
  Taylor coefficients); keep them separate and never merge them.
- History: in early engine versions the final SI conversion lacked the overall 1/2, so every material number was 2x
  the paper's definition (found in a convention audit). The frozen parent algebra uses sigma_frozen = 2 sigma_new;
  write such translations down.
- Normalisation cross-check against literature: compare with at least one published formula and record which one is
  matched (in the example: half of one published formula read literally, equal to another).

## C2. Natural units of the engine and the SI factor

- Engine: hbar = k_B = 1, energies in eV, lengths in A. The BZ integral returns J = Q / A_cell with
  Q = int over [0,1)^2 of I(u, v) du dv (reduced coordinates), A_cell in A^2.
- 2D SI: sigma [A m V^-2] = (q^3 / hbar)(c_L / c_E) J / 2 with q = -e, c_L = 1e-10 m, c_E = e J:
  sigma = -(e^2 / (2 hbar)) x 1e-10 m x J = **-1.2170674036396944e-14 A m V^-2 per natural-unit J**.
- Test the factor in the engine's test suite to 1e-14 relative (a preflight test); use one named constant everywhere
  (e.g. `SIGMA_PER_J`); never retype it.
- The sign is negative because q^3 = -e^3: a positive J is a negative sigma. Plots and tables use sigma with this sign.

## C3. Sheet (2D) units and derived quantities

| quantity | unit (2D) | definition |
| --- | --- | --- |
| sigma_abc | A m V^-2 | j [A/m] = sigma E^2 [V^2/m^2] |
| B_abc (BCD limit) | A m V^-2 eV | lim Gamma -> 0 of Gamma sigma_abc; independent BZ integral |
| fitted coefficient (e.g. a slope in Gamma) | sigma unit per unit of the fit variable | fit window stated with every value |
| n | cm^-2 | spin 2, both valleys |

- 3D would need a volume instead of an area; the converter takes the spatial dimension explicitly.

## C4. Broadening, lifetime and mobility

- Gamma is the half width at half maximum of the Lorentzian broadening; the corresponding lifetime is **tau = hbar / (2 Gamma)**.
- Mobility mu_e = e tau / m_c = e hbar / (2 Gamma m_c), i.e.
  **mu_e [cm^2 / V s] = 578.84 / (Gamma [meV] x m_c / m_e)**, where 578.84 = mu_B / (1 meV) in cm^2 / V s and
  mu_B = e hbar / (2 m_e) [derived].
- Unit check with synthetic inputs: Gamma = 1 meV, m_c = 0.1 m_e gives tau = 3.29e-13 s and mu_e = 5.79e3 cm^2 / V s.
- Use the same tau and m_c in every derived quantity (e.g. a Drude conductivity n e^2 tau / m_c).

## C5. Cyclotron mass from the pocket area

- m_c = (hbar^2 / 2 pi) dA/dE, A = T = 0 pocket area of one valley at E_F (count grid cells below/above E_F in a box
  around the band edge, finite difference in E_F). Holes: E_F < 0 measured from the VBM.
- Numerical settings of the example: box half-width 0.02 (fractional), 1600^2 cells.
- Two discretisations of dA/dE differed by 0.2 %: a 750^2 grid over a valley box of half-width 0.012 (fractional)
  with a +-2 meV central difference, and the pocket tool's 1600^2-cell box of half-width 0.02. Choose one and state
  it. An earlier value came from the superseded Wannier model and had to be replaced.

## C6. Fillings

- Electrons: E_F = mu - CBM; holes: E_F = mu - VBM (negative). CBM/VBM from a dense search on the model actually
  integrated. Record mu to full float precision.
- E_F printed by grid-based tools differs slightly (9.98 vs 10 meV: the grid misses the true minimum by 0.02 meV); the
  defined value is the one from the edge search.
- Carrier density with spin 2 and both valleys; holes count 1 - f below the VBM band
  (run_management.md R12).

## C7. Delta_FS: define it exactly, it is easy to get two values

- Definition used in the paper: the minimum, over the Fermi contour, of the gap from the band at the Fermi level to its
  neighbouring bands (delta -> 0).
- Package tool: minimum over a shell abs(E_c - mu) < 2 meV on a 400^2 grid per valley.
- Where the direct gap grows with energy across the shell (as in graphene/hBN), the shell minimum is lower than the
  contour value, here by 3-5 %; anything derived from Delta_FS moves by the same amount. Where the gap barely varies
  across the shell, the two agree closely.
- Rule: state the definition (contour vs shell width) next to every Delta_FS; converge the shell width to 0 or compute
  on the contour; do not mix tables.
- It recurred in a later analysis script that recomputed Delta_FS with the shell definition, and its ratios disagreed
  with the paper. Read Delta_FS, and every derived scale, from the one record the paper uses; never recompute it in a
  new script.
- **Source**: the project's run notes; the project's methods record.

## C8. Crossover scales

- Define every derived scale exactly: the normalised quantity, the threshold, and "first Gamma where" the threshold
  is reached.
- Interpolate by PCHIP in log Gamma between bracketing computed points (6 per decade in the example).
- Keep the definition next to every value.
- **Source**: the project's crossover-scale notes.

## C9. Contribution names

- If the response is decomposed into named contributions, each name must mean the same integrand in code, tables and
  text. Validate the scan kernel against the engine bitwise (the project had two validation scripts for this).

## C10. Strain and structure conventions

- Write the deformation gradient: graphene/hBN F(s) = [[1 + s, 0], [0, 1]] on the relaxed lattice (no Poisson
  contraction, z and vacuum unchanged, atoms relaxed at fixed lattice); MoS2 A'(s) = (I + eps(s)) A0 with
  eps(s) = s [[1, 0.31], [0.31, -0.17]].
- Check lattice vectors after strain: hBN 1 %: abs(a1) = 2.5048 A, abs(a2) = 2.4862 A, angle 120.25 deg.
- Record whether a lattice constant is optimised or a reference value (MoS2 a = 3.18 A is a reference value; the
  baseline relaxation fixed the lattice).

## C11. Equation references

- Quote "manuscript X, Eq. (n) = label"; keep old builds out of the live tree (their equation numbering differs from
  the current manuscript).

## C12. Residual checks for identities

- Treat an identity as a zero residual evaluated numerically (e.g. with a(bc) = exchange sum:
  sigma_a(bc) - 2 sigma_abc = 0 at DC; with the average: sigma_a(bc) - sigma_abc = 0; or a distribution function minus
  its closed form), not as a tolerance-based "close enough". Keep a small suite and run it after any change to kernels
  or conversions.

## Checklist

- [ ] One written definition per quantity (sigma, B, fitted coefficients, E_F, Delta_FS, crossover scales, tau, m_c).
- [ ] SI factor as one named constant, tested to full precision; sign of q included.
- [ ] Exactly one overall 1/2; exchange sum vs average stated.
- [ ] tau = hbar / (2 Gamma) and m_c definition stated wherever mobilities appear.
- [ ] Delta_FS definition (contour vs shell) stated next to every value.
- [ ] Equation references carry manuscript and label.
