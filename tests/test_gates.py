"""Must-fail controls for the gate scripts of the dft-wannier-transport skill.

    python3 -m pytest        (numpy and pytest are necessary)

Each check of each script has a case that must fail. All models are synthetic: random tight-binding models, not
real materials. The files follow the layouts of Wannier90 3.1.0.
"""
import hashlib
import json
import os
import subprocess
import sys
import time

import numpy as np
import pytest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dft-wannier-transport", "scripts")
VECTORS = [(x, y, 0) for x in (-1, 0, 1) for y in (-1, 0, 1)]
PAULI = np.array([[[1, 0], [0, 1]], [[0, 1], [1, 0]], [[0, -1j], [1j, 0]], [[1, 0], [0, -1]]])


def call(script, *args, stdin=None, env=None):
    """Run one script. Return (exit code, stdout, stderr)."""
    done = subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *map(str, args)],
                          capture_output=True, text=True, input=stdin, env=env)
    return done.returncode, done.stdout, done.stderr


def load(path):
    with open(path) as fh:
        return json.load(fh)


def spinless(nw=4, broken=0.0, seed=1):
    """H(R) of a random model with real elements, thus E(k) = E(-k). `broken` adds an imaginary part."""
    rng, H = np.random.default_rng(seed), {}
    for R in VECTORS:
        minus = tuple(-x for x in R)
        if R in H:
            continue
        real, imag = rng.normal(size=(2, nw, nw))
        if R == minus:
            H[R] = (real + real.T) / 2 + 1j * broken * (imag - imag.T) / 2
        else:
            H[R] = real + 1j * broken * imag
            H[minus] = H[R].conj().T
    return H


def spinor(orbitals=2, seed=2):
    """H(R) of a random spinor model with time-reversal symmetry: A x 1 + i sum_j B_j x sigma_j, A and B_j real.

    The two functions of orbital a (indices 2a and 2a + 1) are a Kramers pair.
    """
    rng, H = np.random.default_rng(seed), {}
    for R in VECTORS:
        minus = tuple(-x for x in R)
        if R in H:
            continue
        parts = rng.normal(size=(4, orbitals, orbitals))
        if R == minus:
            parts[0] = (parts[0] + parts[0].T) / 2
            parts[1:] = (parts[1:] - parts[1:].transpose(0, 2, 1)) / 2
        H[R] = np.kron(parts[0], PAULI[0]) + 1j * sum(np.kron(parts[j], PAULI[j]) for j in (1, 2, 3))
        H[minus] = H[R].conj().T
    return H


def write_model(path, H, layout="hr"):
    """Write H(R) with the line layout of a Wannier90 hr.dat or tb.dat file."""
    nw = len(H[(0, 0, 0)])
    pairs = [(m, n) for n in range(nw) for m in range(nw)]      # the first index changes fastest, as in Wannier90
    with open(path, "w") as fh:
        fh.write("synthetic test model (not a real material)\n")
        if layout == "tb":
            fh.write("1.0 0.0 0.0\n0.0 1.0 0.0\n0.0 0.0 20.0\n")
        fh.write(f"{nw}\n{len(H)}\n" + "    1" * len(H) + "\n")
        for R, h in H.items():
            if layout == "tb":
                fh.write("\n%5d%5d%5d\n" % R)
            for m, n in pairs:
                if layout == "tb":
                    fh.write(f"{m + 1:5d}{n + 1:5d}   {h[m, n].real:15.8E} {h[m, n].imag:15.8E}\n")
                else:
                    fh.write("%5d%5d%5d" % R + f"{m + 1:5d}{n + 1:5d}{h[m, n].real:12.6f}{h[m, n].imag:12.6f}\n")
        for R in H if layout == "tb" else ():                   # the position operator: the gate must ignore it
            fh.write("\n%5d%5d%5d\n" % R)
            fh.writelines(f"{m + 1:5d}{n + 1:5d}   " + "0.00000000E+00 " * 6 + "\n" for m, n in pairs)
    return str(path)


