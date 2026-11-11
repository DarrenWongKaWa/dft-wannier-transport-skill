"""Must-fail controls for the gate scripts of the dft-wannier-transport skill.

    python3 -m pytest        (numpy and pytest are necessary)

Each script has a case that must pass and a case that must fail. All models are synthetic: random
tight-binding models, not real materials.
"""
import hashlib
import json
import os
import shutil
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


def job_folder(tmp_path, H=None, **changes):
    """Make a model, its gate certificate and a job file that passes the preflight. Return (job path, model path)."""
    model = write_model(tmp_path / "model_hr.dat", spinless() if H is None else H)
    call("trs_gate.py", model)
    job = {"model": "model_hr.dat", "half_zone": True, "components": ["yxx", "yyy", "xxx"],
           "forbidden_control": "xxx", "scales": {"yxx": [2e-3, 5e-4], "yyy": 1e-3},
           "expected_magnitudes": {"yxx": [1e-3, 1e-3], "yyy": 4e-3, "xxx": 0.0}}
    job.update(changes)
    (tmp_path / "job.json").write_text(json.dumps(job))
    return str(tmp_path / "job.json"), model


# ---- trs_gate.py -----------------------------------------------------------------------------------------------

def test_gate_passes_a_symmetric_model(tmp_path):
    model = write_model(tmp_path / "sym_hr.dat", spinless())
    code, out, _ = call("trs_gate.py", model)
    cert = load(model + ".trs_gate.json")
    assert code == 0 and "PASS" in out
    assert cert["passed"] is True and cert["max_asym_eV"] < cert["tol_eV"] == 1e-5 and cert["nk"] >= 2000
    assert cert["seed"] == 0 and cert["model_sha256"] == hashlib.sha256(open(model, "rb").read()).hexdigest()


def test_gate_fails_an_asymmetric_model(tmp_path):              # must-fail control
    model = write_model(tmp_path / "asym_hr.dat", spinless(broken=1e-4))
    code, out, _ = call("trs_gate.py", model)
    cert = load(model + ".trs_gate.json")
    assert code == 1 and "FAIL" in out and "Do not continue with a k/-k average" in out
    assert cert["passed"] is False and cert["max_asym_eV"] >= 1e-5


def test_gate_reads_the_tb_layout_and_measures_small_values(tmp_path):
    H = spinless(broken=1e-4)
    hr, tb = (write_model(tmp_path / f"a_{kind}.dat", H, kind) for kind in ("hr", "tb"))
    assert call("trs_gate.py", hr)[0] == 1 and call("trs_gate.py", tb)[0] == 1
    assert abs(load(hr + ".trs_gate.json")["max_asym_eV"] / load(tb + ".trs_gate.json")["max_asym_eV"] - 1) < 0.05
    small = write_model(tmp_path / "small_tb.dat", spinless(broken=1e-9), "tb")
    assert call("trs_gate.py", small)[0] == 0
    assert 0 < load(small + ".trs_gate.json")["max_asym_eV"] < 1e-7


def test_gate_refuses_a_weaker_test(tmp_path):                  # must-fail control
    model = write_model(tmp_path / "sym_hr.dat", spinless())
    assert call("trs_gate.py", model, "--nk", 100)[0] == 2
    assert call("trs_gate.py", model, "--tol", 1e-3)[0] == 2
    assert call("trs_gate.py", tmp_path / "absent_hr.dat")[0] == 2
    assert not os.path.exists(model + ".trs_gate.json")


def test_gate_fails_if_wsvec_images_differ_in_a_kramers_pair(tmp_path):     # must-fail control, rule W17
    H = spinor()
    model = write_model(tmp_path / "spinor_hr.dat", H)
    R, minus = (1, 0, 0), (-1, 0, 0)
    same = {}
    for s in (0, 1):                                            # the 2 x 2 spin block between orbital 0 and orbital 1
        for t in (0, 1):
            same[(R, s, 2 + t)] = [(0, 0, 0), (-1, 0, 0)]
            same[(minus, 2 + t, s)] = [(0, 0, 0), (1, 0, 0)]    # the Hermitian partner
    differ = dict(same)
    differ[(R, 1, 3)], differ[(minus, 3, 1)] = [(0, 0, 0)], [(0, 0, 0)]
    good = write_wsvec(tmp_path / "good_wsvec.dat", H, same)
    assert call("trs_gate.py", model)[0] == 0                   # H(R) without images is symmetric
    assert call("trs_gate.py", model, "--wsvec", good)[0] == 0
    bad = write_wsvec(tmp_path / "spinor_wsvec.dat", H, differ)  # next to the model file: the gate reads it
    assert call("trs_gate.py", model)[0] == 1
    cert = load(model + ".trs_gate.json")
    assert cert["passed"] is False and cert["wsvec_sha256"] == hashlib.sha256(open(bad, "rb").read()).hexdigest()
    assert call("trs_gate.py", model, "--no-wsvec")[0] == 0
    with open(model, "a") as fh:                                # a file with more numbers than the header gives
        fh.write("    0    0    0    1    1    0.000000    0.000000\n")
    assert call("trs_gate.py", model)[0] == 2


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
    assert code == 1 and "FAIL  W6" in out and "SHA-256" in out and "PREFLIGHT REFUSED" in out


