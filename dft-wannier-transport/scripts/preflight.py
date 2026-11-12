#!/usr/bin/env python3
"""Preflight check of a job file before a scan starts (rules W6, B7, B3, S8 of the dft-wannier-transport skill).

    python3 preflight.py JOB.json [JOB.json ...] [--project DIR]
    python3 preflight.py --hook        # Claude Code PreToolUse hook: reads the hook event (JSON) from stdin

Put the first form in the launcher, before the first worker starts. The hook is the second line of defence. It is on
only in a project that has the config file.

Checks:
  W6  The model file of the job has a certificate from trs_gate.py, and the gate passed. The SHA-256 values in the
      certificate are the values of the model file and of its wsvec file now.
  B7  Half-zone doubling is on only if the W6 check passed.
  B3  Each error scale has an expected magnitude, and no scale is more than 10x below it (a target that is too
      strict). The check runs only if the job gives the two tables.
  S8  The job names a symmetry-forbidden control component, and the list of components of the job contains it.

Hook: a command starts a scan if its program, or the script of an interpreter, matches a launch pattern. The hook
follows `cd`, `$PWD`, `sh -c` and the wrappers in WRAPPERS. Such a command must name its job file or its job folder,
or run in the job folder, and each job file must pass the checks. Otherwise the hook blocks the command.

Config file (optional): `dft_gates.json` in the project folder. Its keys are "launch_patterns" (regular expressions
for the programs or scripts that start workers), "job_file_name", "scale_factor" and "fields". "fields" gives the key
of the job file for model, wsvec, certificate, half_zone, scales, expected, components and forbidden_control
("a.b" = key b of object a). The defaults are in DEFAULTS.

Exit code: 0 = pass, 1 = refused, 2 = bad input. With --hook: 0 = permit the command, 2 = block the command.
Only the standard library is necessary (Python 3.8 or later).
"""
import argparse
import glob
import hashlib
import json
import math
import os
import re
import shlex
import sys

CONFIG_NAME = "dft_gates.json"
DEFAULTS = {
    "launch_patterns": ["scan_worker"],                  # regular expressions for the programs that start workers
    "job_file_name": "job.json",
    "fields": {                                          # name in this script -> key in the job file ("a.b" = nested)
        "model": "model", "wsvec": "wsvec", "certificate": "trs_certificate", "half_zone": "half_zone",
        "scales": "scales", "expected": "expected_magnitudes", "components": "components",
        "forbidden_control": "forbidden_control"},
    "scale_factor": 10.0,                                # rule B3
}
MAX_TOL_EV, MIN_NK = 1e-5, 2000                          # rule W6: not in the config file
GATE = "python3 " + shlex.quote(os.path.join(os.path.dirname(os.path.abspath(__file__)), "trs_gate.py"))
GATE_SCRIPTS = {"trs_gate.py", "preflight.py", "live_workers.py"}
FIX_MODEL = ("Correct the model. Then run the gate again (W7, W17). Do not use a k/-k average or a real-part "
             "projection. Do not edit the certificate.")
FIX_CONTROL = ("Add one component that the point group forbids to the list of components of the job. Write its name "
               "under the key of the control (S3, S8).")
FIX_SCALES = ("Take the scales from a comparable cheap model (B3). Give an expected magnitude for each component that "
              "has a scale. For a component that vanishes by symmetry, write 0 (S7).")
FIX_TABLES = (f"Write the two tables as objects: {{component: number or list of numbers}}. If a key has a different "
              f"name, set it in {CONFIG_NAME}.")
REFUSED = """PREFLIGHT REFUSED. Do not start this scan.
Correct each FAIL line. Then run preflight again.
Do not bypass this check. Do not use a k/-k average, a real-part projection or an edited certificate (W7, W17).
If you cannot correct a FAIL line, stop. Tell the owner of the project."""
NO_JOB = """This command starts a scan, but the hook finds no job file for it:
  {}
Name the job file or the job folder in the command as a plain path, or run the command in the job folder.
Do not move the launch into a wrapper script to pass the hook: the launcher must run preflight.py (see the README)."""

# Shell commands, for the hook
ASSIGN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
KEYWORDS = {"!", "{", "}", "if", "then", "else", "elif", "fi", "while", "until", "do", "done", "time"}
WRAPPERS = {                                             # program -> its options that take a value
    "nohup": "", "exec": "", "command": "", "nice": "-n", "env": "-u -S", "caffeinate": "-t -w",
    "taskpolicy": "-c -d -t -l -p", "sudo": "-u -g", "timeout": "-s -k", "stdbuf": "-i -o -e",
    "xargs": "-I -n -P -L -d -s -E", "srun": "-n -N -c -p -J", "uv": "--python --with --project",
    "mpirun": "-n -np -c -H -x --host --hostfile --bind-to --map-by", "mpiexec": "-n -np -c -H -x --host --hostfile"}