def write_wsvec(path, H, images):
    """Write a wsvec.dat file. `images` maps (R, m, n) to its image vectors. Other elements have the image (0, 0, 0)."""
    nw = len(H[(0, 0, 0)])
    with open(path, "w") as fh:
        fh.write("## synthetic test file with use_ws_distance=.true.\n")
        for R in H:
            for m in range(nw):
                for n in range(nw):
                    shifts = images.get((R, m, n), [(0, 0, 0)])
                    fh.write("%5d%5d%5d" % R + f"{m + 1:5d}{n + 1:5d}\n{len(shifts):5d}\n")
                    fh.writelines("%5d%5d%5d\n" % shift for shift in shifts)
    return str(path)


def kramers_images(differ):
    """Images for the 2 x 2 spin block between orbital 0 and orbital 1 of `spinor()` at R = (1, 0, 0), and for its
    Hermitian partner. With `differ`, the two functions of one Kramers pair get different images (rule W17)."""
    R, minus, images = (1, 0, 0), (-1, 0, 0), {}
    for s in (0, 1):
        for t in (0, 1):
            images[(R, s, 2 + t)] = [(0, 0, 0), (-1, 0, 0)]
            images[(minus, 2 + t, s)] = [(0, 0, 0), (1, 0, 0)]
    if differ:
        images[(R, 1, 3)], images[(minus, 3, 1)] = [(0, 0, 0)], [(0, 0, 0)]
    return images


def job_folder(folder, H=None, gate=("--no-wsvec",), **changes):
    """Make a model, its gate certificate and a job file that passes the preflight. Return (job path, model path)."""
    os.makedirs(folder, exist_ok=True)
    model = write_model(os.path.join(folder, "model_hr.dat"), spinless() if H is None else H)
    call("trs_gate.py", model, *gate)
    job = {"model": "model_hr.dat", "half_zone": True, "components": ["yxx", "yyy", "xxx"],
           "forbidden_control": "xxx", "scales": {"yxx": [2e-3, 5e-4], "yyy": 1e-3},
           "expected_magnitudes": {"yxx": [1e-3, 1e-3], "yyy": 4e-3, "xxx": 0.0}}
    job.update(changes)
    path = os.path.join(folder, "job.json")
    with open(path, "w") as fh:
        json.dump(job, fh)
    return path, model


def edit_job(path, **changes):
    job = load(path)
    job.update(changes)
    with open(path, "w") as fh:
        json.dump(job, fh)


# ---- trs_gate.py -----------------------------------------------------------------------------------------------

def test_gate_passes_a_symmetric_model(tmp_path):
    model = write_model(tmp_path / "sym_hr.dat", spinless())
    code, out, _ = call("trs_gate.py", model, "--no-wsvec")
    cert = load(model + ".trs_gate.json")
    assert code == 0 and "PASS" in out
    assert cert["passed"] is True and cert["max_asym_eV"] < cert["tol_eV"] == 1e-5 and cert["nk"] >= 2000
    assert cert["max_antihermitian_eV"] < 1e-12 and cert["seed"] == 0 and cert["no_wsvec"] is True
    assert cert["model_sha256"] == hashlib.sha256(open(model, "rb").read()).hexdigest()


def test_gate_fails_an_asymmetric_model(tmp_path):              # must-fail control
    model = write_model(tmp_path / "asym_hr.dat", spinless(broken=1e-4))
    code, out, _ = call("trs_gate.py", model, "--no-wsvec")
    cert = load(model + ".trs_gate.json")
    assert code == 1 and "FAIL  time-reversal gate" in out and "Do not continue with a k/-k average" in out
    assert cert["passed"] is False and cert["max_asym_eV"] >= 1e-5


def not_hermitian():
    """H(R) = (1 + 0.05i) x a real model. Its Hermitian part is the real model: E(k) = E(-k) hides the defect."""
    return {R: h * (1 + 0.05j) for R, h in spinless().items()}