def test_preflight_refuses_a_wsvec_file_that_changed_after_the_gate(tmp_path):   # must-fail control, rule W17
    H = spinor()
    wsvec = write_wsvec(tmp_path / "model_wsvec.dat", H, {})                 # next to model_hr.dat
    job, model = job_folder(tmp_path, H=H)
    assert load(model + ".trs_gate.json")["wsvec_file"] == "model_wsvec.dat" and call("preflight.py", job)[0] == 0
    write_wsvec(wsvec, H, {((1, 0, 0), 1, 3): [(1, 0, 0)], ((-1, 0, 0), 3, 1): [(-1, 0, 0)]})
    code, out, _ = call("preflight.py", job)
    assert code == 1 and "FAIL  W6" in out and "wsvec" in out
    assert call("trs_gate.py", model)[0] == 1                               # the new images break E(k) = E(-k)
    assert call("trs_gate.py", model, "--no-wsvec")[0] == 0 and call("preflight.py", job)[0] == 0
    (tmp_path / "job.json").write_text(json.dumps(dict(load(job), wsvec="model_wsvec.dat")))
    assert call("preflight.py", job)[0] == 1                                # the job names the file: no exception


def test_preflight_refuses_a_failed_gate_and_half_zone_doubling(tmp_path):  # must-fail control
    job, model = job_folder(tmp_path, H=spinless(broken=1e-4))
    code, out, _ = call("preflight.py", job)
    assert code == 1 and "FAIL  W6" in out and "FAIL  B7" in out and "Do not use a k/-k average" in out
    cert = load(model + ".trs_gate.json")                       # an edited certificate stays refused
    cert["passed"] = True
    with open(model + ".trs_gate.json", "w") as fh:
        json.dump(cert, fh)
    assert call("preflight.py", job)[0] == 1
    os.remove(model + ".trs_gate.json")                         # no certificate
    assert call("preflight.py", job)[0] == 1


def test_preflight_refuses_bad_scales_and_a_missing_control(tmp_path):      # must-fail controls
    job, _ = job_folder(tmp_path, scales={"yxx": [1e-6, 5e-4], "yyy": 1e-3})
    code, out, _ = call("preflight.py", job)
    assert code == 1 and "FAIL  B3" in out and "yxx[0]" in out and "PASS  W6" in out
    job, _ = job_folder(tmp_path, forbidden_control=None)
    code, out, _ = call("preflight.py", job)
    assert code == 1 and "FAIL  S8" in out
    job, _ = job_folder(tmp_path, forbidden_control="zzz")
    assert call("preflight.py", job)[0] == 1


def test_preflight_reads_the_keys_from_the_config_file(tmp_path):
    job, _ = job_folder(tmp_path)
    data = load(job)
    data["inputs"] = {"tb_file": data.pop("model")}
    data["control"] = data.pop("forbidden_control")
    (tmp_path / "job.json").write_text(json.dumps(data))
    assert call("preflight.py", job, "--project", tmp_path)[0] == 1          # the default keys do not fit
    (tmp_path / "dft_gates.json").write_text(json.dumps({"fields": {"model": "inputs.tb_file",
                                                                    "forbidden_control": "control"}}))
    assert call("preflight.py", job, "--project", tmp_path)[0] == 0
    (tmp_path / "dft_gates.json").write_text(json.dumps({"launch_pattern": ["x"]}))
    assert call("preflight.py", job, "--project", tmp_path)[0] == 2          # a typo in a key is an error


def test_hook_blocks_only_a_launch_of_a_refused_job(tmp_path):              # must-fail control
    job, model = job_folder(tmp_path)

    def hook(command):
        event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(tmp_path),
                 "tool_input": {"command": command}}
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path))
        return call("preflight.py", "--hook", stdin=json.dumps(event), env=env)

    launch = "nohup julia scan_worker.jl " + str(tmp_path) + " 3 > worker_3.log 2>&1 &"     # names the job folder
    assert hook(launch) == (0, "", "")
    with open(model, "a") as fh:
        fh.write("\n")
    code, out, err = hook(launch)
    assert code == 2 and out == "" and "Blocked by the preflight hook" in err and "SHA-256" in err
    assert hook("ls -la job.json")[0] == 0                                   # not a launch command
    assert hook("pgrep -fl scan_worker")[0] == 0                             # no job file in the command
    driver = "python3 run_scan.py --job=job.json --workers 8"
    assert hook(driver)[0] == 0                                              # not a launch pattern by default
    (tmp_path / "dft_gates.json").write_text(json.dumps({"launch_patterns": ["run_scan\\.py"]}))
    assert hook(driver)[0] == 2                                              # the project config adds the pattern
    (tmp_path / "dft_gates.json").write_text("{not json")
    assert hook(launch)[0] == 2 and hook("ls -la")[0] == 0                   # a bad config file blocks a launch only


# ---- live_workers.py -------------------------------------------------------------------------------------------

@pytest.mark.skipif(shutil.which("pgrep") is None, reason="pgrep is not available")
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
