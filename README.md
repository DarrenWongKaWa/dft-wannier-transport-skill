# dft-wannier-transport: a Claude Code skill

Engineering lessons from a finished first-principles transport project, packaged as a
[Claude Code](https://claude.com/claude-code) skill so that an agent (or a person) avoids the detours that
project took.

The chain it covers: VASP (PBE, PAW) -> Wannier90 (SMV disentanglement + MLWF) -> tight-binding H(R) + position
operator (get_AA_R) -> a response-function engine integrated over the Brillouin zone with adaptive cubature ->
parameter scans, certified runs, paper figures, and an audit that recomputes every number quoted in the manuscript.
Everything in the example ran on one 12-core workstation.

Most rules name a **symptom**, the **check** that detects it, the **fix**, and the kind of project record where it was
learned; the others are procedures stated directly. The rules are generic; the numbers (graphene/hBN, MoS2) are worked examples of the engineering situation.
The skill contains no physics results of the underlying study, only engineering and numerical-method lessons.

## Who it is for

- People building Wannier tight-binding models for transport, especially for slabs, monolayers and heterostructures
  (vacuum states, entangled manifolds, time-reversal checks, off-grid validation).
- People integrating Fermi-surface or interband quantities over the Brillouin zone (Berry-curvature dipole, Hall,
  shift current, linear or nonlinear conductivity) with small pockets and near-cancellation.
- People running long multi-worker campaigns on a single workstation, and people who must package results with
  provenance and audit the numbers in a manuscript.
- Claude Code users who want the agent to apply these checks automatically.

## Contents

```
dft-wannier-transport/
  SKILL.md                                    entry point: when to use, stage checklists, top pitfalls, run/report checklists
  references/wannierization.md                manifold and windows, vacuum states, convergence, realness/TRS, off-grid validation
  references/symmetry_and_selection_rules.md  point groups, strain, vanishing components, symmetry partners as checks
  references/bz_integration.md                small pockets, error scales, pre-splitting, cancellation, caches, certification
  references/run_management.md                local multi-worker campaigns: cores, threads, priority, resume, monitoring
  references/provenance_and_packaging.md      run records, frozen packages, deterministic archives, private export, archive policy
  references/paper_numbers.md                 audit scripts, negative controls, snapshots, narrative re-checks
  references/conventions_and_units.md         factors of 2, SI sheet units, Delta_FS, tau = hbar/(2 Gamma), mobility, cyclotron mass
  references/incident_index.md                the documented incidents with dates, detection, cost and source
```

## Install

Personal skill (available in all projects): copy or symlink the `dft-wannier-transport/` folder into
`~/.claude/skills/`. First clone this repository into a folder named `dft-wannier-transport-skill` (with
`git clone <repository URL> dft-wannier-transport-skill`) and run the commands below from the folder that contains it.

Option A, symlink (one editable copy; updates with `git pull`):

```bash
mkdir -p ~/.claude/skills
ln -sfn "$(pwd)/dft-wannier-transport-skill/dft-wannier-transport" ~/.claude/skills/dft-wannier-transport
```

Option B, copy (freezes a version):

```bash
mkdir -p ~/.claude/skills
cp -R dft-wannier-transport-skill/dft-wannier-transport ~/.claude/skills/
```

Use one option, not both. Before reinstalling or switching options, run `rm -rf ~/.claude/skills/dft-wannier-transport`
(this removes only the installed link or copy, not your clone); otherwise `ln -s` creates a nested link inside the
existing folder, and `cp -R` merges into the old copy and leaves stale files.

Project skill (one repository only): put the folder at `<repo>/.claude/skills/dft-wannier-transport/`.

Claude Code loads the skill when a task matches the `description` in `SKILL.md`, or on request ("use the
dft-wannier-transport skill"). The reference files are read on demand.

## Contributing a lesson

Add a lesson only when it comes from a real, documented incident. Write it in the same structure as the existing
rules:

- **Symptom**: what you saw (wrong number, slow run, failed check), with numbers.
- **Check**: the test that detects it, cheaply and before it costs anything.
- **Fix**: what resolved it, and what did not (a fix that only hides the symptom is a lesson too).
- **Source**: a short generic description of where it is documented (e.g. "run notes", "archived problem report").
  Do not include local paths, usernames or email addresses, private repository or folder names, project record IDs,
  licensed content (VASP source or patches that quote it, POTCAR files or their contents), or unpublished scientific
  results.

Put the rule in the matching file under `references/` with a numbered heading (e.g. `## W14. ...`), add a row to
`references/incident_index.md` (and update the incident count in the reference-file table of `SKILL.md`), and add a
one-line pitfall to `SKILL.md` only if it is among the most costly. Keep
`SKILL.md` under ~250 lines and check that every link and `#anchor` resolves. Do not invent incidents or provenance:
unknown stays UNKNOWN.

## License

MIT, see [LICENSE](LICENSE).
