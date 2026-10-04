---
name: dft-wannier-transport
description: Engineering rules for first-principles response calculations - DFT (VASP) to Wannier90 (disentanglement, MLWF) to tight-binding with position operator to Berry-curvature, nonlinear or linear transport, integrated over the Brillouin zone with adaptive cubature, run as long local multi-worker campaigns, filed as numbered records, and quoted in a paper. Use when choosing a Wannier manifold or windows, handling slab or 2D vacuum states, checking realness/time reversal or off-grid DFT agreement, setting symmetry-allowed tensor components, Brillouin-zone integration over small Fermi pockets, setting error budgets, planning, scheduling, resuming or monitoring long local computation campaigns, packaging results with provenance, or writing and auditing numbers quoted in a manuscript (paper-number provenance). Worked examples come from a finished second-order response project on graphene/hBN and MoS2.
---

# DFT -> Wannier -> transport: engineering rules

Lessons of a finished project (VASP 6.3.0 PBE/PAW -> Wannier90 3.1.0 SMV + MLWF -> H(R) + get_AA_R -> Julia
conductivity engine with finite broadening Gamma and HCubature over the BZ -> Gamma scans, certified runs, paper audit;
all on a 12-core Mac mini). Most rules name a symptom, the check that detects it and the fix; the others are procedures stated directly. Numbers are worked
examples; the rules are generic for other materials and response functions (Berry-curvature dipole (BCD), Hall,
shift current, linear conductivity).

Sources in the references are generic descriptions of the project's own records (methods record, run notes, archived
problem reports, run scripts). They document where a lesson was learned; you do not need them to apply the rules.

## When to use

- Building or checking a Wannier model for transport (any material, especially slabs, monolayers, heterostructures).
- Any BZ integral of a Fermi-surface or interband quantity with small pockets, near-cancellation or many components.
- Planning or babysitting computations that run for hours on a workstation (multiple workers, MPI + serial jobs).
- Filing results, freezing packages, publishing a private repository, archiving superseded work.
- Writing, revising or auditing the numbers and methods statements of a manuscript.

## Stage checklists (decide before acting)

**1. DFT parent**
- NBANDS covers the target manifold plus the first states above it (64 for a 4-atom slab; vacuum states included).
- Vacuum and dipole correction recorded; ISYM and k mesh fixed for the Wannier NSCF; POTCAR by name + sha256 only.
- Plan the off-grid NSCF now: Wannier-mesh cell centres, rings around extrema, a band-edge patch, a band path.
- Rebuilt or new toolchain? Reproduce a stored SCF first (energy, E-fermi, target-band eigenvalues).

**2. Wannier model** ([wannierization](references/wannierization.md))
- Per-k projectability and sigma_min(A) of the candidate projections before MLWF. Failed models had sigma_min
  2e-4 (median) down to 7e-10, the good one 0.29; below ~1e-3 investigate before running MLWF.
- Entangled (band overlap, states with projectability < 0.5)? -> SMV disentanglement; frozen window below the first
  non-target state; outer window = all bands.
- Converge disentanglement and MLWF (conv_window > 0); rerun with another dis_mix_ratio; compare Omega, centres, H(R).
- Real H(R), A(R); max abs(E(k) - E(-k)) < 1e-5 eV over the whole BZ, all bands. Gate scripts on it.
- Off-grid error near mu (target: ~1 meV); band edges vs DFT; mu re-derived for this model.
- Bracket the manifold (smaller and larger) before trusting percent-level numbers.

**3. TB + position operator**
- H(R) from Wannier90; A(R) by get_AA_R with cross-checks (H rebuilt from chk, B1 weights, position block).
- Transpose the exported chk lattice; use_ws_distance with matching wsvec everywhere; keep .chk/.amn/.mmn + hashes.

