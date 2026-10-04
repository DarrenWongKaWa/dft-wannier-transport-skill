# Brillouin-zone integration: small pockets, adaptive budgets, cancellation, caches

Engine of the example: Julia, HCubature (Genz-Malik) per box over the reduced zone [0,1)^2, 16x16 tiles, integrand =
vector of (contributions) x (components) x (Gamma grid), driven by a Python scan driver with Julia workers. Natural
units: energies eV, lengths A, hbar = k_B = 1 (conventions_and_units.md C2).

## B1. Size the Fermi pocket before choosing any layout

- **Symptom**: a uniform mesh, a default tile layout or a BZ map looks fine but never resolves the pocket.
- **Check**: k_F from the pocket area (A = pi k_F^2 per valley), fractional radius r ~ k_F / abs(b).
  hBN example: abs(b) = 4 pi / (sqrt 3 a) = 2.93 A^-1; at the lowest filling (10 meV above the band edge) r ~
  0.0013-0.0015. A 128x128 mesh (spacing 7.8e-3) cannot see it: a BZ response map on such a mesh is a diagnostic only.
  A 16x16 tile split 4x4 and again 4x4 gives sub-boxes of 3.9e-3, which still hold the whole pocket at fillings
  <= 20 meV.
- **Rule**: compare the pocket diameter with the smallest box of the planned layout; if one box holds the pocket,
  it will dominate the wall time (B4).
- **Source**: the project's paper handoff notes; the project's pocket-area analysis; the project's engineering-lessons
  notes.

## B2. Adaptive cubature: how the budget was distributed

- Norm per box: max_i abs(I_i) / scale_i over the vector entries (contribution x component x Gamma); one HCubature call
  per box integrates all entries at once.
- Global rtol (3e-3 for paper scans, 1e-2 where only crossing points are used) is split over boxes in proportion to
  "shares" from a prior run's evaluation counts (sum of shares = 1). The same counts decide which tiles are split 4x4
  ("heavy" > 2e4 evaluations) and serve as LPT (longest-processing-time-first) scheduling weights.
- maxevals per box (6000 pass 1 for MoS2; 2e4 typical; 4e4 in pass 2).
- A box is converged when its error <= its share of the target; a scan is converged when every box is
  (worst err/target <= 1.00). Total error under budget is not enough (B6).
- Choose rtol by use: crossing points of a normalised response (where it reaches a chosen threshold) moved only
  1-3 % with rtol 1e-2.
- **Source**: the README and driver of the project's Gamma-scan tools; the project's methods record.

## B3. Error scales per component: take them from a comparable cheap model

- **Symptom**: a component's target is ~1e3 too strict; the scan crawls or never converges. Happened twice: hBN
  filling scans on 2026-10-01 (the default scale of one component ~1e3 below its actual magnitude) and the strain
  series on 2026-10-02 (~3e3); the second time it was caught after 1 minute.
- **Cause**: the driver derived default scales for every component from one reference coefficient through a magnitude
  relation assumed in a code comment; for the example that relation did not hold.
- **Check before launch**: print job.json scales next to an estimate of each component's magnitude at a few Gamma
  (from a cheap model or a coarse grid). They must agree within ~10x.
- **Fix**: a scale file built from an earlier scan: scale = max over contributions of abs(J) per (Gamma, component),
  floored at 1e-5 x the largest scale of that component so that small values of a component do not demand absolute
  accuracy. Sources
  used: the N4 (p_z, 4-band, 15-40 min on 2 workers) model at the same filling; the production-strain scan for the
  strain series. A scale only distributes the error budget; it never changes an integrand value.
- **Stale defaults**: the driver still carried, as a built-in default, the B of the superseded Wannier model (wrong in
  sign and magnitude for the corrected one). Any run without an explicit B or scale file silently used it. Pass physics
  inputs explicitly and read job.json before starting workers.
- **Source**: the move log of the archived pass-0 runs; the project's methods record; the project's
  engineering-lessons notes.

## B4. Pre-split boxes that touch the Fermi pocket (quadtree)

- **Symptom**: all workers idle except one or two that grind a pocket box for hours. hBN pocket boxes needed ~2e4
  evaluations at ~1 s each (BigFloat kernels, 16 bands). In the certified hBN runs of one package version the two
  K/K' partitions each hit the 1e5-evaluation cap after ~2.1 h on one core per stage, while the other 254 partitions
  finished in ~50 min; adding ranks cannot shorten that (lower bound ~2 h per stage).
