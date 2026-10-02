# Run management: long local campaigns on one workstation

Machine of the example: Mac mini M4 Pro, 12 cores = 8 performance (P) + 4 efficiency (E), 24 GB, macOS; no cluster.
Campaign of 2026-10-01/02: one certified run (10 ranks), ~20 Gamma scans, DFT and Wannier90 for three strains, up to
19 workers sharing 12 cores. Raw run directories (with caches) lived in a local runs folder outside the repository;
filed records lived in the repository.

## R1. Know the cores; keep lock-step MPI on performance cores

- **Symptom**: VASP on 4 MPI ranks ran 5x slower while scan workers were also running.
- **Cause**: MPI ranks run in lock step; one rank scheduled on an E core slows all of them.
- **Fix**: while DFT runs, keep total compute load <= number of P cores (8). The strain-series scheduler allowed
  `max(0, 8 - 4 - running wannier90.x)` scan workers while `vasp_std` ran and stopped the rest; it exited (resuming
  all) when the chain logged "DFT done".
- `taskpolicy -b` (background, E cores only) starves completely when the P cores are full; not a priority tool.
- **Source**: the strain-series DFT scheduler script; the project's engineering-lessons notes.

## R2. One thread per worker, always

- Set for every Julia/Python/Fortran worker: `JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
  OMP_NUM_THREADS=1`, and `BLAS.set_num_threads(1)` inside Julia. Wannier90 otherwise starts 12 OpenBLAS threads per
  process; VASP with `OMP_NUM_THREADS=1 mpirun -np 4`.
- Count workers, not processes: budget = cores, each worker = 1 core.

## R3. Priority: macOS nice is not enough; use a SIGSTOP/SIGCONT scheduler

- **Symptom**: `nice`d scan workers still competed with the certified run for cores (macOS nice does not protect an
  HPC-style run).
- **Fix** (a small CPU scheduler script): every 60 s compute
  `budget = cores - (live priority ranks) - (other busy compute processes: julia, vasp_std, wannier90.x with %CPU > 40)`;
  order the managed workers by priority; `kill -CONT` the first `budget`, `kill -STOP` the rest. A stopped worker
  keeps its claimed box and loses nothing. Log only when the state line changes; exit when the priority job has
  finished and nothing is managed.
- Side effect to remember: box wall times include stopped time (R10).

## R4. Dynamic work queue with claims; add workers at any time

- Box claimed by atomic `mkdir claims/<box_id>` (first worker wins); a box is done when `boxes/<box_id>.json` exists;
  workers skip done and claimed boxes. Static LPT assignment is used only for the initial balance.
- Freed cores join a running job with new worker indices (an add-workers script taking job dir, package, count and
  first index).
- **Source**: the dynamic mode of the project's scan worker.

## R5. Resume from caches after any crash

1. Remove stale claims: every `claims/<id>` without `boxes/<id>.json`.
2. Restart workers with the same job.json; they skip finished boxes and reuse the per-box point cache.
3. Re-run aggregation after the last worker exits.
- **Example**: a resume script restarted two scans and one pass 2 after the crash in R6; no finished box and no
  cached point was lost.
- Test kill-and-resume on a small job before a long campaign.

## R6. Never move, rename or relocate the tree while jobs run

- **Symptom**: on 2026-10-02, for about one minute, the project folder was not at its path. Every worker that opened a
  file in that window died ("No such file or directory" on its cache file): 3-4 workers each in two scans and one
  pass 2.
- **Rules**:
  - before any `mv`, rename, repository restructuring or sync-tool action, check `pgrep -fl 'scan_worker|vasp_std|wannier90.x|julia'`;
  - run directories live outside cloud-synced folders (some sync clients keep files as on-demand placeholders and
    download them on first read; bulk reads there are slow);
  - workers use absolute paths (they did; that is why a move kills them instead of writing elsewhere);
  - when tools move (the toolchain moved to a machine-wide tools folder on 2026-10-02), scripts written earlier keep
    the old paths: note the move in the README, keep a compatibility note, do not edit archived scripts.
- **Source**: the project's run notes (interruption section); the toolchain README.

## R7. A scan is done only when its aggregation covers every box

- **Symptom**: the driver aggregated while extra (added) workers were still running; the summary line showed fewer
  boxes than expected.
- **Check**: the aggregation line `N/N half-zone boxes, N converged, worst err/target <= 1.00`. Anything else is not
  a result (and partial sums can be 58x off, bz_integration.md B5).
- **Fix**: a watcher that waits until no process references the job and then aggregates
  (`while pgrep -f "<job>/job.json" > /dev/null; do sleep 30; done; <driver> --aggregate <dir>`).
  Put the loop in a script file (not `sh -c '...'`), or use a pattern that cannot match the watcher itself: on Linux
  (procps) pgrep does not exclude its parent shell, so a `sh -c` watcher matches its own command line and never ends.