def test_gate_fails_a_model_that_is_not_hermitian(tmp_path):     # must-fail control
    model = write_model(tmp_path / "nh_hr.dat", not_hermitian())
    code, out, _ = call("trs_gate.py", model, "--no-wsvec")
    cert = load(model + ".trs_gate.json")
    assert code == 1 and "H(k) is not Hermitian" in out and cert["max_asym_eV"] < 1e-5
    assert cert["passed"] is False and cert["max_antihermitian_eV"] >= 1e-5


def test_gate_reads_the_tb_layout_and_measures_small_values(tmp_path):
    H = spinless(broken=1e-4)
    hr, tb = (write_model(tmp_path / f"a_{kind}.dat", H, kind) for kind in ("hr", "tb"))
    assert call("trs_gate.py", hr, "--no-wsvec")[0] == 1 and call("trs_gate.py", tb, "--no-wsvec")[0] == 1
    assert abs(load(hr + ".trs_gate.json")["max_asym_eV"] / load(tb + ".trs_gate.json")["max_asym_eV"] - 1) < 0.05
    small = write_model(tmp_path / "small_tb.dat", spinless(broken=1e-9), "tb")
    assert call("trs_gate.py", small, "--no-wsvec")[0] == 0
    assert 0 < load(small + ".trs_gate.json")["max_asym_eV"] < 1e-7


def test_gate_refuses_a_weaker_test_and_bad_input(tmp_path):    # must-fail control
    model = write_model(tmp_path / "sym_hr.dat", spinless())
    assert call("trs_gate.py", model, "--no-wsvec", "--nk", 100)[0] == 2
    assert call("trs_gate.py", model, "--no-wsvec", "--tol", 1e-3)[0] == 2
    assert call("trs_gate.py", tmp_path / "absent_hr.dat", "--no-wsvec")[0] == 2
    code, _, err = call("trs_gate.py", model)                  # no wsvec file and no --no-wsvec
    assert code == 2 and "no wsvec file" in err
    assert not os.path.exists(model + ".trs_gate.json")
    with open(model, "a") as fh:                                # more numbers than the header gives
        fh.write("    0    0    0    1    1    0.000000    0.000000\n")
    assert call("trs_gate.py", model, "--no-wsvec")[0] == 2


def test_gate_fails_if_wsvec_images_differ_in_a_kramers_pair(tmp_path):     # must-fail control, rule W17
    H = spinor()
    model = write_model(tmp_path / "spinor_hr.dat", H)
    assert call("trs_gate.py", model, "--no-wsvec")[0] == 0   # H(R) without images is symmetric
    good = write_wsvec(tmp_path / "good_wsvec.dat", H, kramers_images(differ=False))
    assert call("trs_gate.py", model)[0] == 0                   # the only wsvec file of the folder
    assert load(model + ".trs_gate.json")["wsvec_file"] == "good_wsvec.dat"
    bad = write_wsvec(tmp_path / "spinor_wsvec.dat", H, kramers_images(differ=True))
    code, out, _ = call("trs_gate.py", model)                  # NAME_wsvec.dat comes first
    cert = load(model + ".trs_gate.json")
    assert code == 1 and "FAIL  time-reversal gate" in out and cert["max_antihermitian_eV"] < 1e-12
    assert cert["wsvec_sha256"] == hashlib.sha256(open(bad, "rb").read()).hexdigest()
    assert call("trs_gate.py", model, "--wsvec", good)[0] == 0
    other = write_model(tmp_path / "w90_model.dat", H)         # a name without _hr or _tb: two wsvec files here
    code, _, err = call("trs_gate.py", other)
    assert code == 2 and "several wsvec files" in err
    os.makedirs(tmp_path / "one")
    one = write_model(tmp_path / "one" / "w90_model.dat", H)
    write_wsvec(tmp_path / "one" / "w90_wsvec.dat", H, kramers_images(differ=True))
    assert call("trs_gate.py", one)[0] == 1                     # the only wsvec file of its folder