WRAPPER_WORD = {"timeout", "uv"}                         # one word after the options: a duration, or "run"
SHELL = re.compile(r"(sh|bash|zsh|dash|ksh)$")
INTERPRETER = re.compile(r"(python[0-9.]*|julia|Rscript|ruby|perl|node)$")
VALUE_OPTIONS = {"-t", "-p", "-J", "-L", "-W", "-X", "--threads", "--procs", "--sysimage", "--load"}
CODE_OPTIONS = {"-c", "-m", "-e", "-E", "--eval"}        # the next word is the program text or the module


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def find_wsvec(model):
    """The wsvec file of a model file: NAME_wsvec.dat next to NAME_hr.dat or NAME_tb.dat, else the only file
    *wsvec*.dat in the folder of the model. Return (path or None, number of files found). trs_gate.py uses it too."""
    near = re.sub(r"_(hr|tb)\.dat$", "_wsvec.dat", model)
    if near != model and os.path.isfile(near):
        return near, 1
    found = glob.glob(os.path.join(glob.escape(os.path.dirname(os.path.abspath(model))), "*wsvec*.dat"))
    return (found[0] if len(found) == 1 else None), len(found)


def load_config(project):
    """Return DEFAULTS with the changes of the config file. An unknown key is an error: a typo must remove no check."""
    cfg, path = dict(DEFAULTS, fields=dict(DEFAULTS["fields"])), os.path.join(project, CONFIG_NAME)
    if os.path.isfile(path):
        with open(path) as fh:
            user = json.load(fh)
        fields = user.pop("fields", {}) if isinstance(user, dict) else None
        if not isinstance(fields, dict):
            raise ValueError(f"{path} must be a JSON object, and \"fields\" must be an object")
        unknown = [k for k in user if k not in DEFAULTS] + [k for k in fields if k not in DEFAULTS["fields"]]
        if unknown:
            raise ValueError(f"unknown key in {path}: {', '.join(unknown)}")
        cfg["fields"].update(fields)
        cfg.update(user)
    patterns = cfg["launch_patterns"]
    if not isinstance(patterns, list) or not patterns or not all(isinstance(p, str) and p for p in patterns):
        raise ValueError("\"launch_patterns\" must be a list of regular expressions")
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as err:
            raise ValueError(f"launch pattern {pattern!r} is not a regular expression: {err}")
    if not all(isinstance(v, str) and v for v in list(cfg["fields"].values()) + [cfg["job_file_name"]]):
        raise ValueError("the values of \"fields\" and \"job_file_name\" must be strings")
    factor = cfg["scale_factor"]
    if isinstance(factor, bool) or not isinstance(factor, (int, float)) or not 1 < factor < math.inf:
        raise ValueError("\"scale_factor\" must be a number above 1")
    return cfg


def get(job, key):
    """Value of a key of the job file. "a.b" is key b of object a. None if the key is absent."""
    for part in key.split("."):
        if not isinstance(job, dict) or part not in job:
            return None
        job = job[part]
    return job


def resolve(path, bases):
    """Absolute path. A relative path is relative to the first base folder that contains it."""
    path = os.path.expanduser(path)
    for base in bases:
        if os.path.exists(os.path.join(base, path)):
            return os.path.join(base, path)
    return os.path.join(bases[0], path)


