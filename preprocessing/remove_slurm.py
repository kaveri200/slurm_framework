#!/usr/bin/env python3
"""
preprocessing/remove_slurm.py  (WSL Edition)
Removes Slurm, Munge, hwloc source builds cleanly.
Must be run as root (sudo).
"""

import os
import sys
import shutil
import subprocess

sys.path.insert(0, os.path.dirname(__file__))
from health import check_health, HEALTHY, BROKEN, NOT_INSTALLED


def run(cmd: str):
    subprocess.run(cmd, shell=True)


def rmtree(path: str):
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)
        print(f"  [REMOVED] {path}")


def rm(path: str):
    if os.path.exists(path):
        os.remove(path)
        print(f"  [REMOVED] {path}")


def section(title: str):
    print(f"\n{'─'*50}")
    print(f"  {title}")
    print(f"{'─'*50}\n")


def perform_cleanup():

    section("Stopping Slurm services")
    for svc in ("slurmd", "slurmctld", "slurmdbd"):
        run(f"systemctl stop    {svc} 2>/dev/null")
        run(f"systemctl disable {svc} 2>/dev/null")

    section("Stopping Munge")
    run("systemctl stop    munge 2>/dev/null")
    run("systemctl disable munge 2>/dev/null")

    section("Removing Slurm binaries")
    for path in ("/usr/local/bin/s*", "/usr/local/sbin/slurm*",
                 "/usr/local/lib/slurm", "/usr/local/include/slurm",
                 "/usr/local/share/doc/slurm*"):
        run(f"rm -rf {path} 2>/dev/null")

    section("Removing Slurm config and data")
    for p in ("/etc/slurm",
              "/var/spool/slurmd",
              "/var/spool/slurmctld",
              "/var/log/slurm",
              "/var/log/slurmctld.log",
              "/var/log/slurmdbd.log"):
        rmtree(p) if os.path.isdir(p) else rm(p)

    section("Removing Munge")
    for p in ("/etc/munge",
              "/usr/local/var/log/munge",
              "/usr/local/var/run/munge",
              "/usr/local/sbin/munge*",
              "/usr/local/bin/munge*",
              "/usr/local/lib/libmunge*"):
        run(f"rm -rf {p} 2>/dev/null")

    section("Removing systemd units")
    for svc_file in (
        "/usr/local/lib/systemd/system/slurmctld.service",
        "/usr/local/lib/systemd/system/slurmd.service",
        "/usr/local/lib/systemd/system/slurmdbd.service",
        "/etc/systemd/system/slurmctld.service",
        "/etc/systemd/system/slurmd.service",
        "/etc/systemd/system/slurmdbd.service",
        "/etc/systemd/system/munge.service",
    ):
        rm(svc_file)

    run("systemctl daemon-reload")

    section("Removing MySQL Slurm database")
    run("mysql -u root -e \"DROP DATABASE IF EXISTS slurm_acct_db\" 2>/dev/null")
    run("mysql -u root -e \"DROP USER IF EXISTS 'slurm'@'localhost'\" 2>/dev/null")

    section("Removing system users")
    for user in ("slurm", "munge"):
        r = subprocess.run(f"id {user}", shell=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            run(f"userdel {user} 2>/dev/null || true")
            print(f"  [REMOVED] user: {user}")
        else:
            print(f"  [SKIP]    user {user} not found")

    print("\n[DONE] Slurm has been fully removed.\n")


def main():
    print("===== SLURM CLEANUP MODULE (WSL Edition) =====\n")

    if os.geteuid() != 0:
        print("[ERROR] Run with sudo.")
        sys.exit(1)

    state = check_health()

    if state == NOT_INSTALLED:
        print("[INFO] Slurm is not installed. Nothing to clean up.")
        sys.exit(0)

    if state == BROKEN:
        print("[WARN] Slurm is BROKEN. Removing automatically...\n")
        perform_cleanup()
        sys.exit(0)

    if state == HEALTHY:
        print("[INFO] Slurm is currently HEALTHY and running.\n")
        try:
            choice = input(
                "  Slurm is healthy. Are you sure you want to remove it? (yes/no): "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n[INFO] Cleanup cancelled.")
            sys.exit(0)

        if choice not in ("yes", "y"):
            print("[INFO] Cleanup cancelled.")
            sys.exit(0)

        perform_cleanup()


if __name__ == "__main__":
    main()