# ---- preflight.py ----------------------------------------------------------------------------------------------

def test_preflight_passes_a_good_job(tmp_path):
    job, _ = job_folder(tmp_path)
    code, out, _ = call("preflight.py", job)
    assert code == 0 and "PREFLIGHT PASSED" in out and "FAIL" not in out


def test_preflight_refuses_a_certificate_with_a_wrong_hash(tmp_path):       # must-fail control
    job, model = job_folder(tmp_path)
    with open(model, "a") as fh:                                # the model file changes after the gate
        fh.write("\n")
    code, out, _ = call("preflight.py", job)
    assert code == 1 and "FAIL  W6" in out and "SHA-256 of the model file does not agree" in out


def test_preflight_refuses_a_wsvec_file_that_changed_after_the_gate(tmp_path):   # must-fail control, rule W17
    H = spinor()
    wsvec = write_wsvec(tmp_path / "model_wsvec.dat", H, kramers_images(differ=False))
    job, model = job_folder(tmp_path, H=H, gate=())
    assert load(model + ".trs_gate.json")["wsvec_file"] == "model_wsvec.dat" and call("preflight.py", job)[0] == 0
    write_wsvec(wsvec, H, kramers_images(differ=True))
    code, out, _ = call("preflight.py", job)
    assert code == 1 and "the wsvec file is not the wsvec file of the certificate" in out
    assert call("trs_gate.py", model)[0] == 1                   # the new images break E(k) = E(-k)
    assert call("trs_gate.py", model, "--no-wsvec")[0] == 0 and call("preflight.py", job)[0] == 0
    edit_job(job, wsvec="model_wsvec.dat")                      # the job names the file: no exception
    assert call("preflight.py", job)[0] == 1
    os.remove(wsvec)
    edit_job(job, wsvec=None)
    assert call("trs_gate.py", model)[0] == 2                   # no wsvec file, and no --no-wsvec


def test_preflight_refuses_a_failed_gate_and_half_zone_doubling(tmp_path):  # must-fail control
    job, model = job_folder(tmp_path, H=spinless(broken=1e-4))
    code, out, _ = call("preflight.py", job)
    assert code == 1 and "FAIL  W6" in out and "FAIL  B7" in out and "Do not use a k/-k average" in out
    cert = load(model + ".trs_gate.json")                       # an edited certificate stays refused
    cert["passed"] = True
    with open(model + ".trs_gate.json", "w") as fh:
        json.dump(cert, fh)
    assert call("preflight.py", job)[0] == 1
    job, model = job_folder(tmp_path / "nh", H=not_hermitian())
    code, out, _ = call("preflight.py", job)
    assert code == 1 and "not Hermitian" in out
    cert = load(model + ".trs_gate.json")
    cert["passed"] = True
    with open(model + ".trs_gate.json", "w") as fh:
        json.dump(cert, fh)
    assert call("preflight.py", job)[0] == 1                    # the measured value refuses it, not only the flag
    os.remove(model + ".trs_gate.json")                         # no certificate
    assert call("preflight.py", job)[0] == 1


def test_preflight_b3_refuses_too_strict_and_missing_scales(tmp_path):      # must-fail controls
    job, _ = job_folder(tmp_path)
    for scales, expected, ok in [
            ({"yxx": [1e-6, 5e-4], "yyy": 1e-3}, None, False),           # 1e-6 is 1000x below 1e-3
            ({"yxx": [1.0, 5e-4], "yyy": 1e-3}, None, True),             # larger scales pass (floors of S7)
            ({"yxx": 1e-3, "yyy": 1e-3, "yxy": 1e-3}, None, False),      # yxy has no expected magnitude
            ({"xxx": 1e-9}, {"xxx": 3e-18}, True),                       # a floor above the noise of a zero
            ({"yxx": []}, None, False),                                  # an empty list
            ({"yxx": "big"}, None, False),                               # not a number
            ({}, None, False)]:                                          # nothing to compare
        edit_job(job, scales=scales, **({"expected_magnitudes": expected} if expected else {}))
        code, out, _ = call("preflight.py", job)
        assert (code == 0) == ok and ("PASS  B3" if ok else "FAIL  B3") in out, (scales, out)
        assert "Traceback" not in out


