#!/usr/bin/env python3
"""Preflight check of a job file before a scan starts (rules W6, B7, B3, S8 of the dft-wannier-transport skill).

    python3 preflight.py JOB.json [JOB.json ...] [--project DIR]
    python3 preflight.py --hook        # Claude Code PreToolUse hook: reads the hook event (JSON) from stdin

Put the first form in the launcher, before the first worker starts. The hook is the second line of defence. The hook
is on only in a project that has the config file.

Checks:
  W6  The model file of the job has a certificate from trs_gate.py. The gate passed, and the SHA-256 in the
      certificate is the SHA-256 of the model file now.
  B7  Half-zone doubling is on only if the W6 check passed.
  B3  Each error scale agrees with the expected magnitude within a factor of 10 (only if the job gives both).
  S8  The job names a minimum of one symmetry-forbidden control component.

Config file (optional): `dft_gates.json` in the project folder. Its keys are "launch_patterns" (regular expressions
for the commands that start workers), "job_file_name", "scale_factor" and "fields". "fields" gives the key of the
job file for model, wsvec, certificate, half_zone, scales, expected, components and forbidden_control ("a.b" = key b
of object a). The defaults are in DEFAULTS. The hook checks a job file only if the command text names it.

Exit code: 0 = pass, 1 = refused, 2 = bad input. With --hook: 0 = permit the command, 2 = block the command.
Only the standard library is necessary.
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import sys

CONFIG_NAME = "dft_gates.json"
DEFAULTS = {
    "launch_patterns": ["scan_worker"],                  # regular expressions: a command that matches starts a scan
    "job_file_name": "job.json",
    "fields": {                                          # name in this script -> key in the job file ("a.b" = nested)
        "model": "model", "wsvec": "wsvec", "certificate": "trs_certificate", "half_zone": "half_zone",
        "scales": "scales", "expected": "expected_magnitudes", "components": "components",
        "forbidden_control": "forbidden_control"},
    "scale_factor": 10.0,                                # rule B3
}
MAX_TOL_EV, MIN_NK = 1e-5, 2000                          # rule W6: not in the config file
GATE = "python3 " + shlex.quote(os.path.join(os.path.dirname(os.path.abspath(__file__)), "trs_gate.py"))
FIX_MODEL = ("Correct the model. Then run the gate again (W7, W17). Do not use a k/-k average or a real-part "
             "projection. Do not edit the certificate.")
FIX_CONTROL = ("Add one component that the point group forbids to the components of the job. Write its name "
               "under this key (S3, S8).")
FIX_SCALES = ("Take the scales from a comparable cheap model (B3). For a component that vanishes by symmetry, "
              "use a floor over all components (S7).")
FIX_TABLES = (f"Write the two tables as objects: {{component: number or list of numbers}}. If a key has a different "
              f"name, set it in {CONFIG_NAME}.")
REFUSED = """PREFLIGHT REFUSED. Do not start this scan.
Correct each FAIL line. Then run preflight again.
Do not bypass this check. Do not use a k/-k average, a real-part projection or an edited certificate (W7, W17).
If you cannot correct a FAIL line, stop. Tell the owner of the project."""


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


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
    if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
        raise ValueError("\"launch_patterns\" must be a list of regular expressions")
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as err:
            raise ValueError(f"launch pattern {pattern!r} is not a regular expression: {err}")
    if not all(isinstance(v, str) for v in list(cfg["fields"].values()) + [cfg["job_file_name"]]):
        raise ValueError("the values of \"fields\" and \"job_file_name\" must be strings")
    factor = cfg["scale_factor"]
    if isinstance(factor, bool) or not isinstance(factor, (int, float)) or factor <= 1:
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
    ws, near = get(job, fields["wsvec"]), re.sub(r"_(hr|tb)\.dat$", "_wsvec.dat", model)
    named = isinstance(ws, str)                          # the job names the wsvec file: the engine loads it
    ws = resolve(ws, bases) if named else near if near != model and os.path.isfile(near) else None
    run = f"Run the gate: {GATE} {shlex.quote(model)}" + (f" --wsvec {shlex.quote(ws)}" if named else "")
    cert_path = get(job, fields["certificate"])
    cert_path = resolve(cert_path, bases) if isinstance(cert_path, str) else model + ".trs_gate.json"
    try:
        with open(cert_path) as fh:
            cert = json.load(fh)
        asym, tol, nk = float(cert["max_asym_eV"]), float(cert["tol_eV"]), int(cert["nk"])
        if cert["gate"] != "W6-trs":
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        return False, f"there is no valid gate certificate at {cert_path}", run
    if cert.get("model_sha256") != sha256(model):
        return (False, "the SHA-256 of the model file does not agree with the certificate: the model file changed "
                "after the gate, or the certificate is from a different model", run)
    if ws is None or cert.get("wsvec_sha256") is None:   # no wsvec file now, or the gate read no wsvec file
        ws_ok = cert.get("wsvec_sha256") is None and (ws is None or (cert.get("no_wsvec") is True and not named))
    else:
        ws_ok = os.path.isfile(ws) and cert["wsvec_sha256"] == sha256(ws)
    if not ws_ok:
        return (False, "the wsvec file is not the wsvec file of the certificate: the images changed after the gate, "
                "or the gate read a different wsvec file (W17)", run)
    if cert.get("passed") is not True or not asym < tol:
        return (False, f"the model FAILED the time-reversal gate: max |E(k) - E(-k)| = {asym:.2e} eV, "
                f"limit {tol:.1e} eV", FIX_MODEL)
    if tol > MAX_TOL_EV or nk < MIN_NK:
        return False, f"the certificate is from a weaker test than rule W6 (limit {tol:.1e} eV, {nk} k)", run
    return True, f"max |E(k) - E(-k)| = {asym:.2e} eV < {tol:.1e} eV, and the SHA-256 of the model file agrees", ""


def check_scales(job, fields, factor):
    """Rule B3. Return (passed, text, next step). passed is None if the job does not give the two tables."""
    scales, expect = get(job, fields["scales"]), get(job, fields["expected"])
    if scales is None or expect is None:
        return None, "the job file does not give error scales together with expected magnitudes", ""
    if not isinstance(scales, dict) or not isinstance(expect, dict):
        return False, "the error scales or the expected magnitudes are not an object", FIX_TABLES
    bad, count = [], 0
    try:
        for comp in sorted(set(scales) & set(expect)):
            s, e = (v if isinstance(v, list) else [v] for v in (scales[comp], expect[comp]))
            if len(s) != len(e) and 1 not in (len(s), len(e)):
                bad.append(f"{comp}: {len(s)} scales, {len(e)} expected magnitudes")
                continue
            for i in range(max(len(s), len(e))):
                scale, size = float(s[i % len(s)]), abs(float(e[i % len(e)]))
                if size == 0:                            # a value that vanishes by symmetry has no magnitude (S7)
                    continue
                count += 1
                if not size / factor <= scale <= size * factor:
                    bad.append(f"{comp}[{i}]: scale {scale:.3g}, expected {size:.3g}, ratio {scale / size:.3g}")
    except (TypeError, ValueError):
        return False, "an error scale or an expected magnitude is not a number", FIX_TABLES
    if bad:
        return False, (f"these error scales do not agree with the expected magnitudes within a factor of {factor:g}: "
                       + ", ".join(bad[:6]) + (f" and {len(bad) - 6} more" if len(bad) > 6 else "")), FIX_SCALES
    if count == 0:
        return False, "no component is in the two tables: the check compared nothing", FIX_TABLES
    return True, f"{count} error scales agree with the expected magnitudes within a factor of {factor:g}", ""


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
    listed = isinstance(control, list) and isinstance(components, list)
    absent = [c for c in control if c not in components] if listed else []
    if not isinstance(control, list) or not control or not all(isinstance(c, str) for c in control):
        results.append(("S8", False, "the job names no symmetry-forbidden control component "
                        f"(key \"{fields['forbidden_control']}\")", FIX_CONTROL))
    elif absent:
        results.append(("S8", False, f"the control component {', '.join(absent)} is not in the components of the job",
                        FIX_CONTROL))
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
        except (OSError, ValueError) as err:
            results = [("job", False, f"the job file is not readable: {err}", "Correct the job file.")]
        for rule, ok, text, step in results:
            lines.append(f"  {'SKIP' if ok is None else 'PASS' if ok else 'FAIL'}  {rule}  {text}")
            if ok is False:
                lines.append(f"        Next: {step}")
                refused = True
    lines.append(REFUSED if refused else "PREFLIGHT PASSED. You can start the scan.")
    return "\n".join(lines), refused


def find_jobs(command, name, bases):
    """Job files that the command text names: a path to a file NAME, or a folder that contains NAME."""
    try:
        words = shlex.split(command)
    except ValueError:
        words = command.split()
    found = []
    for word in words:
        for part in {word, word.split("=", 1)[-1]} - {""}:      # also --job=PATH
            for base in bases:
                try:
                    path = os.path.join(base, os.path.expanduser(part))
                    if os.path.isdir(path):
                        path = os.path.join(path, name)
                    path = os.path.normpath(path)
                    if os.path.basename(path) == name and os.path.isfile(path) and path not in found:
                        found.append(path)
                except ValueError:                       # a word that cannot be a path
                    pass
    return found


def hook(a):
    """PreToolUse hook. Block (exit code 2) a scan-launch command if a job file that it names fails the checks."""
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
    try:
        cfg, problem = load_config(project), ""
    except (OSError, ValueError) as err:
        cfg = DEFAULTS
        problem = f"The config file is not valid: {err}\nCorrect the config file. Then run the command again."
    if not any(re.search(pattern, command) for pattern in cfg["launch_patterns"]):
        return 0
    try:
        jobs = find_jobs(command, cfg["job_file_name"], [cwd or project, project])
        text, refused = (problem, True) if problem else run(jobs, cfg, project) if jobs else ("", False)
    except Exception as err:                             # an error in a check must not permit the scan
        text, refused = f"The preflight stopped with an error: {err!r}", True
    if refused:
        print("Blocked by the preflight hook of dft-wannier-transport. This command starts a scan.", file=sys.stderr)
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