def check_gate(job, fields, bases):
    """Rule W6. Return (passed, text, next step)."""
    model = get(job, fields["model"])
    if not isinstance(model, str):
        return (False, f"the job file names no model file (key \"{fields['model']}\")",
                "Write the path of the model file into the job file. If the key has a different name, set it in "
                f"{CONFIG_NAME}.")
    model = resolve(model, bases)
    if not os.path.isfile(model):
        return False, f"the model file is not found: {model}", "Correct the path in the job file."
    ws = get(job, fields["wsvec"])
    named = isinstance(ws, str)                          # the job names the wsvec file that the engine loads
    ws = resolve(ws, bases) if named else find_wsvec(model)[0]
    run = f"Run the gate: {GATE} {shlex.quote(model)}" + (f" --wsvec {shlex.quote(ws)}" if named else "")
    cert_path = get(job, fields["certificate"])
    cert_path = resolve(cert_path, bases) if isinstance(cert_path, str) else model + ".trs_gate.json"
    try:
        with open(cert_path) as fh:
            cert = json.load(fh)
        asym, anti = float(cert["max_asym_eV"]), float(cert["max_antihermitian_eV"])
        tol, nk = float(cert["tol_eV"]), int(cert["nk"])
        if cert["gate"] != "W6-trs":
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        return False, f"there is no valid gate certificate at {cert_path}", run
    if cert.get("model_sha256") != sha256(model):
        return (False, "the SHA-256 of the model file does not agree with the certificate. The model file changed "
                "after the gate, or the certificate is from a different model", run)
    if cert.get("no_wsvec") is True and not named:       # the gate was told that the engine ignores the images
        ws_ok = cert.get("wsvec_sha256") is None
    elif ws is None:
        return (False, "the job names no wsvec file, and the folder of the model has no single wsvec file (W17)",
                f"Write the path of the wsvec file into the job file (key \"{fields['wsvec']}\"). If the engine "
                "ignores the images, run the gate with --no-wsvec.")
    else:
        ws_ok = os.path.isfile(ws) and cert.get("wsvec_sha256") == sha256(ws)
    if not ws_ok:
        return (False, "the wsvec file is not the wsvec file of the certificate. The images changed after the gate, "
                "or the gate read a different wsvec file (W17)", run)
    if cert.get("passed") is not True or not asym < tol or not anti < tol:
        what = (f"max |E(k) - E(-k)| = {asym:.2e} eV" if anti < tol else
                f"H(k) is not Hermitian, max |H(k) - H(k)^dagger| / 2 = {anti:.2e} eV")
        return False, f"the model FAILED the time-reversal gate: {what}, limit {tol:.1e} eV", FIX_MODEL
    if tol > MAX_TOL_EV or nk < MIN_NK:
        return False, f"the certificate is from a weaker test than rule W6 (limit {tol:.1e} eV, {nk} k)", run
    return True, f"max |E(k) - E(-k)| = {asym:.2e} eV < {tol:.1e} eV, and the SHA-256 values agree", ""


def check_scales(job, fields, factor):
    """Rule B3. Return (passed, text, next step). passed is None if the job does not give the two tables."""
    scales, expect = get(job, fields["scales"]), get(job, fields["expected"])
    if scales is None or expect is None:
        return None, "the job file does not give error scales together with expected magnitudes", ""
    if not isinstance(scales, dict) or not isinstance(expect, dict):
        return False, "the error scales or the expected magnitudes are not an object", FIX_TABLES
    bad, count = [], 0
    for comp in sorted(scales):
        if comp not in expect:
            bad.append(f"{comp}: no expected magnitude")
            continue
        s, e = (v if isinstance(v, list) else [v] for v in (scales[comp], expect[comp]))
        if not s or not e or (len(s) != len(e) and 1 not in (len(s), len(e))):
            bad.append(f"{comp}: {len(s)} scales, {len(e)} expected magnitudes")
            continue
        for i in range(max(len(s), len(e))):
            try:
                scale, size = float(s[i % len(s)]), abs(float(e[i % len(e)]))
            except (TypeError, ValueError):
                bad.append(f"{comp}[{i}]: not a number")
                continue
            count += 1
            if not (0 < scale < math.inf and size < math.inf):
                bad.append(f"{comp}[{i}]: scale {scale:.3g}, expected {size:.3g}")
            elif scale < size / factor:
                bad.append(f"{comp}[{i}]: scale {scale:.3g} is {size / scale:.3g}x below the expected {size:.3g}")
    if bad:
        return False, f"these error scales do not pass (factor {factor:g}): " + ", ".join(bad[:6]) + (
            f" and {len(bad) - 6} more" if len(bad) > 6 else ""), FIX_SCALES
    if count == 0:
        return False, "no component has an error scale: the check compared nothing", FIX_TABLES
    return True, f"{count} error scales, none more than {factor:g}x below its expected magnitude", ""