def test_preflight_s8_refuses_a_missing_control(tmp_path):                  # must-fail controls
    job, _ = job_folder(tmp_path)
    for changes in [{"forbidden_control": None}, {"forbidden_control": "zzz"}, {"components": None},
                    {"components": "yxx yyy xxx"}]:
        edit_job(job, **changes)
        code, out, _ = call("preflight.py", job)
        assert code == 1 and "FAIL  S8" in out, changes
        edit_job(job, forbidden_control="xxx", components=["yxx", "yyy", "xxx"])
    assert call("preflight.py", job)[0] == 0


def test_preflight_reads_the_keys_from_the_config_file(tmp_path):
    job, _ = job_folder(tmp_path)
    data = load(job)
    data["inputs"] = {"tb_file": data.pop("model")}
    data["control"] = data.pop("forbidden_control")
    with open(job, "w") as fh:
        json.dump(data, fh)
    assert call("preflight.py", job, "--project", tmp_path)[0] == 1          # the default keys do not fit
    (tmp_path / "dft_gates.json").write_text(json.dumps({"fields": {"model": "inputs.tb_file",
                                                                    "forbidden_control": "control"}}))
    assert call("preflight.py", job, "--project", tmp_path)[0] == 0
    (tmp_path / "dft_gates.json").write_text(json.dumps({"launch_pattern": ["x"]}))
    assert call("preflight.py", job, "--project", tmp_path)[0] == 2          # a typo in a key is an error


# ---- the hook (preflight.py --hook) ----------------------------------------------------------------------------

def hook(project, command, cwd=None):
    event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(cwd or project),
             "tool_input": {"command": command}}
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project))
    return call("preflight.py", "--hook", stdin=json.dumps(event), env=env)


def test_hook_blocks_a_launch_of_a_refused_job(tmp_path):                   # must-fail control
    job, model = job_folder(tmp_path / "runs" / "s1")
    launch = "nohup julia scan_worker.jl runs/s1 3 > worker_3.log 2>&1 &"
    with open(model, "a") as fh:                                # the job is refused now
        fh.write("\n")
    assert hook(tmp_path, launch) == (0, "", "")                # no config file: the hook is off
    (tmp_path / "dft_gates.json").write_text("{}")
    code, out, err = hook(tmp_path, launch)
    assert code == 2 and out == "" and "Blocked by the preflight hook" in err and "SHA-256" in err
    for command in ["cd runs/s1; nohup julia scan_worker.jl job.json &",
                    "nohup julia scan_worker.jl runs/s1/job.json; echo started",
                    "cd runs && nohup julia scan_worker.jl s1",
                    'nohup julia scan_worker.jl "$PWD/runs/s1" 3 &',
                    "julia --project=. -t 1 scan_worker.jl runs/s1",
                    'bash -c "cd runs/s1 && julia scan_worker.jl ."',
                    "JOB=runs/s1 julia scan_worker.jl",
                    "cd runs/s1\njulia scan_worker.jl . 3",
                    "for i in 1 2; do nohup julia scan_worker.jl runs/s1 $i & done"]:
        code, _, err = hook(tmp_path, command)                  # the hook finds the job file and refuses it
        assert code == 2 and "SHA-256 of the model file" in err, command
    code, _, err = hook(tmp_path, "julia scan_worker.jl 3", cwd=tmp_path / "runs" / "s1")   # run in the job folder
    assert code == 2 and "SHA-256 of the model file" in err
    code, _, err = hook(tmp_path, "julia scan_worker.jl 3")    # names no job file
    assert code == 2 and "finds no job file" in err