**4. Response function** ([conventions](references/conventions_and_units.md), [symmetry](references/symmetry_and_selection_rules.md))
- One written definition per quantity; one named SI constant tested to full precision; sign of q; one overall 1/2.
- Point group of every structure; list allowed, forbidden and partner components; plan one forbidden control.
- Known limits as checks. Example: B = the clean-limit (BCD) coefficient, lim Gamma -> 0 of Gamma sigma
  ([C3](references/conventions_and_units.md#c3-sheet-2d-units-and-derived-quantities)), computed by an independent
  integral; check Gamma x (the integrand term whose clean limit is B) / B -> 1 as Gamma -> 0. The total Gamma sigma
  differs from B by O(Gamma) terms.

**5. BZ integration** ([bz_integration](references/bz_integration.md))
- Pocket radius vs smallest box; pre-split pocket boxes (quadtree) so no box holds the whole pocket.
- Error scales per component from a comparable cheap model; no driver defaults for physics inputs.
- Half-zone doubling only after the TRS gate; per-box caches keyed by config/source hashes.
- Certify one anchor point (primary + independent crosscheck); every scan reproduces it.

**6. Campaign** ([run_management](references/run_management.md))
- One thread per worker; workers <= free cores; lock-step MPI on performance cores only.
- Priority via SIGSTOP/SIGCONT scheduler, not nice; claims-based queue; resumable from caches.
- Nothing moves the tree while workers run; done = aggregation covers N/N boxes.

**7. Filing and packaging** ([provenance](references/provenance_and_packaging.md))
- Numbered record with RUN.json by script; deterministic tarball + sha256; one valid deliverable.
- Superseded -> archive/ with PROBLEMS.md; private export without archive/; no licensed files anywhere.

**8. Paper** ([paper_numbers](references/paper_numbers.md))
- Audit script recomputes every quoted number and asserts the string; negative controls; snapshot before edits.

## Top pitfalls (one line each)

1. "Lowest N bands" of a slab contains vacuum NFE states -> near-singular projections (sigma_min 7e-10), complex,
   irreproducible gauge, 0.12 eV off-grid error. Disentangle. [W1](references/wannierization.md#w1-lowest-n-bands-of-a-slab-or-2d-cell-is-usually-not-an-isolated-group)
2. MLWF stopped while still descending is a false minimum (complex WFs). Converge; rerun with other mixing. [W4](references/wannierization.md#w4-converge-mlwf-a-stopped-minimisation-is-a-false-minimum), [W5](references/wannierization.md#w5-reproducibility-test-of-the-gauge)
3. A symmetry projection (H -> Re H) restores E(k) = E(-k) and hides everything else; the response changed sign after
   the real fix. Fix the model instead. [W7](references/wannierization.md#w7-a-symmetry-projection-is-a-symptom-not-a-fix)
4. On-mesh agreement is exact by construction; only off-grid DFT measures interpolation. [W8](references/wannierization.md#w8-validate-off-grid-on-mesh-agreement-is-exact-by-construction)
5. A model's band edge is a model property: a 9.8 meV CBM error put "CBM + 10 meV" 0.2 meV above the true edge.
   Re-derive mu and budgets per model. [W9](references/wannierization.md#w9-band-edges-and-fillings-are-model-properties)
6. Orbitals absent from the parent DFT (spd for B/N/C) reproduce the failure; test sigma_min(A) first. [W3](references/wannierization.md#w3-do-not-add-orbitals-the-parent-dft-does-not-contain)
7. TRS checks sampled only near valleys understate asymmetry (84 meV vs 0.40 eV); sample the whole BZ, all bands. [W6](references/wannierization.md#w6-realness-and-time-reversal-check-everywhere-gate-automatically)
8. Default error scales assume one physics; one component's target was 1e3-3e3 too strict, twice. Take scales from
   a cheap comparable model; print the job file (job.json in the example) before launch. [B3](references/bz_integration.md#b3-error-scales-per-component-take-them-from-a-comparable-cheap-model)
9. A Fermi pocket inside one box = hours on one worker; more workers do not help. Pre-split with a quadtree. [B4](references/bz_integration.md#b4-pre-split-boxes-that-touch-the-fermi-pocket-quadtree)
10. Pocket boxes cancel: 148/149 boxes gave 58x the final value. Never use partial aggregates; judge convergence per
    box, not by the total. [B5](references/bz_integration.md#b5-cancellation-between-boxes), [B6](references/bz_integration.md#b6-pass-2-split-what-did-not-converge-reuse-every-point)
11. Half-zone doubling (k -> -k) is exact only for a TRS-symmetric (real) model. [B7](references/bz_integration.md#b7-half-zone-doubling-k-to--k-only-for-trs-symmetric-models)
12. Symmetry residuals are measurements: an exact symmetry relation violated by 2.3 % was a model (interpolation)
    error, confirmed by an exactly symmetric two-band model that satisfied it exactly. Report, do not symmetrise
    away. [S5](references/symmetry_and_selection_rules.md#s5-symmetry-partners-as-numerical-checks-the-list-used)
13. Lock-step MPI on efficiency cores ran 5x slower; macOS nice does not protect a priority run. Reserve P cores;
    SIGSTOP scheduler. [R1](references/run_management.md#r1-know-the-cores-keep-lock-step-mpi-on-performance-cores), [R3](references/run_management.md#r3-priority-macos-nice-is-not-enough-use-a-sigstopsigcont-scheduler)
14. Moving the project folder for one minute killed every worker that touched a file. Never move a tree with live
    workers; resume from caches. [R5](references/run_management.md#r5-resume-from-caches-after-any-crash), [R6](references/run_management.md#r6-never-move-rename-or-relocate-the-tree-while-jobs-run)
15. Electron-only tools on holes (hole density ~700x too large); argparse rejects `--x -1e-16`; scripted `# comment`
    after `;` kills statements. Mirror tests, `--opt=value`, comments on their own line. [R12](references/run_management.md#r12-scripted-edits-and-cli-pitfalls)
16. Factors of 2 and definitions: missing overall 1/2 doubled results; Delta_FS shell-minimum vs contour differ by
    3-5 %. Write one definition per quantity. [C1](references/conventions_and_units.md#c1-second-order-dc-conductivity-and-the-single-12), [C7](references/conventions_and_units.md#c7-delta_fs-define-it-exactly-it-is-easy-to-get-two-values)
17. After a model change the paper scripts still read old data and old mechanisms stay in the text. Grep data paths;
    recheck the narrative sentence by sentence. [N4](references/paper_numbers.md#n4-data-come-from-the-released-bundle-never-from-working-directories), [N5](references/paper_numbers.md#n5-after-a-model-change-re-check-the-narrative-sentence-by-sentence)
18. Packaging traps: `git add -A` skips force-added files in an export; symlinks into archive/ dangle; ZIP refuses
    mtime 0; basenames collide. [P4](references/provenance_and_packaging.md#p4-zip-deliverables), [P7](references/provenance_and_packaging.md#p7-private-github-export-without-the-archive)
19. Checks that pass in the working tree can fail in the copy you ship (an ignore rule dropped pinned files). Rerun
    the checks inside the export; anchor ignore patterns. [P12](references/provenance_and_packaging.md#p12-verify-the-export-not-the-working-tree)
20. Certificates belong to one manuscript version. Map later versions display by display; never re-pin hashes or copy
    verdicts. [N11](references/paper_numbers.md#n11-certificates-belong-to-a-manuscript-snapshot)
21. "Reproducible" holds only after a box-level rerun from the shipped repository matched the filed values; a restart
    that kept work done under other settings needs a written history. [P15](references/provenance_and_packaging.md#p15-make-every-record-recomputable-from-its-own-job-file-and-test-it-box-by-box), [P16](references/provenance_and_packaging.md#p16-a-run-restarted-with-another-error-norm-needs-a-scale-history)
22. A difference of two computed responses keeps a numerical residue of the terms that cancel analytically; fit it
    before quoting a small-Gamma slope. A box-integrated limit is truncated; compare it once with the whole zone.
    [B14](references/bz_integration.md#b14-a-box-integrated-limit-is-truncated-compare-it-once-with-the-whole-zone), [B15](references/bz_integration.md#b15-small-gamma-coefficients-of-a-difference-fit-the-leftover-offset)
23. Rewording a manuscript under an audit: protect the audited strings, keep displays, math, cites and numbers fixed
    by script, then run a cross-section consistency pass. [N13](references/paper_numbers.md#n13-rewording-a-manuscript-that-an-audit-reads)
24. Session scratch files vanish; keep analyses in the repository. zsh globs, Julia `3f2n`, `str.format` on CSS.
    [P18](references/provenance_and_packaging.md#p18-session-scratch-space-is-temporary), [R12](references/run_management.md#r12-scripted-edits-and-cli-pitfalls)

The full list of documented incidents with dates and costs: [incident_index](references/incident_index.md).

## Before you start a long run

- [ ] Model passed every gate: converged, reproducible, real, TRS < 1e-5 eV, off-grid error near mu known, band edges
      match DFT, mu derived on this model and written to full precision.
- [ ] Components: symmetry-allowed set plus one forbidden control; anchor point certified or planned.
- [ ] Physics inputs (mu, T, B (BCD coefficient), Gamma grid, components, rtol) explicit in the job file; job file
      printed and read.
- [ ] Error scales per component compared with expected magnitudes (within ~10x).
- [ ] Pocket radius computed; boxes touching it pre-split below the pocket radius.
- [ ] Cost estimate: evaluations x s/eval / workers, and the longest single box; compare with the time available.
- [ ] Caches, claims and results on local disk outside cloud sync; kill-and-resume tested on a small job.
- [ ] Thread variables = 1; workers <= free cores; P cores reserved for MPI; priority scheduler if needed.
- [ ] Nothing will move or rename the tree until the last worker exits; watcher aggregates after the last worker.
- [ ] Inspect after one minute (targets, first box counts); abort cheaply if wrong; archive aborted runs, do not delete.

## Before you report a number

- [ ] It comes from a filed record (RUN.json): converged, N/N boxes, worst err/target <= 1, package version + sha256.
- [ ] Independent confirmation: crosscheck run, anchor reproduction, a known limit (e.g. the clean-limit BCD check
      Gamma x (the integrand term whose clean limit is B) / B -> 1), or bitwise reproduction from caches.
- [ ] Symmetry zeros and partner relations evaluated; residuals stated as model uncertainty.
- [ ] Model uncertainty quoted where it matters (manifold bracket, symmetry residual).
- [ ] Units, sign (q = -e), the single 1/2, sheet units, and the definitions of E_F, Fermi-surface scales, crossover
      scales, tau and m_c stated.
- [ ] Scope: which strain, filling, temperature; extrapolations and fit windows labelled; no generalisation from one case.
- [ ] Recomputed from the released data by the audit script; string asserted in the text; negative control passed.
- [ ] Partial aggregates, superseded models and archived records never used as sources.
- [ ] A box-integrated reference (e.g. B) compared once with the whole zone; truncation stated.

## Working rules carried over from the project

- One valid version of everything; superseded items archived unchanged with PROBLEMS.md; never delete results.
- Export without archive/; keep the export private unless the owner decides otherwise; push only when asked;
  licensed files (VASP, POTCAR) never distributed.
- Ask before archiving anything that feeds paper figures; edit the manuscript only when asked; snapshot first.
- Do not invent incidents or provenance: unknown stays UNKNOWN.

## Reference files

| file | content |
| --- | --- |
| [references/wannierization.md](references/wannierization.md) | manifold choice, entangled vs isolated, vacuum NFE states, frozen windows, convergence, realness/TRS, gauge reproducibility, off-grid validation, get_AA_R build, manifold bracket |
| [references/symmetry_and_selection_rules.md](references/symmetry_and_selection_rules.md) | point groups, strain to break C3, vanishing components, relations between components, symmetry partners as checks, cost of symmetric zeros |
| [references/bz_integration.md](references/bz_integration.md) | pocket sizing, adaptive budgets, error scales, quadtree pre-split, cancellation, pass 2, half zone, caches, certification, grids, limits, cost model |
| [references/run_management.md](references/run_management.md) | cores and MPI, threads, SIGSTOP scheduling, claims queue, resuming, moving folders, aggregation, fail-fast, gates, wall-time logging, CLI pitfalls, overlays |
| [references/provenance_and_packaging.md](references/provenance_and_packaging.md) | RUN.json records, frozen packages, deterministic tar/zip, one deliverable, PROBLEMS.md, private export, licensed files |
| [references/paper_numbers.md](references/paper_numbers.md) | audit scripts, negative controls, snapshots, data paths, narrative re-check, generalisation, methods with citations |
| [references/conventions_and_units.md](references/conventions_and_units.md) | the single 1/2, SI factor, sheet units, tau = hbar / (2 Gamma), mobility, cyclotron mass, fillings, Delta_FS, crossover-scale definitions |
| [references/incident_index.md](references/incident_index.md) | 43 documented incidents: date, detection, cost, rule, source |
