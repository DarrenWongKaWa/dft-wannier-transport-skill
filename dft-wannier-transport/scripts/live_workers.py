#!/usr/bin/env python3
"""Refuse a move or a rename while worker processes are alive (rule R6 of the dft-wannier-transport skill).

    python3 live_workers.py [--pattern REGEX ...] && mv OLD NEW

Each pattern is a regular expression. The script compares it with the full command line of each process, as
`pgrep -f` does. Without --pattern, it uses the pattern of rule R6, with vasp_ncl, vasp_gam and postw90.x added.
It ignores itself and every process that started it, for example the shell of a wait loop (rule R20).

Exit code: 0 = no worker process is alive. 1 = refused: worker processes are alive. 2 = the check did not run.
Only the standard library and ps are necessary.
"""
import argparse
import os
import re
import subprocess
import sys

R6_PATTERNS = [r"scan_worker|vasp_std|vasp_ncl|vasp_gam|wannier90\.x|postw90\.x|julia"]
REFUSED = """Do not move, rename or relocate the tree now (R6). A worker that opens a file during the move stops.
Next steps:
1. Wait until the workers exit. Or pause the queue with marker claims (R15).
2. Run this check again.
3. Move the tree only after this check passes."""


def live(patterns):
    """Return [(pid, command line)] of the processes that match, without this script and the processes above it."""
    regex = [re.compile(p) for p in patterns]
    ps = subprocess.Popen(["ps", "-A", "-ww", "-o", "pid=", "-o", "ppid=", "-o", "command="],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = ps.communicate()
    if ps.returncode != 0:
        raise RuntimeError(err.strip() or f"ps exit code {ps.returncode}")
    table = {}
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            table[int(parts[0])] = (int(parts[1]), parts[2] if len(parts) > 2 else "")
    skip, pid = {ps.pid}, os.getpid()
    while pid > 1 and pid not in skip:                   # R20: a calling shell has the pattern in its command line
        skip.add(pid)
        pid = table.get(pid, (0, ""))[0]
    return sorted((p, cmd) for p, (_, cmd) in table.items() if p not in skip and any(r.search(cmd) for r in regex))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pattern", action="append", help="regular expression for the command line of a worker "
                    "(you can repeat it)")
    patterns = ap.parse_args(argv).pattern or R6_PATTERNS
    try:
        found = live(patterns)
    except (OSError, RuntimeError, re.error) as err:
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