def check_job(path, cfg, project):
    """Do the checks on one job file. Return a list of (rule, passed or None, text, next step)."""
    with open(path) as fh:
        job = json.load(fh)
    if not isinstance(job, dict):
        raise ValueError("the job file is not a JSON object")
    fields, bases = cfg["fields"], [os.path.dirname(os.path.abspath(path)), project]
    gate_ok, text, step = check_gate(job, fields, bases)
    results = [("W6", gate_ok, text, step)]
    if not get(job, fields["half_zone"]):
        results.append(("B7", None, "the job file does not set half-zone doubling "
                        f"(key \"{fields['half_zone']}\")", ""))
    elif gate_ok:
        results.append(("B7", True, "half-zone doubling is on, and check W6 passed", ""))
    else:
        results.append(("B7", False, "half-zone doubling is on, but check W6 did not pass. The doubling is exact "
                        "only for a model that passes the gate", "Correct check W6 first."))
    results.append(("B3",) + check_scales(job, fields, float(cfg["scale_factor"])))
    control, components = get(job, fields["forbidden_control"]), get(job, fields["components"])
    control = [control] if isinstance(control, str) else control
    if not isinstance(control, list) or not control or not all(isinstance(c, str) for c in control):
        results.append(("S8", False, "the job names no symmetry-forbidden control component "
                        f"(key \"{fields['forbidden_control']}\")", FIX_CONTROL))
    elif not isinstance(components, list):
        results.append(("S8", False, f"the job file has no list of components (key \"{fields['components']}\")",
                        FIX_CONTROL))
    elif [c for c in control if c not in components]:
        results.append(("S8", False, "the list of components does not contain the control component "
                        + ", ".join(c for c in control if c not in components), FIX_CONTROL))
    else:
        results.append(("S8", True, "symmetry-forbidden control component: " + ", ".join(control), ""))
    return results


def run(paths, cfg, project):
    """Check each job file. Return (report text, refused)."""
    lines, refused = [], False
    for path in paths:
        lines.append(f"preflight  job={path}")
        try:
            results = check_job(path, cfg, project)
        except Exception as err:                         # a check that cannot run refuses the job
            results = [("job", False, f"the job file cannot be checked: {err!r}", "Correct the job file.")]
        for rule, ok, text, step in results:
            lines.append(f"  {'SKIP' if ok is None else 'PASS' if ok else 'FAIL'}  {rule}  {text}")
            if ok is False:
                lines.append(f"        Next: {step}")
                refused = True
    lines.append(REFUSED if refused else "PREFLIGHT PASSED. You can start the scan.")
    return "\n".join(lines), refused


