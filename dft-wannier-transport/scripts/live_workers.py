#!/usr/bin/env python3
"""Refuse a move or a rename while worker processes are alive (rule R6 of the dft-wannier-transport skill).

    python3 live_workers.py [--pattern REGEX ...] && mv OLD NEW

Each pattern is a pgrep pattern: `pgrep -f` compares it with the full command line of each process.
Without --pattern, the script uses the pattern of rule R6. It ignores itself and the shells that call it (rule R20).

Exit code: 0 = no worker process is alive. 1 = refused: worker processes are alive. 2 = pgrep did not run.
Only the standard library and pgrep are necessary.
"""
import argparse
import os
import subprocess
import sys

R6_PATTERNS = ["scan_worker|vasp_std|wannier90.x|julia"]
REFUSED = """Do not move, rename or relocate the tree now (R6). A worker that opens a file during the move stops.
Next steps:
1. Wait until the workers exit. Or pause the queue with marker claims (R15).
2. Run this check again.
3. Move the tree only after this check passes."""


def live(pattern):
    """Return [(pid, command line)] of the processes that match, without this script and its callers."""
    done = subprocess.run(["pgrep", "-fl", pattern], capture_output=True, text=True)
    if done.returncode not in (0, 1):
        raise RuntimeError(done.stderr.strip() or f"pgrep exit code {done.returncode}")
    found = []
    for line in done.stdout.splitlines():
        pid, _, command = line.strip().partition(" ")
        if not pid.isdigit():
            continue
        try:                                             # Linux: pgrep -fl prints the name only
            with open(f"/proc/{pid}/cmdline") as fh:
                command = fh.read().replace("\0", " ").strip() or command
        except OSError:
            pass
        if int(pid) in (os.getpid(), os.getppid()) or "live_workers" in command:
            continue                                     # R20: a calling shell has the pattern in its command line
        found.append((int(pid), command))
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pattern", action="append", help="pgrep pattern of the worker processes (you can repeat it)")
    patterns = ap.parse_args(argv).pattern or R6_PATTERNS
    try:
        found = sorted({item for pattern in patterns for item in live(pattern)})
    except (OSError, RuntimeError) as err:
        print(f"live_workers: cannot do the check: {err}", file=sys.stderr)
        return 2
    shown = " ".join(repr(p) for p in patterns)
    if not found:
        print(f"live_workers: PASS. No process matches {shown}.")
        print("You can move the tree now. Start no worker during the move.")
        return 0
    print(f"live_workers: REFUSED. Worker processes are alive: {len(found)} (patterns {shown}).")
    for pid, command in found:
        print(f"  {pid:>7}  {command[:160]}")
    print(REFUSED)
    return 1


if __name__ == "__main__":
    sys.exit(main())
