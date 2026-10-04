# Provenance and packaging: records, frozen packages, one valid deliverable, archive

Goal of the example project (set by its author on 2026-10-01): exactly one latest, correct deliverable; superseded
versions archived with what was wrong; a private GitHub repository holding only the correct computation chain; the
failures kept locally to codify lessons (this skill).

## P1. Numbered run records with RUN.json

- Every finished computation becomes a numbered record folder `runs/<id>_<material>_<what>/` via a filing script. The
  script:
  - copies small outputs (qualified result, summaries, plans, tiles, logs, figures, the exact local run scripts);
  - compares the run's package file by file with the release tarball;
  - writes RUN.json; regenerates the index `runs/README.md` from all RUN.json files;
  - leaves caches in the raw run directory and records its path (`raw_run_dir`).
- RUN.json fields used: run_id, material, component, mu_eV, temperature_K, gamma_eV, status, converged,
  physical_result_valid, validation_failures, J_natural, J_error_bound, sigma_SI_A_m_per_V2, sigma_error_bound_SI,
  B_abc_SI_A_m_per_V2_eV, gamma_sigma_over_B, primary_vs_crosscheck_total, package (version, tarball sha256, release
  commit), config_sha256, timing, evaluations, raw_run_dir, conversion (the SI factor and its equation).
