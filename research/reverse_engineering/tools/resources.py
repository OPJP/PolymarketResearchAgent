"""Memory and disk gate for the deep reverse-engineering agents.

Several agents share one machine, so each checks the machine before starting
a heavy job or a large download:

    .venv/Scripts/python.exe research/reverse_engineering/tools/resources.py
    .venv/Scripts/python.exe research/reverse_engineering/tools/resources.py --wait-mem 1500
    .venv/Scripts/python.exe research/reverse_engineering/tools/resources.py --need-disk 5000

Prints available memory and free disk (MB). --wait-mem blocks until at least
that many MB of physical memory are available (polling every 20 s, giving up
after --timeout seconds with exit code 2). --need-disk exits with code 3 when
free disk on the repository's drive is below that many MB.
"""

from __future__ import annotations

import argparse
import ctypes
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def available_mb() -> float:
    if sys.platform == "win32":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
        return st.ullAvailPhys / 2**20
    with open("/proc/meminfo") as f:
        info = {line.split(":")[0]: line.split()[1] for line in f}
    return int(info["MemAvailable"]) / 1024


def commit_headroom_mb() -> float | None:
    """Windows commit charge headroom (allocations fail when it reaches 0)."""
    if sys.platform != "win32":
        return None

    class PERFORMANCE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("CommitTotal", ctypes.c_size_t),
            ("CommitLimit", ctypes.c_size_t),
            ("CommitPeak", ctypes.c_size_t),
            ("PhysicalTotal", ctypes.c_size_t),
            ("PhysicalAvailable", ctypes.c_size_t),
            ("SystemCache", ctypes.c_size_t),
            ("KernelTotal", ctypes.c_size_t),
            ("KernelPaged", ctypes.c_size_t),
            ("KernelNonpaged", ctypes.c_size_t),
            ("PageSize", ctypes.c_size_t),
            ("HandleCount", ctypes.c_ulong),
            ("ProcessCount", ctypes.c_ulong),
            ("ThreadCount", ctypes.c_ulong),
        ]

    pi = PERFORMANCE_INFORMATION()
    pi.cb = ctypes.sizeof(PERFORMANCE_INFORMATION)
    ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(pi), pi.cb)
    return (pi.CommitLimit - pi.CommitTotal) * pi.PageSize / 2**20


def free_disk_mb() -> float:
    return shutil.disk_usage(REPO).free / 2**20


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait-mem", type=float, default=0.0)
    ap.add_argument("--need-disk", type=float, default=0.0)
    ap.add_argument("--timeout", type=float, default=1800.0)
    a = ap.parse_args()

    t0 = time.time()
    while True:
        mem = available_mb()
        commit = commit_headroom_mb()
        ok = mem >= a.wait_mem and (commit is None or commit >= a.wait_mem)
        if ok or a.wait_mem <= 0:
            break
        if time.time() - t0 > a.timeout:
            print(f"timeout: available {mem:.0f} MB, commit headroom {commit} MB < {a.wait_mem:.0f} MB")
            return 2
        time.sleep(20)
    disk = free_disk_mb()
    waited = time.time() - t0
    commit_s = "n/a" if commit is None else f"{commit:.0f} MB"
    print(f"available memory {mem:.0f} MB, commit headroom {commit_s}, free disk {disk:.0f} MB, waited {waited:.0f} s")
    if a.need_disk and disk < a.need_disk:
        print(f"low disk: {disk:.0f} MB free < {a.need_disk:.0f} MB; do not download more, delete intermediates")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
