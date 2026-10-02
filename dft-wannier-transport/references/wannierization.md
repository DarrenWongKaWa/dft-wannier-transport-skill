# Wannierization: manifold, windows, convergence, validation

Every rule: **symptom**, **check** (what detects it), **fix**, **example** (graphene/hBN 1 % strain, MoS2), **source**
(a generic description of the project record where the lesson was learned).

The single most expensive failure of the project lives here: a Wannier model that reproduced DFT on the mesh, passed
every on-mesh check, was used for five run records and two package versions, and was wrong by 0.12 eV near the Fermi
level; after the model was fixed the response changed sign and by more than an order of magnitude. Treat a Wannier
model as unvalidated until W1-W10 pass.

## Gates (all must pass before any transport run)

| gate | tool / quantity | good (hBN N16_DIS: 16 Wannier functions, sp, SMV-disentangled; naming in W13) | bad (old isolated N16) |
| --- | --- | --- | --- |
| projectability of every state in the frozen window | per-k sum over trial orbitals of abs(A_mn)^2 | >= 0.905 | ~1/3 of states in bands 9-16 < 0.5 |
| conditioning of projections | sigma_min(A(k)) over all k | 0.29 | 7e-10 (median 2e-4) |
| disentanglement and MLWF converged | `.wout` spread history, conv_window > 0 | converged, 7500 steps | stopped at 200 steps, still descending |
| gauge reproducible | rerun with another dis_mix_ratio | Omega 8.91389 vs 8.91393 A^2 | 143.1 vs 153.9 A^2 from identical inputs |
| real (spinless, TRS) | max abs Im H(R), max abs Im A(R) | 3.5e-8 eV, 1.1e-9 A | 32 meV |
| E(k) = E(-k) on random k, all bands | dense random sample, whole BZ | 1.4e-7 eV | 0.40 eV (band 1) |
| off-grid error near mu | non-SCF DFT off the Wannier mesh, abs(E - mu) < 0.3 eV | 1.2 meV | 0.12 eV |
| band edge | model CBM vs DFT patch at the same k | agree to the 0.1 meV print precision of OUTCAR | 9.8 meV too low |
| spreads and centres | per-WF Omega, centre position | 0.45-0.67 A^2, on atoms | centres in the vacuum (z = 4-5 A) |