def test_hook_permits_other_commands_and_a_good_job(tmp_path):             # must-pass control
    job, model = job_folder(tmp_path / "runs" / "s1")
    (tmp_path / "dft_gates.json").write_text("{}")
    assert hook(tmp_path, "nohup julia scan_worker.jl runs/s1 3 > worker_3.log 2>&1 &") == (0, "", "")
    assert hook(tmp_path, "julia scan_worker.jl 3", cwd=tmp_path / "runs" / "s1") == (0, "", "")
    assert hook(tmp_path, "cd runs/s1 && nohup julia scan_worker.jl job.json &") == (0, "", "")
    assert hook(tmp_path, 'nohup julia scan_worker.jl "$PWD/runs/s1" 3 &') == (0, "", "")
    with open(model, "a") as fh:                                # the job is refused now
        fh.write("\n")
    for command in ["pgrep -fl scan_worker; ls -la runs/s1",
                    "python3 /x/live_workers.py --pattern scan_worker && mv runs/s1 archive/s1",
                    "grep -c scan_worker runs/s1/job.json",
                    'until ! pgrep -f "[s]can_worker.jl"; do sleep 60; done',
                    "cat > launch.sh <<'EOF'\njulia scan_worker.jl runs/s1 3\nEOF\nchmod +x launch.sh",
                    "python3 /x/preflight.py runs/s1/job.json",
                    "git status", "ls -la job.json"]:
        assert hook(tmp_path, command) == (0, "", ""), command


def test_hook_follows_the_config_file(tmp_path):                           # must-fail controls
    job, model = job_folder(tmp_path / "runs" / "s1")
    with open(model, "a") as fh:
        fh.write("\n")
    driver = "nohup python3 bz_scan.py --job=runs/s1/job.json > log 2>&1 &"
    (tmp_path / "dft_gates.json").write_text("{}")
    assert hook(tmp_path, driver)[0] == 0                       # not a launch pattern by default
    (tmp_path / "dft_gates.json").write_text(json.dumps({"launch_patterns": ["bz_scan"]}))
    assert hook(tmp_path, driver)[0] == 2
    for bad in ['{"launch_patterns": ["bz_scan"], "scale_factr": 5}', '{"launch_patterns": "bz_scan"}', "{not json"]:
        (tmp_path / "dft_gates.json").write_text(bad)
        code, _, err = hook(tmp_path, driver)                   # a bad config file blocks each job file
        assert code == 2 and "config file is not valid" in err, bad
        assert hook(tmp_path, "ls -la")[0] == 0
        assert hook(tmp_path, "python3 /x/preflight.py runs/s1/job.json")[0] == 0


# ---- live_workers.py -------------------------------------------------------------------------------------------

def test_live_workers_refuses_while_a_worker_is_alive():                    # must-fail control
    marker = f"toy_worker_{os.getpid()}"
    worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)", marker])
    try:
        for _ in range(50):
            code, out, _ = call("live_workers.py", "--pattern", marker)
            if code == 1:
                break
            time.sleep(0.1)
        assert code == 1 and str(worker.pid) in out and "Do not move" in out
    finally:
        worker.kill()
        worker.wait()
    assert call("live_workers.py", "--pattern", marker)[0] == 0              # its own command line has the marker
    script = os.path.join(SCRIPTS, "live_workers.py")
    shell = subprocess.run(["sh", "-c", f"'{sys.executable}' '{script}' --pattern {marker}; exit $?"])
    assert shell.returncode == 0                                             # R20: the calling shell has it too
    assert call("live_workers.py", "--pattern", "(")[0] == 2                 # not a regular expression
    default = __import__("re").compile(open(script).read().split("R6_PATTERNS = [r\"")[1].split("\"]")[0])
    assert all(default.search(cmd) for cmd in ["mpirun -np 4 vasp_ncl", "postw90.x hBN", "julia scan_worker.jl"])
