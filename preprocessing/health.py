#!/usr/bin/env python3
"""
preprocessing/health.py  (WSL Edition)
Checks health of Slurm installation built from source.
 
In WSL, services are often started manually (not via systemd),
so we check both systemctl AND ps aux for each process.
 
Import:  from health import check_health, HEALTHY, BROKEN, NOT_INSTALLED
Run:     python3 health.py
"""
 
import os
import subprocess
import shutil
import sys
 
# ── Return codes ─────────────────────────────────────────────────
HEALTHY       = 0
BROKEN        = 1
NOT_INSTALLED = 2
 
 
# ── Helpers ──────────────────────────────────────────────────────
 
def _cmd_ok(cmd: str) -> bool:
    return subprocess.run(cmd, shell=True,
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0
 
 
def _sinfo_binary() -> str | None:
    for path in ("/usr/local/bin/sinfo",
                 "/usr/bin/sinfo",
                 shutil.which("sinfo") or ""):
        if path and os.path.isfile(path):
            return path
    return None
 
 
def _process_running(name: str) -> bool:
    """Check if a process is running via ps aux (WSL-safe)."""
    result = subprocess.run(
        f"ps aux | grep -E '[/]{name}|^[^ ]+ +[0-9]+ .* {name}' | grep -v grep",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )
    return result.returncode == 0 and bool(result.stdout.strip())
 
 
def _service_or_process_active(svc: str, process: str = None) -> bool:
    """
    Returns True if service is active via systemctl OR process is running via ps.
    This handles both systemd-managed and manually-started services (common in WSL).
    """
    process = process or svc
 
    # Check systemctl first
    if _cmd_ok(f"systemctl is-active --quiet {svc}"):
        return True
 
    # Fall back to ps aux check
    return _process_running(process)
 
 
# ── Public API ────────────────────────────────────────────────────
 
def check_health() -> int:
    """
    Returns HEALTHY / BROKEN / NOT_INSTALLED
    """
 
    # 1. Binary present?
    if _sinfo_binary() is None:
        return NOT_INSTALLED
 
    # 2. Config present?
    if not os.path.isfile("/etc/slurm/slurm.conf"):
        return NOT_INSTALLED
 
    # 3. Check each service/process
    checks = {
        "munge":     ("munge",     "munged"),
        "slurmdbd":  ("slurmdbd",  "slurmdbd"),
        "slurmctld": ("slurmctld", "slurmctld"),
        "slurmd":    ("slurmd",    "slurmd"),
    }
 
    for svc, (systemd_name, process_name) in checks.items():
        if not _service_or_process_active(systemd_name, process_name):
            return BROKEN
 
    # 4. sinfo actually responds?
    if not _cmd_ok(_sinfo_binary()):
        return BROKEN
 
    return HEALTHY
 
 
# ── Standalone ────────────────────────────────────────────────────
 
def _label(state: int) -> str:
    return {
        HEALTHY:       "HEALTHY ✔",
        BROKEN:        "BROKEN ✘",
        NOT_INSTALLED: "NOT INSTALLED"
    }.get(state, "UNKNOWN")
 
 
def _check_display(svc: str, process: str) -> tuple:
    """Returns (is_ok, how_it_was_detected)"""
    if _cmd_ok(f"systemctl is-active --quiet {svc}"):
        return True, "systemctl"
    if _process_running(process):
        return True, "process"
    return False, "not found"
 
 
def main():
    print("===== SLURM HEALTH CHECK (WSL) =====\n")
 
    sinfo = _sinfo_binary()
    print(f"  Binary  (sinfo)      : {'✔  ' + sinfo if sinfo else '✘  not found'}")
 
    conf = "/etc/slurm/slurm.conf"
    print(f"  Config  (slurm.conf) : {'✔  ' + conf if os.path.isfile(conf) else '✘  not found'}")
 
    dbd_conf = "/etc/slurm/slurmdbd.conf"
    print(f"  Config  (slurmdbd)   : {'✔  ' + dbd_conf if os.path.isfile(dbd_conf) else '✘  not found'}")
 
    print()
 
    checks = [
        ("munge",     "munged"),
        ("mysql",     "mysqld"),
        ("slurmdbd",  "slurmdbd"),
        ("slurmctld", "slurmctld"),
        ("slurmd",    "slurmd"),
    ]
 
    for svc, process in checks:
        ok, how = _check_display(svc, process)
        if ok:
            print(f"  Service {svc:<14}: ✔  active  [{how}]")
        else:
            print(f"  Service {svc:<14}: ✘  inactive/missing")
 
    if sinfo:
        ok = _cmd_ok(sinfo)
        print(f"\n  sinfo   response     : {'✔  ok' if ok else '✘  error'}")
 
    state = check_health()
    print(f"\n  Overall State        : {_label(state)}\n")
    sys.exit(state)
 
 
if __name__ == "__main__":
    main()