A scripted gate stopped rejected models from reaching the integrator: after the engine's model check, the queue script
refused to scan when `max abs(E(k) - E(-k)) >= 1e-5 eV` (source: the manifold-check run's queue script).

---

## W1. "Lowest N bands" of a slab or 2D cell is usually not an isolated group

- **Symptom**: near-singular projections, Wannier centres in the vacuum, complex and irreproducible gauge,
  E(k) != E(-k), large off-grid errors. On-mesh errors stay tiny (1e-7 eV), so nothing looks wrong on the mesh.
- **Cause**: in cells with vacuum (slabs, monolayers, heterobilayers) nearly-free-electron (NFE) vacuum states drop
  into the energy range of the target bands. In graphene/hBN they start at mu + 3.51 eV, below the sp sigma* states
  (mu + 8.2 eV), so about a third of the states in bands 9-16 are vacuum states with sp projectability < 0.5.
  The "isolated" shell also overlapped band 17 in energy (band 17 min 6.46 eV < band 16 max 11.75 eV), separated
  only by a per-k gap of >= 36 meV.
- **Check** (before running MLWF):
  1. Per-k, per-band projectability onto the trial orbitals from `.amn`; list states below ~0.5 inside the intended
     window and their energies relative to mu.
  2. sigma_min(A(k)) over all k. Failed models: 7e-10 (median 2e-4) and 3.3e-6; working models: 0.29. Treat values
     below ~1e-3 as a red flag (heuristic from these cases, not a tested threshold): the initial gauge then amplifies
     numerical noise, differently at k and -k, which is how the old model broke TRS.
  3. Global overlap test: min of band N+1 over k vs max of band N over k. If they overlap, the group is entangled.
- **Fix**: Souza-Marzari-Vanderbilt disentanglement (PRB 65, 035109, 2001). Outer window = all computed bands
  (64 for the 4-atom cell), frozen window below the first non-target state (mu + 3.0 eV; at most 9 bands per k,
  all with sp projectability >= 0.905).
- **Source**: the README of the disentangled Wannier model; the archived problem report of the superseded isolated
  model; the project's methods record.

## W2. Frozen-window rules

- Put every state the observable samples near mu inside the frozen window (exact on the mesh there).
- Keep its top below the first state with poor projectability (vacuum NFE, other-orbital character).
- Count bands per k inside the frozen window: must be <= num_wann at every k.
- When a structure changes (strain series), shift both windows by the change of the SCF Fermi energy, then re-run all
  gates per model (source: the strain-series window script and the per-strain gate table in the methods record).
- Example: N4 (p_z only) used mu +- 2.5 eV; N18 (sp + 2 vacuum s orbitals) used up to mu + 4.5 eV so the first NFE
  band is reproduced exactly.

## W3. Do not add orbitals the parent DFT does not contain

- **Symptom**: the extended manifold fails the same way as W1.
- **Example**: spd model N36 for B/N/C. d character is absent in the 64-band parent: sigma_min(A) 3.3e-6 (spd),
  5.3e-5 (sp + C d), 4.5e-4 (sp + d_xz/d_yz). The MLWF gauge came out complex (max abs Im H(R) 87 meV,
  max abs(E(k) - E(-k)) 0.80 eV); even the disentangled subspace in the projection gauge had 1.2 meV Im H. Rejected
  after 4288 s of Wannier90; its scan was aborted and archived (with a line in the move log).
- **Check**: sigma_min(A) for the candidate projections before running MLWF (minutes, not hours).
- **Fix**: extend the manifold only with orbitals that have low-lying states in the parent (here: diffuse s orbitals
  in the vacuum 2.5 A outside each layer, which capture the NFE states; sigma_min(A) = 0.29).
- **Source**: the README of the disentangled Wannier model (manifold sufficiency section).

## W4. Converge MLWF; a stopped minimisation is a false minimum

- **Symptom**: complex Wannier functions; Omega differs between reruns.
- **Check**: spread history in `.wout` must have flattened; conv_window > 0 (the old run had conv_window = -1 and
  num_iter = 200). Marzari-Vanderbilt 1997 (PRB 56, 12847): for an isolated spinless TRS group, Wannier functions at
  the true minimum are real; complex WFs signal a false minimum.
- **Fix**: conv_tol 1e-10, conv_window 5, guiding_centres = T, enough iterations (7500 needed; 634 s single core).
  dis_conv_tol 1e-10.
- **Source**: the README of the disentangled Wannier model; the project's methods record.

## W5. Reproducibility test of the gauge

- **Check A (rerun from source)**: rebuild the toolchain, rerun DFT and Wannier90 from the archived inputs. If DFT
  eigenvalues (7.6e-9 eV), gauge-invariant A^dag A (1e-9) and Omega_I (5e-9 A^2) reproduce but Omega does not
  (143.1 vs 153.9 A^2), the gauge is ill-conditioned (W1). This was the only route that exposed the old model.
- **Check B (perturbed rerun)**: rerun with a different dis_mix_ratio (1.0 vs 0.5). Good: Omega 8.91389 vs
  8.91393 A^2, centres within 2.6e-4 A, H(R) within 2.9 meV per element, both real.
- **Source**: the regression check of the isolated-model protocol stored with the disentangled model; the project's
  engineering-lessons notes.

## W6. Realness and time reversal: check everywhere, gate automatically

- **Check**: max abs Im H(R) and max abs Im A(R) of the final tb file; max abs(E(k) - E(-k)) on the off-grid points
  plus ~2000 random k, **all bands, whole BZ**.
- **Pitfall**: sampling only near the valleys understated the asymmetry ("up to 84 meV"); the whole-BZ maximum was
  0.40 eV (band 1). Valley-box sampling is not a TRS test.
- **Gate**: refuse to integrate above 1e-5 eV. Half-zone integration (bz_integration.md B7) is exact only if this
  holds.
- **Source**: the archived problem report of the superseded package version; the manifold-check queue script.

## W7. A symmetry projection is a symptom, not a fix

- **Symptom**: model breaks TRS; tempting fix [H(k) + H(-k)^*]/2, i.e. H(R), A(R) -> real part.
- **What it did**: restored E(k) = E(-k) exactly but kept every other error: 0.117 eV off grid near mu, CBM 9.8 meV
  low, band gap at the valley ~15 % too small; on the DFT mesh it moved bands by up to 0.19 eV (2 meV next to mu).
  The response computed on the projected model differed in sign and by more than an order of magnitude from the one
  on the corrected model.
- **Rule**: if a model needs a projection to satisfy a symmetry the Hamiltonian has, the model is wrong. Diagnose
  with W1-W5. A projection may be used only as a diagnostic (how much does the observable move?), never as the
  production fix. The same holds for forcing C3 relations (symmetry_and_selection_rules.md S6).
- **Source**: the archived problem report of the superseded package version; the project's paper handoff notes.

## W8. Validate off grid; on-mesh agreement is exact by construction

- **Symptom**: "model matches DFT to 1e-7 eV" while the interpolation between mesh points is off by 0.1 eV.
- **Check**: non-SCF DFT (ICHARG = 11, same INCAR, charge from the SCF) at k points that are **not** on the Wannier
  mesh, computed through the production engine loader (the engine's model-check script):
  - all cell centres of the Wannier mesh (18x18 -> 324 points);
  - rings around band extrema (K, K', radius 0.004-0.035 fractional; 96 points);
  - a dense patch around the CBM (100 points);
  - the DFT band path (Gamma-M-K-Gamma, 180 points).
  Metric: max abs(E_model - E_DFT) for abs(E - mu) < 0.3 eV and inside the frozen window.
- **Example**: hBN N16_DIS 1.19 meV, MoS2 0.26 meV; old model 0.118 eV. An archived TRS/DFT check "found no
  errors" because it compared only on the DFT mesh.
- **Note**: OUTCAR prints eigenvalues to 0.1 meV; that is the floor of this test.
- **Plan the off-grid NSCF together with the Wannier NSCF** (cheap: 532 s on 4 ranks for hBN).
- **Source**: the interpolation table of the project's methods record; the archived problem report of the superseded
  deliverables.

## W9. Band edges and fillings are model properties

- **Symptom**: filling defined as "CBM + 10 meV" lands 0.2 meV above the true CBM because the model's CBM is 9.8 meV
  too low; carrier density and Fermi-surface scales are all off.
- **Check**: CBM/VBM by a dense search around the extrema of the model; compare energy and k with a DFT patch.
  Good: model and DFT CBM at the same k, agreeing to the 0.1 meV print precision.
- **Fix**: re-derive mu for every new model and record it to full float precision. Re-derive preset error budgets too
  (bz_integration.md B10): the response magnitude changed by more than an order of magnitude with the model fix.
- **Source**: the release notes of the corrected package version; the archived problem report of the superseded one.

## W10. Quote only checks made on the production artifact

- An old RMS summary file claimed 0.04 meV along the band path; a direct check of the production TB gave 0.7 meV (max
  in window). Cause never found; the number was dropped. Any accuracy number in a paper must come from a script that
  loads the exact file the engine loads (same loader, same WS convention).
- **Source**: the project's paper handoff notes.

## W11. Building H(R) + position operator (get_AA_R)

- H(R) from Wannier90's `_tb.dat`. A(R) from the checkpoint and the full `.mmn`: S = V^dag M V, AA += i w_b b S
  (postw90 formula, transl_inv = F), hermitise per k, Fourier transform.
- **Cross-checks** (all must hold; source: the README of the project's Wannier tools):
  - H(R) rebuilt from the checkpoint gauge V(k) and DFT eigenvalues vs Wannier90 H(R): 5e-8 eV (tb.dat prints E15.8);
  - b-vector weights from the B1 condition vs the `.wout` table: 4e-8 relative;
  - off-diagonal i w_b b S (before hermitisation) vs Wannier90's own position block: 5e-9 A;
  - hermiticity of H and A: 1e-13 eV, 0.
- **Pitfall**: `w90chk2chk.x -export` writes the lattice column-major ((lattice(i, j), i = 1..3), j = 1..3); transpose
  back to row vectors or every b vector is wrong (handled in the project's formatted-chk reader).
- Use `use_ws_distance = .true.` and load the matching `_wsvec.dat` in the engine and in every check.
- **Keep the checkpoint** (17 MB). The MoS2 `.chk` was lost (only its sha256 survived), so its gauge can no longer be
  rechecked. Keep `.chk`, `.amn`, `.mmn` (393 MB) outside git with sha256 in a build-metadata JSON.

## W12. Toolchain hygiene

- Run `wannier90.x` with `OPENBLAS_NUM_THREADS=1`; otherwise every process starts 12 BLAS threads.
- After rebuilding the toolchain, run a regression before trusting it: SCF energy and E-fermi, eigenvalues of the
  target bands, A^dag A and Omega_I against the archived run (hBN: bands 1-16 within 7.6e-9 eV).
- Record versions, build flags and binary sha256 (in a toolchain README). VASP and POTCAR are licensed: store recipes,
  names and hashes, never the files.

## W13. Manifold sufficiency: bracket the production manifold

- Build smaller and larger manifolds on the same DFT, each at its own CBM + E_F: N4 (p_z), N16 (sp, production),
  N18 (sp + vacuum s). Model names give the number of Wannier functions; they are unrelated to the rule IDs N1-N12 in
  paper_numbers.md.
- Result: for Gamma <= 0.1 eV, N4 -> N16 -> N18 changes the computed response by ~5 % then 1.6 %: converged; quote
  ~2 % manifold uncertainty at the working point. At Gamma = 1 eV both steps differ by +13 / +18 %, not monotonic: at
  large Gamma the response samples bands far from mu, so large-Gamma values are qualitative only.
- Cheap first: N4 scans (4 bands) took 15-40 min on 2 workers and also served as the error-scale proxy
  (bz_integration.md B3).
- **Source**: the manifold-check run record; the README of the disentangled Wannier model.

## Checklist (copy into the run notes)

- [ ] NBANDS of the NSCF covers the outer window and the first states above the target manifold.
- [ ] Per-k projectability and sigma_min(A) computed for the candidate projections.
- [ ] Entangled? (band overlap, low-projectability states) -> disentangle; frozen window justified by numbers.
- [ ] Disentanglement and MLWF converged; spreads and centres sane.
- [ ] Second run with perturbed mixing reproduces Omega, centres and H(R).
- [ ] Real H(R), A(R); max abs(E(k) - E(-k)) < 1e-5 eV over the whole BZ, all bands.
- [ ] Off-grid DFT error near mu (cell centres, extremum rings, edge patch, band path).
- [ ] Band edges match DFT; mu re-derived for this model and recorded to full precision.
- [ ] tb + get_AA_R cross-checks pass; checkpoint and large files kept with hashes.
- [ ] Manifold bracket planned (at least one smaller, one larger manifold).
