#!/usr/bin/env python3
"""Time-reversal gate for a Wannier tight-binding model (rule W6 of the dft-wannier-transport skill).

    python3 trs_gate.py MODEL [--wsvec FILE | --no-wsvec] [--json CERTIFICATE] [--nk 2000] [--seed 0] [--tol 1e-5]

MODEL is a Wannier90 `*_hr.dat` or `*_tb.dat` file. The gate computes max |E(k) - E(-k)| at random k, for
all bands, in the whole Brillouin zone. It writes a certificate (JSON) with the SHA-256 of each file it read.
The images in `*_wsvec.dat` change the bands (rule W17). Thus the gate reads `NAME_wsvec.dat` if it is next to
`NAME_hr.dat` or `NAME_tb.dat`. --wsvec gives a different file. Use --no-wsvec only if the engine ignores the images.

Exit code: 0 = pass. 1 = fail: do not integrate this model. 2 = bad input. numpy is necessary.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import warnings

try:
    import numpy as np
except ImportError:
    print("trs_gate: numpy is necessary. Use a Python that has numpy.", file=sys.stderr)
    sys.exit(2)

GATE = "W6-trs"
TOL_EV = 1e-5     # rule W6: refuse to integrate at or above this value
MIN_NK = 2000     # rule W6: number of random k

FAIL_TEXT = """FAIL  time-reversal gate (W6). Do not integrate this model.
      Do not continue with a k/-k average or with a real-part projection (W7, W17). They hide the cause.
      Next steps:
      1. Find the cause. For a spinor model, compare the wsvec images of each Kramers pair (W17).
         For other models, do the checks W1 to W5.
      2. Correct the model.
      3. Run this gate again. Start the scan only after the gate passes.
      If you cannot correct the model, stop. Tell the owner of the project."""


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def numbers(text, dtype=float):
    """All numbers of a text. The parser stops at the first token that is not a number. The callers count."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return np.fromstring(text, dtype=dtype, sep=" ")


def read_model(path):
    """Return (R[nR,3], degeneracy[nR], H[nR,nw,nw]) from a Wannier90 hr.dat or tb.dat file.

    H[r, m, n] is the element that the file prints with the orbital indices (m, n), in this sequence.
    """
    with open(path) as fh:
        fh.readline()
        first = fh.readline().split()
        is_tb = len(first) == 3                       # tb.dat: three lattice vectors come before num_wann
        if is_tb:
            fh.readline()
            fh.readline()
            first = fh.readline().split()
        nw = int(first[0])
        num = numbers(fh.read())
    nr = int(num[0])
    deg, body, n2 = num[1:1 + nr], num[1 + nr:], nw * nw
    width = 3 + 4 * n2 if is_tb else 7 * n2           # numbers for one R vector
    sizes = (nr * width, nr * width + nr * (3 + 8 * n2)) if is_tb else (nr * width,)   # with or without positions
    if nr < 1 or body.size not in sizes or not (deg > 0).all():
        raise ValueError(f"the file does not have {nr} blocks of {nw} x {nw} elements")
    block = body[:nr * width].reshape(nr, width)      # a tb.dat file continues with the position operator
    R = block[:, :3]
    if is_tb:
        rows = block[:, 3:].reshape(nr, n2, 4)
    else:
        rows = block.reshape(nr, n2, 7)[:, :, 3:]
        if not (block.reshape(nr, n2, 7)[:, :, :3] == R[:, None, :]).all():
            raise ValueError("a block has more than one R vector")
    m, n = rows[:, :, 0].astype(int) - 1, rows[:, :, 1].astype(int) - 1
    if not (np.sort(m * nw + n, axis=1) == np.arange(n2)).all():
        raise ValueError("a block does not list each orbital pair one time")
    H = np.zeros((nr, nw, nw), complex)
    H[np.arange(nr)[:, None], m, n] = rows[:, :, 2] + 1j * rows[:, :, 3]
    return R.astype(int), deg, H


def read_wsvec(path, R, nw):
    """Return (records[nR*nw*nw, 4], images[total, 3]) from a Wannier90 wsvec.dat file.

    One record = (index of R, m, n, number of images). The images of the records follow one after the other.
    """
    with open(path) as fh:
        fh.readline()
        w = numbers(fh.read(), int).tolist()
    index = {tuple(v): i for i, v in enumerate(R.tolist())}
    rec, images, pos = [], [], 0
    while pos + 5 < len(w):
        count = w[pos + 5]
        rec.append((index.get(tuple(w[pos:pos + 3]), -1), w[pos + 3] - 1, w[pos + 4] - 1, count))
        images += w[pos + 6:pos + 6 + 3 * count]
        pos += 6 + 3 * max(count, 0)
    good = len(rec) == len({x[:3] for x in rec}) == len(R) * nw * nw and len(images) == 3 * sum(x[3] for x in rec)
    if not good or not all(x[0] >= 0 and 0 <= x[1] < nw and 0 <= x[2] < nw and x[3] > 0 for x in rec):
        raise ValueError("the wsvec file does not list each (R, m, n) of the model one time")
    return np.array(rec), np.array(images).reshape(-1, 3)