- Status vocabulary: CONVERGED (all checks pass), FAILED with `validation_failures` (e.g. "independent
  spectral/local feature checks failed"). Keep failed records; archive them with PROBLEMS.md.
- Scan records also carry: model name, E_F definition (and the option used for holes), Fermi scales, error-scale
  source (the scale file), tile layout source, pass history, wall times and new evaluations in a note.

## P2. Frozen engine packages

- Versioned source directory -> deterministic tarball + `.sha256` + RELEASE.md + ACCEPTANCE.json, tagged by a release
  commit. Inside: CHECKSUMS.sha256, SOURCE_HASHES.json, a hash scope file, frozen configs with their hashes.
- Acceptance from a clean unpack (final version): 512 file checksums, 580 Julia checks incl. a real worker smoke test,
  27 Python tests, preflight of both materials.
- Never patch a released package. A changed input is a new version (the last version change touched only the hBN
  inputs, mu and presets) or an overlay for analysis (run_management.md R13).
- Seeded caches allow bitwise reproduction across versions when the integrand files are byte-identical (a later record
  reproduced an earlier one bitwise). That is how a result from an archived version stays valid: reproduce it on the
  live version, archive the old one.

## P3. Deterministic tarball

```python
# sorted entries, root ownership, epoch mtimes, fixed modes, gzip without name/mtime
info = tarfile.TarInfo(arc); info.uid = info.gid = 0; info.uname = info.gname = ''; info.mtime = 0
info.mode = 0o755 if rel in executables else 0o644
# skip __pycache__, results/, .DS_Store, ._*
gzip.GzipFile(fileobj=f, mode='wb', mtime=0, filename='')
```
- Same source and same Python/zlib -> same sha256 (the project's release tarball tool).

## P4. Zip deliverables

- ZIP cannot store timestamps before 1980: files extracted from an mtime-0 tarball make `zipfile` raise. Use
  `zipfile.ZipFile(..., strict_timestamps=False)`.
- Basenames collide when files from several directories go into one folder: keep paths relative to the group's common
  directory (`inputs/<group>/<relative path>`).
- Write `inputs/MANIFEST.tsv` (copy, source path, sha256) and a `.zip.sha256` sidecar.
- Never include licensed files (POTCAR, VASP source/binaries) or large files (WAVECAR, CHGCAR, .mmn, .chk).
- Consumers (the paper scripts) read an unpacked copy and check the zip's sha256 first.
- **Source**: the project's deliverable zip builder; the project's engineering-lessons notes.

## P5. One valid deliverable; archive, do not delete, do not repair

- Live tree = the final chain only: theory notes, DFT parents + certified Wannier models, the current package, numbered
  releases and runs, deliverables. Everything superseded goes to `archive/` as it is (git mv), with `PROBLEMS.md`.
- Do not fix links or paths inside archived trees (effort spent on that was unwanted).
- Ask the owner before archiving anything that feeds paper figures.
- Root-level zips follow the same rule: one current bundle; older ones archived with a note.
- Moves outside the repository (raw run dirs, aborted runs) are listed in `MOVED.md` (date, from, to, why).
- **Source**: the project's deliverable and archive policy; the archive README.

## P6. PROBLEMS.md: what to write

```markdown
# <item>: archived <date>
- What it was (version, record, model) and what replaced it (path).
- What is wrong, with numbers and the check that showed it
  (e.g. "off grid it misses DFT by up to 0.12 eV within 0.3 eV of mu; CBM 9.8 meV too low").
- Which results depend on it (record ids) and whether their numerics are sound but the physics input is not.
- Statements elsewhere that were wrong because of it (e.g. "up to 84 meV" understated; true 0.40 eV).
- Whether anything in it is still valid (e.g. "the MoS2 part is byte-identical to the next version").
```
Separate "numerics sound, physics input wrong" (four records built on the superseded Wannier model) from "numerics
failed" (one certified run) and from "no error, superseded by an identical record" (one record). Examples: every
`PROBLEMS.md` in the project's archive.

## P7. Private GitHub export without the archive

The project's export script:
1. Refuse if tracked changes are uncommitted.
2. `git archive HEAD -- . ':(exclude)archive' | tar -x -C <export dir>`: a separate repository with its own linear
   history ("Sync with <repo> <rev>").
3. Symlinks that point into `archive/` would dangle on GitHub: replace them by copies of their targets.
4. `git add -A --force` in the export: files force-added in the source and matched by `.gitignore` would otherwise be
   skipped silently.
5. Create the repo as private if missing; **refuse unless visibility is PRIVATE**.
6. Attach the release tarball and the single deliverable zip to a GitHub release (`--clobber` replaces an older zip).
- The full history and `archive/` stay local. Keep the repository private until the owner decides otherwise; push only
  when asked.

## P8. Licensed and third-party material

- VASP source/binaries and POTCAR: never in git or deliverables. Store names, titles and sha256
  (a POTCAR metadata JSON), build recipes (`makefile.include`, `build.sh`, a `sed` fix for C23 timing prototypes).
- Keep build recipes in private storage (a `makefile.include` is derived from the arch/ templates of the licensed VASP
  distribution). If a recipe must be public, describe it in prose (compiler, flags, libraries, what a patch changes)
  and publish neither VASP source lines nor the makefile itself. POTCAR metadata is limited to titles/names and hashes.
- Third-party PDFs (journal papers, user guides) are not pushed (archived out of the theory folder on 2026-10-02).
- Record licenses of what is distributed (engine MIT, Wannier90 GPL-2.0; check the LICENSE of the version you use);
  unknown license -> say UNKNOWN and ask.

## P9. Toolchain provenance

- Versions, build flags, compiler, binary sizes and sha256, regression results (in a toolchain README).
- A tool rebuilt from source must reproduce a stored run before use (wannierization.md W12).

## P10. Equation references and conventions

- Cite equations by manuscript and label, not only by number: equation numbers differed between the old builds and the
  rewrite, and old PDFs in the live tree invited reading the wrong equation (archived 2026-10-02).
- Record convention translations explicitly (sigma_new = sigma_frozen / 2; conventions_and_units.md C1).

## P11. Data hygiene before packaging

- Validate CSVs: no NaN in data columns (an old toy-model CSV had NaN in four rows), no duplicated grid rows (one
  Gamma value listed twice), monotone grids, expected row counts.
- A script that writes outputs must write where the package expects them (an export script wrote to a non-existent
  `inputs/` and recorded the wrong operator source).
- **Source**: the archived problem report of the early toy-model package.

## P12. Verify the export, not the working tree

- **Symptom**: a package passes every check where it was built and fails in the copy you ship. On 2026-10-02 a new
  `*.zip` ignore rule kept two engine files pinned by the engine lock file out of the commit; `make check` passed in
  the working tree and failed in the exported reviewer repository ("engine drift").
- **Check**: run the package's own checks (and the paper audit, figure scripts, dataset builders) inside the exported or
  freshly cloned copy; compare `git status` there after the run (expect no changes).
- **Fix**: anchor ignore patterns (`/*.zip`, not `*.zip`); list ignored files before committing a new layout
  (`git status --ignored`); keep the assembler idempotent so a re-run with unchanged sources commits nothing.
- **Source**: the project's reviewer-repository assembler; the commit history of the replay repository.

## P13. General tools live outside project repositories

- Compilers, VASP, Wannier90 and POTCAR libraries are machine-wide (a tools folder with a README of versions, build
  recipes and sha256). A project records only the provenance (version, flags, hash, path). A toolchain kept inside the
  project was lost once in a repository rename (incident 30) and mixed licensed trees into the project.
- **Source**: the machine-wide tools README; the project's toolchain README.

## P14. Cloud-synced folders are volatile; compute in git working copies

- **Symptom**: files that scripts depend on vanish or change while a session works (2026-10-02: several
  packages disappeared from the cloud-synced paper folder, moved by another device or session).
- **Fix**: keep code, data records and the manuscript in a git working copy on local disk; exchange between machines
  only through git; resolve inputs through one paths module with explicit fallbacks and verify them by sha256.
- **Source**: the paths module of the reviewer repository; the manuscript project's workflow plan.

## P15. Make every record recomputable from its own job file, and test it box by box

- **Situation**: the job files of the filed scans held the complete final box layout (limits, targets, evaluation caps,
  initial subdivision) and all physics inputs, but also an absolute output folder, and the worker skips every box whose
  result file already exists there. "Rerun the job file" would fail on another machine and silently do nothing on the
  original one.
- **Fix**: a rerun tool that copies the job file with a fresh output folder (and refuses a non-empty one), selects a
  subset of boxes (by id, or the N cheapest), rebuilds the model overlay the record used, runs the workers and compares
  every box with the filed result: values and error estimate.
- **Result**: cheap boxes from every class of record reproduced bit for bit on the same machine (filling scans, hole
  filling, quadtree pocket leaves, pass-2 sub-boxes, model overlays, and a record filed with an older engine version
  whose kernel hashes were identical), and a complete 143-box record reproduced including its aggregate. A box filled
  entirely from a copied point cache also reproduced, which showed that the cache reuse had been sound.
- **Rule**: a deterministic integrand plus a job file that pins the final layout is a reproducibility guarantee only
  after a box-level rerun from the shipped repository has matched the filed values.

## P16. A run restarted with another error norm needs a scale history

- **Symptom**: rerun boxes of one record had identical values but different error estimates.
- **Cause**: the scan had been restarted with other error scales and kept the 156 boxes finished under the old norm.
  The norm drives the adaptive subdivision, so a box that subdivides would not even reproduce its value under the new one.
- **Fix**: a scale-history file in the record lists those boxes and the job file of the old norm (here derived from the
  box files' modification times, which matched the box count in the run log); the rerun tool uses that norm for them.
- **Rule**: when a restart keeps finished work under changed settings, write down at the time which units of work used
  which settings.

## P17. Ship the layout prior, not the superseded run it came from

- The scan layouts came from the evaluation counts of an archived certified run of a superseded model. Shipping its
  result files would ship superseded integrals. A small JSON with only the per-tile evaluation counts rebuilds the
  filed layouts exactly (box ids, limits and targets).

## P18. Session scratch space is temporary

- An analysis that later decisions depend on (a comparison of this project's tools with an upstream package) lived
  only in a session scratch file for a day. Move such results into the repository when they are made, with a date,
  the decisions taken on them, and a sensitivity note (what must not be posted).
- **Source**: the project's upstream-feedback record.

## Checklist

- [ ] Record filed by script; RUN.json complete; package compared file by file with the tarball.
- [ ] Release tarball deterministic; sha256 recorded; acceptance from a clean unpack.
- [ ] Exactly one live package and one deliverable; superseded items archived with PROBLEMS.md.
- [ ] Export excludes archive/, copies archive symlink targets, force-adds, refuses non-private.
- [ ] No licensed or large files in git, zip or release assets.
- [ ] Checks rerun inside the exported copy; `git status` clean afterwards.
