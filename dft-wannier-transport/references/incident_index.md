# Incident index: what actually went wrong, how it was caught, where it is written down

Only documented incidents (do not add invented ones). Sources are generic descriptions of the project's own records
(archived problem reports, run notes, methods record, engineering-lessons notes, run scripts). Cost = what it took to
undo.

| # | date | incident | how it was caught | cost | rule | source |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 2026-08 -> 2026-10-01 | hBN Wannier model = lowest 16 bands, no disentanglement, MLWF stopped at 200 steps; vacuum NFE states in the shell; complex gauge; 0.12 eV off-grid error; CBM 9.8 meV low | rerun from source (Omega 143.1 vs 153.9 A^2 from identical inputs) and new off-grid DFT | 2 package versions, 5 run records, deliverables and a paper section redone; the response changed sign and by more than an order of magnitude | wannierization W1, W4, W5, W8 | archived problem report of the superseded Wannier model |
| 2 | 2026-09-30 | TRS "projection" (H, A -> real part) adopted as the fix for E(k) != E(-k) | off-grid DFT: errors unchanged (0.117 eV); bands moved up to 0.19 eV on the mesh | the package version and its records archived | wannierization W7 | archived problem report of that package version |
| 3 | 2026-10-01 | TRS asymmetry quoted as "up to 84 meV" from valley-box sampling | whole-BZ random sampling: 0.40 eV (band 1) | documentation corrections | wannierization W6 | same problem report |
| 4 | 2026-10-01 | a TRS/DFT check compared the model with DFT only on the mesh and "found no errors" | off-grid DFT | deliverables of 2026-09-30/10-01 archived | wannierization W8 | archived problem report of the superseded deliverables |
| 5 | 2026-10-01 | spd N36 manifold for B/N/C: d character absent in the 64-band parent; complex gauge (Im H 87 meV, E(k) - E(-k) 0.80 eV) | engine check + TRS gate | 4288 s Wannier90 + aborted scan | wannierization W3; run_management R9 | README of the disentangled model; move log of archived runs |
| 6 | 2026-10-01 | default error scale of one component ~1e3 below its actual magnitude (hBN filling scans) | slow progress; pass-0 runs | two pass-0 scans moved to archive | bz_integration B3 | move log of archived runs |
| 7 | 2026-10-02 | same scale trap again in the strain series (~3e3) | inspection after 1 minute | 1 minute; stopped part in `aborted/` | bz_integration B3; run_management R8 | methods record; engineering-lessons notes |
| 8 | 2026-10-01/02 | Fermi pocket inside one box: ~2e4 evaluations x ~1 s on one worker | wall-time logs; pass 1 not converged | pass 2 for three scans; extra passes for the later low-filling scans | bz_integration B4, B6 | run notes; README of the Gamma-scan tools |
| 9 | 2026-10-01 | partial aggregate (148/149 boxes) 58x the final sigma | comparison with final | none (not reported) | bz_integration B5 | run notes |
| 10 | 2026-10-01 | one box at the 2e4 cap with 1.95x its share although total error 0.75 of budget | per-box convergence policy | pass 2 | bz_integration B6 | run notes |
| 11 | 2026-09-27 | preset budget ~1000x stricter than acceptance; feature checks failed | certified run FAILED | one package version | bz_integration B10 | release notes of the next package version |
| 12 | before 2026-09-22 | SI conversion missing the overall 1/2: material numbers 2x the paper's definition | convention audit | one engine version | conventions C1 | archived notes of the early engine version |
| 13 | 2026-10-02 | Fermi-scales tool counted the whole valence band for holes (hole density ~700x too large) | electron/hole mirror (n(-E_F) vs n(+E_F)) | tool fix (optional hole mode) | run_management R12 | methods record |
| 14 | 2026-10-02 | VASP 4 ranks 5x slower with scan workers running (E cores) | DFT wall time | DFT scheduler script | run_management R1 | strain-series DFT scheduler script |
| 15 | 2026-10-01 | nice did not protect the certified run | not recorded | SIGSTOP scheduler | run_management R3 | CPU scheduler script |
| 16 | 2026-10-02 | project folder briefly moved (about one minute); workers crashed opening cache files | worker logs "No such file or directory" | resume from caches (two scans and one pass 2) | run_management R5, R6 | run notes; resume script |
| 17 | 2026-10-02 | extra workers outlived the driver's aggregation | box count in the aggregation line | re-aggregation watcher | run_management R7 | engineering-lessons notes; watcher script |
| 18 | 2026-10-02 | scripted edits appended `# comment` after `;`-joined statements (3 scripts) | not recorded | re-edits | run_management R12 | engineering-lessons notes |
| 19 | 2026-10-02 | argparse rejected negative values in exponent form (`--x -1e-16`) | CLI error | use `--opt=value` | run_management R12 | filing notes |
| 20 | 2026-10-02 | strain s = 0 with "mirror" error scales: ~12 min per pocket sub-box | wall time per box | scale switch after 156/239 boxes | symmetry S7 | methods record |
| 21 | 2026-10-02 | an exact 3m symmetry relation violated by 2.3 % at s = 0; forbidden BCD 0.4 % of the strained value | symmetry checks; a two-band model satisfies the relation exactly | stated as ~2 % model uncertainty | symmetry S5 | paper handoff notes |
| 22 | 2026-10-02 | Delta_FS: package shell minimum vs paper contour definition differ by 3-5 % | paper scripts recomputed from data | noted; both kept with definitions | conventions C7 | run notes |
| 23 | 2026-10-02 | a handed-over functional-form claim was not supported by the data | recomputation by paper scripts | text corrected | bz_integration B12; paper_numbers N7 | run notes |
| 24 | 2026-10-02 | paper scripts still read superseded data (old hBN model, old records) | path grep after model change | scripts rewritten (round 6) | paper_numbers N4 | paper handoff notes |
| 25 | 2026-09-30 -> 10-01 | a scaling claim made from one filling | scans at further fillings | text corrected | paper_numbers N6 | manuscript project handoff notes |
| 26 | 2026-10-01 | packaging: force-added files skipped by `git add -A` in the export; symlinks into archive/ dangling; ZIP refused mtime 0; basenames collided | zip build error (mtime); others not recorded | `--force`, copy link targets, `strict_timestamps=False`, relative paths | provenance P4, P7 | engineering-lessons notes; export script |
| 27 | found 2026-10-01 | MoS2 `wannier90.chk` lost (only sha256) | provenance review | gauge cannot be re-checked | wannierization W11 | methods record, missing-information list |
| 28 | fixed by 2026-09-26 | toy CSV with NaN rows and a duplicated Gamma row; export script writing to a non-existent path | package rebuild review | refilled rows (9e-9 agreement), fixed script | provenance P11 | archived problem report of the toy-model package |
| 29 | 2026-10-02 | old manuscript PDFs in the live tree with different equation numbers | cleanup | archived | provenance P10 | archived problem report of the superseded theory files |
| 30 | 2026-10-01 | toolchain lost in a repository rename; rebuilt from archived sources | missing binaries | rebuild + regression | wannierization W12 | toolchain rebuild notes |
| 31 | 2026-10-02 | `*.zip` ignore rule dropped two engine files pinned by the engine lock file; checks passed in the working tree, failed in the export | running the checks in the exported reviewer repository | one recommit | provenance P12 | commit history of the replay repository |
| 32 | 2026-10-02 | files removed from the cloud-synced paper folder while a session worked there | missing sibling zip at run time | inputs re-pointed via a paths module + sha256 | provenance P14 | manuscript project workflow plan |
| 33 | 2026-10-02 | replay certificates belonged to an older manuscript version; the paper had moved on | display-by-display version map | version map; Wolfram rerun pending | paper_numbers N11 | replay package version map |
| 34 | 2026-10-02 | the scan driver still defaulted hBN B to the superseded model's value | code review while writing this skill | default removed, B required | bz_integration B3 | project commit history |
| 35 | 2026-10-03 | a record mixed two error norms (156 boxes kept across a restart); not written down at the time | box-level rerun: values identical, error estimates not | scale-history file | provenance P16 | the record's scale-history file |

## Patterns across incidents

- The costliest errors passed every check that existed at the time (on-mesh agreement, converged integrals). Each was
  found by a new, independent test: off-grid DFT, a rerun from source, a symmetry partner, a second filling, a
  recomputation from raw data. Add independent tests early; they are cheap compared with redoing records.
- Defaults encode the physics of the first case (error scales, B of an old model, electron-only densities). Every
  new material, filling sign or component is a new case: pass inputs explicitly and print the job before running.
- Most runtime losses were scheduling problems, not physics: pocket boxes on one worker, lock-step MPI on slow cores,
  priority not enforced, a moved folder. Caches and claims made all of them recoverable.