- **Fix** (driver options: pocket centre, pocket radius R, split N, pocket share, depth D):
  - every box within R of the band-edge position is split N x N before the run;
  - sub-boxes that still touch the pocket disk are split 2x2 again, D - 1 times (quadtree), so a small pocket does not
    end up inside one sub-box;
  - the sub-boxes that touch the disk get 90 % of the parent's error budget, the rest 10 %; the total is unchanged;
  - R = 1.5e-3 + sqrt(2) k_F / abs(b) (on the hexagonal lattice abs(dk)^2 >= abs(b)^2 (du^2 + dv^2) / 2).
- **When**: fillings <= 20 meV in hBN needed depth 3 (smallest box 9.8e-4) from the start; the later low-filling
  scans needed an extra pass otherwise. With the defaults used (heavy tiles split 4x4, then pocket split N = 4, share
  0.9), depth D gives a smallest box of 1/16 / 4 / 4 / 2^(D-1); D = 3 -> 9.8e-4. Rule of thumb (heuristic): smallest
  pocket box < pocket radius.
- **Source**: the README of the project's Gamma-scan tools (option added 2026-10-02); the project's methods record.

## B5. Cancellation between boxes

- **Symptom**: an intermediate aggregate is wildly off. With one quadrant of one pocket box missing (148/149 boxes),
  the transverse component at one Gamma was 58x the final value.
- **Consequences**:
  - never report, plot or reason from a partial aggregate;
  - the accuracy that matters is relative to the net value, so the cancelling pocket boxes dominate cost;
  - per-box relative tolerance on large cancelling pieces is the right target only if the scales come from the net
    (B3) and the shares give the pocket most of the budget (B4).
- **Source**: the project's run notes; the project's methods record.

## B6. Pass 2: split what did not converge, reuse every point

- **Symptom**: total error within budget but one box above its share. In one scan a box at the 2e4 cap had 1.95x its
  share while all boxes together used 0.75 of the budget. Policy: still unconverged.
- **Fix** (a pass-2 split script): converged boxes are copied; each unconverged box becomes 4 quadrants with a quarter
  of the target and initdiv 1. The parent's first subdivision (initdiv 2) is exactly these quadrants, so the parent's
  cache (copied to each quadrant) gives cache hits. Options: split factor, pocket-only, selected box ids, pocket depth.
  Then re-aggregate over all box results.
- **Source**: the project's pass-2 split script; the project's run notes.

## B7. Half-zone doubling (k to -k) only for TRS-symmetric models

- Tiles (u, v) and (15 - u, 15 - v) are partners. Integrate u + v < 15 plus the self-paired line u + v = 15 with
  u <= 7, then double. Exact only if E(k) = E(-k) and the TRS-even integrand is symmetric, i.e. the model is real
  (wannierization.md W6). With a TRS-broken model the doubling silently produces a different integral.
- Record the reconstruction rule in the result file ("half zone (u+v<15, and u+v=15 with u<=7) x 2 under k -> -k").

## B8. Point caches and checkpoints

- Memoise every integrand evaluation per box on disk (serialised per box). Write the box result file only when done.
- Benefits used in this project:
  - pass 2 and tighter targets reuse pass-1 points (14,000-20,026 cached points reused per scan);
  - resume after crashes (run_management.md R5);
  - bitwise reproduction: a later run reproduced an earlier certified run with **zero** new evaluations (2,158,898
    points from the seed cache), allowed because config, source and integrand-file hashes were identical. Key caches
    by these hashes.
- **Source**: the project's run notes and the RUN.json of the reproduction record.

## B9. Certify one anchor point, then cross-check scans against it

- Certified run: primary (initdiv 8) and an independent crosscheck (initdiv 7 plus a shift), rtol 1e-3, atol 1e-10,
  each contribution and the total checked separately; spectral/feature checks; a certificate. CONVERGED only if all
  pass. Example: 482,528 + 422,280 fresh points; primary vs crosscheck 1.1e-8 (natural units); 4 h 22 min on 10 ranks.
- Every scan includes the anchor Gamma and reports the difference to the certified value: 3.6e-8 (hBN scan) and
  6.5e-7 (MoS2 scan), natural units.
- **Source**: the project's methods record; the index of run records.

## B10. Preset budgets must follow the response magnitude

- **Symptom**: certified run FAILED with "independent spectral/local feature checks failed" (an early package version).
- **Cause**: preset partition budget ~1000x stricter than the acceptance budget.
- **Fix**: preset ~0.2x acceptance; re-derive when the model changes (the Wannier-model fix changed the response
  magnitude by more than an order of magnitude and moved the hBN presets from [2e-4, 2e-2, 2e-2] to
  [2e-4, 1e-3, 1e-3]); dry-run the feature check with the new plan before releasing.
- **Source**: the release notes of the package versions involved (including a feature-check pretest).

## B11. Grids: uniform is not converged, grid edges are offset, do not splice