## R8. Fail fast: look at the first minute

- Read job.json (mu, B, scales, Gamma grid, components, rtol) before starting workers.
- After ~1 min: first box evaluation counts and error ratios. If targets look 1e3 off, stop, fix, restart. The second
  occurrence of the scale problem cost 1 minute instead of a pass; the stopped part went to an `aborted/` folder of
  the run.
- Aborted or superseded run directories are moved to an archive folder with a line in a `MOVED.md` (date, from, to,
  why), not deleted.

## R9. Chain long pipelines with explicit gates

- Pattern used for every new model (a queue script per model check):
  wait for `W90_STATUS.txt` -> build tb (exit on failure) -> engine checks -> **TRS gate** (exit if
  max abs(E(k) - E(-k)) >= 1e-5 eV) -> overlay package -> B integral -> error scales -> scan.
- Every step logs `[timestamp] step result` to one queue log; each DFT step writes `START_TIME`, `END_TIME`,
  `RUN_STATUS.txt` (exit code, wall seconds, ranks).
- `set -uo pipefail`; check exit codes; never let a later step run on a failed earlier one.

## R10. Log wall time and evaluations; know what box_seconds mean

- Per record: wall-clock start/end per pass, number of workers, new evaluations, cached points reused. These go in the
  RUN.json note (provenance_and_packaging.md P1).
- `box_seconds` (wall time per box) overestimates cost: it includes SIGSTOP time and oversubscription (19 workers on
  12 cores). Report evaluations (and seconds per evaluation measured on an idle core) as the cost measure.
- Typical wall times (2026-10-01/02): hBN DFT SCF 46 s, NSCF 64 bands 104 s, LWANNIER90 99 s, off-grid 532 s (4 ranks);
  Wannier90 N16_DIS 634 s, N36 4288 s (single core); certified hBN point 4 h 22 min (10 ranks); Gamma scans 2.5-7 h.

## R11. Environment hygiene for packaged engines

- Precompile and preflight after clearing `SLURM_PROCID`, `SLURM_NTASKS`, `PMI*`, `OMPI*`; otherwise precompilation
  behaves differently inside an allocation (fixed in a later package version).
- Local runs replace `srun` by a small launcher with the same rank environment, so the package that runs locally is
  byte-identical to the released one (513 files compared for the certified run).
- **Source**: the release notes of the package version with the fix; the project's run notes.

## R12. Scripted edits and CLI pitfalls

- **Comment after `;`**: a scripted `str.replace` that appends `# comment` to a line holding several `;`-separated
  statements comments out the statements after it. Happened three times on 2026-10-02 (two plotting scripts and the
  record-filing script). Put comments on their own line; after any scripted edit, re-run the script and diff its
  outputs.
- **Negative values in argparse**: `--x -1e-16` fails with "expected one argument" (argparse's negative-number test
  has no exponent form; checked with CPython 3.9 and 3.12, newer versions may differ); `--x -0.010` works. The
  version-independent rule: always write `--x=-1e-16`, `--opt=-10`.
- **Electron-only tools on holes**: a Fermi-scales tool summed f over the whole valence band for hole fillings (hole
  density ~700x too large). Check: where the bands near the edges are nearly electron-hole symmetric,
  n(-E_F) ~ n(+E_F) (this held after the fix). Fix: an optional hole mode counting 1 - f of the bands up to the VBM
  band.
- **Source**: the project's engineering-lessons notes; the project's methods record (hole density fix).

## R13. Variants as overlay packages, never edits of the frozen package

- For a manifold check or a strain series: unpack the release tarball into the run directory, replace only
  `inputs/<material>/` (tb, wsvec), rewrite MODEL.json with new hashes and `notes: "OVERLAY ONLY (not a release)"`.
- The frozen package stays bit-identical; the record says which inputs were overlaid.

## Pre-launch checklist (long run)

- [ ] Model passed all gates (wannierization.md); mu, T, B, Gamma grid, components explicit in job.json.
- [ ] Error scales checked against expected magnitudes; pocket boxes pre-split (bz_integration.md).
- [ ] Cost estimate: total evaluations x s/eval / workers, and the longest single box.
- [ ] Thread variables set; worker count <= free cores; P cores reserved for lock-step MPI.
- [ ] Priority scheduler running if a priority job shares the machine.
- [ ] Claims, caches and box files on local disk outside cloud sync; enough disk.
- [ ] Kill-and-resume tested on a small job; resume script ready.
- [ ] Nothing will move the tree (no repo restructuring, no sync relocation) until the last worker exits.
- [ ] Logs with timestamps; watcher that aggregates after the last worker; first-minute inspection planned.