def fold(R, deg, H, ws=None):
    """Return (vectors[nV,3], weights[nV,nw,nw]) with H(k) = sum over V of exp(2 pi i k.V) weights[V].

    Without wsvec: V = R, weights = H(R) / degeneracy(R). With wsvec: element (m, n) of H(R) goes in equal
    parts to the vectors R + T, one part for each image T that the file lists for (R, m, n).
    """
    if ws is None:
        return R, H / deg[:, None, None]
    rec, images = ws
    r, m, n, count = (np.repeat(col, rec[:, 3]) for col in rec.T)
    vec, inverse = np.unique(R[r] + images, axis=0, return_inverse=True)
    weights = np.zeros((len(vec),) + H.shape[1:], complex)
    np.add.at(weights, (inverse.reshape(-1), m, n), H[r, m, n] / (deg[r] * count))
    return vec, weights


def bands(vec, weights, k):
    """Band energies [nk, nw] at the fractional k points [nk, 3]."""
    nw = weights.shape[1]
    flat, out = weights.reshape(len(vec), nw * nw), np.empty((len(k), nw))
    step = max(1, 4_000_000 // (nw * nw))             # limits the memory for H(k)
    for i in range(0, len(k), step):
        with np.errstate(all="ignore"):               # some BLAS builds raise false matmul warnings
            phase = np.exp(2j * np.pi * (k[i:i + step] @ vec.T.astype(float)))
            Hk = (phase @ flat).reshape(-1, nw, nw)
        out[i:i + step] = np.linalg.eigvalsh((Hk + Hk.conj().transpose(0, 2, 1)) / 2)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model", help="Wannier90 *_hr.dat or *_tb.dat file")
    ap.add_argument("--wsvec", help="Wannier90 *_wsvec.dat file (default: NAME_wsvec.dat next to the model file)")
    ap.add_argument("--no-wsvec", action="store_true", help="read no wsvec file: the engine ignores the images")
    ap.add_argument("--json", help="path of the certificate (default: MODEL.trs_gate.json)")
    ap.add_argument("--nk", type=int, default=MIN_NK, help=f"number of random k (minimum {MIN_NK})")
    ap.add_argument("--seed", type=int, default=0, help="seed of the random k")
    ap.add_argument("--tol", type=float, default=TOL_EV, help=f"limit in eV (maximum {TOL_EV:g}, rule W6)")
    a = ap.parse_args(argv)
    if a.nk < MIN_NK or not 0 < a.tol <= TOL_EV:
        print(f"trs_gate: rule W6 needs --nk >= {MIN_NK} and --tol <= {TOL_EV:g} eV.", file=sys.stderr)
        return 2
    out = a.json or a.model + ".trs_gate.json"
    near = re.sub(r"_(hr|tb)\.dat$", "_wsvec.dat", a.model)
    wsvec = None if a.no_wsvec else a.wsvec or (near if near != a.model and os.path.isfile(near) else None)
    try:
        R, deg, H = read_model(a.model)
        nw = H.shape[1]
        vec, weights = fold(R, deg, H, read_wsvec(wsvec, R, nw) if wsvec else None)
        k = np.random.default_rng(a.seed).uniform(-0.5, 0.5, size=(a.nk, 3))
        asym = np.abs(bands(vec, weights, k) - bands(vec, weights, -k))
        if not np.isfinite(asym).all():
            raise ValueError("the band energies are not finite")
        worst, band = float(asym.max()), int(np.unravel_index(asym.argmax(), asym.shape)[1]) + 1
        cert = {"gate": GATE, "passed": worst < a.tol, "max_asym_eV": worst, "tol_eV": a.tol, "nk": a.nk,
                "seed": a.seed, "num_wann": nw, "worst_band": band,
                "model_file": os.path.basename(a.model), "model_sha256": sha256(a.model),
                "wsvec_file": os.path.basename(wsvec) if wsvec else None,
                "wsvec_sha256": sha256(wsvec) if wsvec else None, "no_wsvec": a.no_wsvec}
        with open(out, "w") as fh:
            json.dump(cert, fh, indent=1)
            fh.write("\n")
    except (OSError, ValueError, IndexError) as err:
        print(f"trs_gate: cannot do the test: {err}", file=sys.stderr)
        return 2
    print(f"trs_gate  model={cert['model_file']}  sha256={cert['model_sha256'][:12]}  "
          f"wannier functions={nw}  R vectors={len(R)}")
    if wsvec:
        print(f"  wsvec file         = {cert['wsvec_file']}  sha256={cert['wsvec_sha256'][:12]}"
              + ("" if a.wsvec else "  (found next to the model file)"))
    print(f"  max |Im H(R)|      = {np.abs(H.imag).max():.2e} eV")
    print(f"  max |E(k) - E(-k)| = {worst:.2e} eV  ({a.nk} random k, all {nw} bands, whole zone, worst band {band})")
    print(f"  tolerance (W6)     = {a.tol:.1e} eV")
    print(f"  certificate        = {out}")
    if not cert["passed"]:
        print(FAIL_TEXT)
        return 1
    print("PASS  time-reversal gate (W6). Half-zone integration (B7) is permitted for these file contents.")
    if not wsvec:
        print("NOTE  The gate read no wsvec file. If the engine uses use_ws_distance, run the gate again")
        print("      with --wsvec (W17).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