- Toy model: uniform grids did not converge a BCD-type component; a clustered map k = u + c sin u (c = 0.8) converged
  at 48-64 points per direction (source: the manuscript project's handoff notes).
- One figure, one grid: an earlier figure spliced 512^2 and 1024^2 data; it was redone on 28 points of one 1024^2 grid,
  and the audit records the splice difference.
- A band extremum found on a grid is biased toward the band interior: the CBM comes out too high, the VBM too low
  (400^2 grid: CBM 0.02 meV high, so E_F printed 9.98 instead of 10 meV). Define E_F from a dense edge search; treat
  grid offsets as a known bias, not a new filling.
- **Source**: the archived notes of an early engine version; the project's methods record.

## B12. Limits and independent integrals as checks

- Clean-limit BCD check: Gamma x (the integrand term whose clean limit is B) / B -> 1 as Gamma -> 0 (the total
  Gamma sigma differs from B by O(Gamma) terms, so compare that term, or go to small enough Gamma), with B from a
  separate adaptive integral over K and K' boxes (half-width 0.04 for hBN, 0.06-0.09 for MoS2, rtol 1e-6, both
  valleys equal): agreement to 1e-5 (hBN, Gamma = 1e-4 eV) and to 2e-8 (MoS2 K box, high accuracy).
- Contributions that must vanish identically (symmetry_and_selection_rules.md S3) are checks too.
- Claims about the functional form of a response in Gamma (e.g. "linear"): check the relevant ratio across the fit
  window before quoting a fitted coefficient, and use the same fit window for every record you compare (fits over
  different windows differed at the percent level).
- **Source**: the project's run notes; the project's paper handoff notes.

## B13. Cost model (worked numbers, Mac mini M4 Pro, 1 worker = 1 core)

| item | cost |
| --- | --- |
| hBN N16 integrand point, scan mode (BigFloat kernels, 16 bands, full Gamma vector) | ~1 s |
| hBN N16 integrand point, certified single-Gamma run | ~0.08 s [derived: 1e5 evaluations in ~2.1 h (B4); ~905k points in 22 core-hours (B9)] |
| hBN pocket box, unsplit | ~2e4 evaluations, hours on one worker |
| hBN Gamma scan, 6 points/decade, rtol 1e-2-3e-3 | 25k-47k new evaluations, 2.5-7 h wall on 4-8 workers |
| certified hBN point (primary + crosscheck) | 22 busy core-hours (10 ranks x 4 h 22 min wall; ranks idle while the K/K' partitions finish) |
| N4 (p_z, 4 bands) scan | 15-40 min on 2 workers; use as scale proxy |

Estimate before launching: evaluations x seconds per evaluation (for the engine mode you will run) / workers, and
separately the longest single box.

## B14. A box-integrated limit is truncated: compare it once with the whole zone

- **Symptom**: a clean-limit BCD integrated over a valley box (half-width 0.06) was 0.07 % above the whole-zone
  integral, while the methods text claimed a 1e-6 integration tolerance. The box tolerance is not the truncation.
- **Fix/check**: integrate the limit once over the whole zone for each material and filling, state the truncation
  next to every box-based value, and widen the box until the difference is below the precision you quote.
- **Source**: the project's methods appendix (corrected).

## B15. Small-Gamma coefficients of a difference: fit the leftover offset

- **Symptom**: the order-Gamma slope of a difference of two computed responses with the same clean limit came out
  biased for one record. Their 1/Gamma terms cancel analytically, but a numerical residue delta/Gamma^2 survives and
  dominates at the smallest Gamma.
- **Fix**: fit delta/Gamma^2 + a + b Gamma + c Gamma^2 with the columns scaled to similar size (Gamma in meV), and
  report delta and a (both should be ~0) as checks. Take the reference value of each part from the run that
  produced that part.
- **Check**: compare the slope with a direct integral of the closed-form leading coefficient when one exists.
- **Source**: the project's slope-fit scripts and the record of that analysis.

## Checklist

- [ ] Pocket radius computed; smallest planned box smaller than the pocket radius near the band edge.
- [ ] Error scales per (component, Gamma) from a comparable run; job.json printed and compared with estimates.
- [ ] No driver defaults for physics (B, mu, T); all passed explicitly.
- [ ] Half-zone doubling only after the TRS gate.
- [ ] Caches keyed by config and source hashes; pass-2 path tested.
- [ ] Anchor Gamma included; difference to the certified value reported.
- [ ] Convergence judged per box; partial aggregates never used.
- [ ] Fit windows identical across compared records; functional form checked across the window; extrapolations
      labelled.
- [ ] Box-integrated limits compared once with the whole zone; truncation stated (B14).
- [ ] Small-Gamma slopes of differences fitted with the offset term; delta and a reported (B15).
