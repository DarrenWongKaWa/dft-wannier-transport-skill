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
  scripts/trs_gate.py                         time-reversal gate for a Wannier90 model file (rule W6), writes a certificate
  scripts/preflight.py                        checks a job file before a scan starts (rules W6, B7, B3, S8)
  scripts/live_workers.py                     refuses a move or a rename while worker processes are alive (rule R6)
  hooks/hooks.json                            Claude Code hook: runs preflight.py before a Bash command that starts a scan
  .claude-plugin/plugin.json                  plugin manifest: Claude Code loads the folder as a plugin, with the hook
tests/test_gates.py                           must-fail controls for the three scripts (synthetic models)
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

The folder is also a Claude Code plugin, because it contains `.claude-plugin/plugin.json`. Claude Code loads such a
folder in `~/.claude/skills/` as a plugin at the start of each session. Thus Option A and Option B also load the hook
(see [The hook](#the-hook)). To check, run `claude plugin list`. It shows `dft-wannier-transport@skills-dir` with the
status `loaded`. To stop the hook, run `claude plugin disable dft-wannier-transport@skills-dir`. To load the plugin
for one session from a clone, run `claude --plugin-dir dft-wannier-transport-skill/dft-wannier-transport`.

## Executable gates

A written rule did not stop a scan of a model that failed the time-reversal gate: 39 runs and 490 CPU-hours, and 24
runs ran again after the correction (incident 62 in the incident index). Thus the costliest rules are scripts. A
script that refuses prints the next steps.

| script | it refuses (exit code 1) when | it needs |
| --- | --- | --- |
| `trs_gate.py MODEL` | max abs(E(k) - E(-k)) is 1e-5 eV or more, at 2000 random k, for all bands, in the whole zone (rule W6) | Python 3.9, numpy |
| `preflight.py JOB` | one of the four checks below fails | Python 3.9 |
| `live_workers.py [--pattern REGEX]` | a process matches the pattern (default: the pattern of rule R6) | Python 3.9, pgrep |

Exit code 0 = pass. Exit code 2 = bad input. The scripts are in `dft-wannier-transport/scripts/`.

**`trs_gate.py`** reads a Wannier90 `_hr.dat` or `_tb.dat` file. Use the file that the engine loads. The gate also
reads `NAME_wsvec.dat` if it is next to `NAME_hr.dat` or `NAME_tb.dat`: different images for the two functions of a
Kramers pair break E(k) = E(-k) although H(R) is symmetric (rule W17). `--wsvec FILE` gives a different file. Use
`--no-wsvec` only if the engine ignores the images. The gate writes a certificate (`MODEL.trs_gate.json`) with the
SHA-256 of each file, the measured value, the tolerance, the number of k and the seed. The gate does not accept a
tolerance above 1e-5 eV or less than 2000 k.

**`preflight.py`** does four checks on a job file:

1. W6: the model file has a certificate, the gate passed, and the SHA-256 in the certificate is the SHA-256 of the
   model file now. The same applies to the wsvec file that the job names, or that is next to the model file.
2. B7: half-zone doubling is on only if check 1 passed.
3. B3: each error scale agrees with the expected magnitude within a factor of 10. This check runs only if the job
   gives the two tables. It ignores an expected magnitude of 0 (a value that vanishes by symmetry, rule S7).
4. S8: the job names a minimum of one symmetry-forbidden control component, and the component is in the job.

**`live_workers.py`** runs `pgrep -f` and refuses when a worker process is alive. Run it before a move or a rename:
`python3 live_workers.py && mv OLD NEW`. It ignores itself and the shells that call it (rule R20).

### The launcher first, the hook second

Put the gate in the launcher. Call `trs_gate.py` and `preflight.py` in the script that starts the workers, before
the first worker starts:

```bash
set -uo pipefail
GATES="$HOME/.claude/skills/dft-wannier-transport/scripts"
python3 "$GATES/trs_gate.py" "$MODEL" || exit 1
python3 "$GATES/preflight.py" "$JOB_DIR/job.json" || exit 1
```

The hook is the second line of defence. It compares the text of a command with the launch patterns. Thus it does not
see a scan that a wrapper script starts (`bash run_all.sh`). It also does not see a job file that the launcher writes
after the command starts.

### The hook

The `PreToolUse` hook in `hooks/hooks.json` runs `preflight.py --hook` before each Bash command:

1. If the command matches no launch pattern, the hook permits the command.
2. If the command matches, the hook looks for job files in the command text: a path to a file `job.json`, or a folder
   that contains `job.json`.
3. The hook does the four checks on each job file. If a check fails, the hook blocks the command with exit code 2,
   and Claude gets the refusal text.

- The hook loads with the plugin. It does not depend on a call of the skill.
- The hook needs `python3` on the PATH. It uses the standard library only.
- Claude Code 2.1.314 or later is necessary for the hook to see commands that the Monitor tool starts. Earlier
  versions run the hook for the Bash tool only.
- The hook takes the project folder from `CLAUDE_PROJECT_DIR`.

### Config file

A file `dft_gates.json` in the project folder changes the launch patterns and the keys of the job file. All keys are
optional. This example shows the defaults:

```json
{
  "launch_patterns": ["scan_worker"],
  "job_file_name": "job.json",
  "scale_factor": 10,
  "fields": {
    "model": "model",
    "wsvec": "wsvec",
    "certificate": "trs_certificate",
    "half_zone": "half_zone",
    "scales": "scales",
    "expected": "expected_magnitudes",
    "components": "components",
    "forbidden_control": "forbidden_control"
  }
}
```

- `launch_patterns`: regular expressions. A command that matches one of them starts a scan. Give one pattern for
  each command that starts workers in your project (launcher, add-workers script, pool script).
- `fields`: the key in the job file for each quantity. `"inputs.tb_file"` is the key `tb_file` in the object `inputs`.
- `model`, `wsvec`, `certificate`: paths, relative to the folder of the job file or to the project folder. Without a
  `certificate` key in the job file, the certificate is `MODEL.trs_gate.json`. Without a `wsvec` key, the preflight
  uses `NAME_wsvec.dat` next to the model file, if that file is there.
- `scales`, `expected`: objects `{component: number or list of numbers}`.
- An unknown key in `dft_gates.json` is an error, so that a typo does not remove a check.

### Tests

```bash
python3 -m pytest
```

The tests need numpy and pytest. Each script has a case that must pass and a case that must fail: a symmetric
synthetic model passes the gate, an asymmetric model fails, and the preflight refuses a certificate with a wrong hash.

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

After a change to a script, run `python3 -m pytest`. Keep a case that must fail for each check of each script.

## License

MIT, see [LICENSE](LICENSE).