def simple_commands(command):
    """Split a shell command into simple commands: lists of words, without operators, redirection targets and the
    bodies of here-documents. A line break separates two commands."""
    kept, end = [], None
    for line in command.replace("\\\n", " ").split("\n"):
        if end is not None:
            end = None if line.strip() == end else end
            continue
        kept.append(line)
        match = re.search(r"(?<!<)<<-?(?!<)\s*['\"]?(\w+)", line)
        end = match.group(1) if match else None
    lexer = shlex.shlex(" ;\n".join(kept), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:                                   # an open quote
        tokens = " ;\n".join(kept).split()
    out, cur, target = [], [], False
    for tok in tokens:
        if tok and not tok.strip("();<>|&"):             # an operator
            target = "<" in tok or ">" in tok
            if not target:
                out, cur = out + [cur], []
        elif target:
            target = False                               # the file of a redirection
        else:
            cur.append(tok)
    return [c for c in out + [cur] if c]


def program(words):
    """Return (index of the program, head, inner) of a simple command. head is the program and, for an interpreter,
    its script, module or program text. inner is the command text of `sh -c`. index is None if there is no program."""
    i, n = 0, len(words)
    while i < n:
        if words[i] in KEYWORDS or ASSIGN.match(words[i]):
            i += 1
        elif os.path.basename(words[i]) in WRAPPERS:
            base, i = os.path.basename(words[i]), i + 1
            values, word = WRAPPERS[base].split(), base in WRAPPER_WORD
            while i < n and (word or words[i].startswith("-") or ASSIGN.match(words[i])):
                word = word and (words[i].startswith("-") or bool(ASSIGN.match(words[i])))
                i += 2 if words[i] in values else 1
        else:
            break
    if i >= n:
        return None, [], None
    head, base, j = [words[i]], os.path.basename(words[i]), i + 1
    shell = bool(SHELL.match(base))
    if shell or INTERPRETER.match(base):
        while j < n and words[j].startswith("-"):
            if shell and not words[j].startswith("--") and "c" in words[j]:
                return i, head, words[j + 1] if j + 1 < n else ""
            if not shell and words[j] in CODE_OPTIONS:
                return i, head + words[j + 1:j + 2], None
            j += 2 if not shell and words[j] in VALUE_OPTIONS else 1
        head += words[j:j + 1]
    return i, head, None


def expand(word, cwd):
    """Absolute path of a shell word, with $PWD, $HOME and ~ expanded. None if the word holds another variable."""
    word = re.sub(r"\$(PWD|\{PWD\})(?!\w)", lambda m: cwd, word)
    word = os.path.expanduser(re.sub(r"\$(HOME|\{HOME\})(?!\w)", lambda m: os.path.expanduser("~"), word))
    if "$" in word or "`" in word or "\0" in word:
        return None
    return os.path.normpath(os.path.join(cwd, word))


def job_files(words, cwd, project, name):
    """Job files that shell words name: a path to a file NAME, or a folder that contains NAME."""
    found = []
    for word in words:
        for part in {word, word.split("=", 1)[-1]} - {""}:      # also --job=PATH
            for base in (cwd, project):
                path = expand(part, base)
                if path and os.path.isdir(path):
                    path = os.path.join(path, name)
                if path and os.path.basename(path) == name and os.path.isfile(path):
                    found += [] if path in found else [path]
                    break
    return found


def launches(command, cwd, project, cfg, patterns, depth=0):
    """Return [(simple command, job files)] for each simple command that starts a scan."""
    found, name = [], cfg["job_file_name"]
    for words in simple_commands(command):
        i, head, inner = program(words)
        if i is None:
            continue
        if os.path.basename(head[0]) in ("cd", "pushd"):
            target = expand(next((w for w in words[i + 1:] if not w.startswith("-")), "~"), cwd)
            cwd = target if target and os.path.isdir(target) else cwd
        elif inner is not None:
            found += launches(inner, cwd, project, cfg, patterns, depth + 1) if depth < 4 else []
        elif os.path.basename(head[-1]) not in GATE_SCRIPTS and any(
                re.search(p, w) for p in patterns for w in head):
            named = [w.split("=", 1)[1] for w in words[:i] if ASSIGN.match(w)] + words[i + 1:]
            jobs = job_files(named, cwd, project, name)
            jobs = jobs or ([os.path.join(cwd, name)] if os.path.isfile(os.path.join(cwd, name)) else [])
            found.append((" ".join(words), jobs))
    return found


def hook(a):
    """PreToolUse hook. Block (exit code 2) a command that starts a scan, unless each job file passes the checks."""
    try:
        event = json.load(sys.stdin)
        command = event["tool_input"]["command"]
    except (ValueError, KeyError, TypeError):
        return 0
    if not isinstance(command, str):
        return 0
    cwd = event.get("cwd") if isinstance(event.get("cwd"), str) else None
    project = a.project or os.environ.get("CLAUDE_PROJECT_DIR") or cwd or os.getcwd()
    if not os.path.isfile(os.path.join(project, CONFIG_NAME)):
        return 0                                         # the hook is on only in a project that has the config file
    cwd = cwd or project
    try:
        try:
            cfg, problem = load_config(project), ""
        except (OSError, ValueError) as err:
            cfg = DEFAULTS
            problem = f"The config file is not valid: {err}\nCorrect the config file. Then run the command again."
        found = launches(command, cwd, project, cfg, cfg["launch_patterns"])
        if problem:                                      # the launch patterns are not known: block each job file
            named = any(jobs for _, jobs in launches(command, cwd, project, cfg, [""]))
            text, refused = problem, bool(found or named)
        else:
            jobs = list(dict.fromkeys(j for _, js in found for j in js))
            text, refused = run(jobs, cfg, project) if jobs else ("", False)
            for cmd, js in found:
                if not js:
                    text, refused = NO_JOB.format(cmd[:300]) + ("\n" + text if text else ""), True
    except Exception as err:                             # an error in a check must not permit the scan
        text, refused = f"The preflight stopped with an error: {err!r}", True
    if refused:
        print("Blocked by the preflight hook of dft-wannier-transport.", file=sys.stderr)
        print(text, file=sys.stderr)
        return 2
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("jobs", nargs="*", help="job files")
    ap.add_argument("--project", help=f"project folder, where {CONFIG_NAME} can be (default: $CLAUDE_PROJECT_DIR, "
                    "then the current folder)")
    ap.add_argument("--hook", action="store_true", help="read a Claude Code PreToolUse event from stdin")
    a = ap.parse_args(argv)
    if a.hook:
        return hook(a)
    if not a.jobs:
        ap.error("give a job file, or --hook")
    project = a.project or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        cfg = load_config(project)
    except (OSError, ValueError) as err:
        print(f"preflight: the config file is not valid: {err}", file=sys.stderr)
        return 2
    text, refused = run(a.jobs, cfg, project)
    print(text)
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
