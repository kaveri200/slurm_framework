#!/usr/bin/env python3
"""
preprocessing/install_slurm.py  (WSL Edition)
Installs Slurm 24.11.1 from source — mirrors install_slurm.sh in Python.
Must be run as root (sudo).
"""

import os
import sys
import subprocess
import shutil
import platform
import time

sys.path.insert(0, os.path.dirname(__file__))
from health import check_health, HEALTHY, BROKEN, NOT_INSTALLED

# ── Versions & URLs ───────────────────────────────────────────────
SLURM_VERSION  = "24.11.1"
MUNGE_VERSION  = "0.5.16"
HWLOC_VERSION  = "2.11.2"

DOWNLOAD_DIR   = "/root"

SLURM_TAR  = f"slurm-{SLURM_VERSION}.tar.bz2"
MUNGE_TAR  = f"munge-{MUNGE_VERSION}.tar.xz"
HWLOC_TAR  = f"hwloc-{HWLOC_VERSION}.tar.bz2"

SLURM_URL  = f"https://download.schedmd.com/slurm/{SLURM_TAR}"
MUNGE_URL  = f"https://github.com/dun/munge/releases/download/munge-{MUNGE_VERSION}/{MUNGE_TAR}"
HWLOC_URL  = f"https://download.open-mpi.org/release/hwloc/v2.11/{HWLOC_TAR}"

SLURM_CONF    = "/etc/slurm/slurm.conf"
CGROUP_CONF   = "/etc/slurm/cgroup.conf"
SLURMDBD_CONF = "/etc/slurm/slurmdbd.conf"

NPROC = os.cpu_count() or 2


# ── Helpers ───────────────────────────────────────────────────────

def run(cmd: str, check: bool = False) -> int:
    result = subprocess.run(cmd, shell=True)
    if check and result.returncode != 0:
        print(f"[ERROR] Command failed: {cmd}")
        sys.exit(1)
    return result.returncode


def run_quiet(cmd: str) -> int:
    return subprocess.run(cmd, shell=True,
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode


def cmd_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def user_exists(user: str) -> bool:
    return run_quiet(f"id {user}") == 0


def section(title: str):
    print(f"\n{'─'*50}")
    print(f"  {title}")
    print(f"{'─'*50}\n")


# ── Step 1 — System packages ──────────────────────────────────────

def install_system_packages():
    section("STEP 1: Installing system packages")

    run("apt-get update -y", check=True)

    packages = [
        "build-essential", "libssl-dev",
        "libglib2.0-dev", "libgtk2.0-dev", "libgtk2.0-doc",
        "devhelp", "libdbus-1-dev",
        "mysql-server", "libmysqlclient-dev",
        "mysql-common",
        "wget", "bzip2", "xz-utils",
    ]

    # Check and install only missing packages
    missing = []
    for pkg in packages:
        if run_quiet(f"dpkg -s {pkg}") != 0:
            missing.append(pkg)
        else:
            print(f"  [SKIP]    {pkg} already installed")

    if missing:
        print(f"\n  [INSTALL] {' '.join(missing)}\n")
        run(f"apt-get install -y {' '.join(missing)}", check=True)

    # Start MySQL
    run("systemctl start mysql")
    run("systemctl enable mysql")
    print("\n  [OK] System packages ready.")


# ── Step 2 — Download tarballs ────────────────────────────────────

def download_files():
    section("STEP 2: Downloading source tarballs")

    downloads = [
        (SLURM_URL, os.path.join(DOWNLOAD_DIR, SLURM_TAR)),
        (MUNGE_URL, os.path.join(DOWNLOAD_DIR, MUNGE_TAR)),
        (HWLOC_URL, os.path.join(DOWNLOAD_DIR, HWLOC_TAR)),
    ]

    for url, dest in downloads:
        if os.path.isfile(dest):
            print(f"  [SKIP]    {os.path.basename(dest)} already downloaded")
        else:
            print(f"  [DOWNLOAD] {os.path.basename(dest)}")
            run(f"wget -q --show-progress -P {DOWNLOAD_DIR} {url}", check=True)

    print("\n  [OK] All tarballs ready.")


# ── Step 3 — Build Munge ─────────────────────────────────────────

def build_munge():
    section("STEP 3: Building Munge from source")

    # Create munge user
    if not user_exists("munge"):
        print("  [CREATE] munge user")
        run("useradd --system --no-create-home munge 2>/dev/null || true")
    else:
        print("  [SKIP]   munge user already exists")

    munge_src = os.path.join(DOWNLOAD_DIR, f"munge-{MUNGE_VERSION}")

    if not os.path.isdir(munge_src):
        print("  [EXTRACT] munge tarball")
        run(f"tar -xf {DOWNLOAD_DIR}/{MUNGE_TAR} -C {DOWNLOAD_DIR}", check=True)

    if cmd_exists("munged"):
        print("  [SKIP]   munge already built/installed")
    else:
        print("  [BUILD]  munge")
        run(f"cd {munge_src} && ./configure --sysconfdir=/etc/ --libdir=/usr/lib", check=True)
        run(f"cd {munge_src} && make -j{NPROC}", check=True)
        run(f"cd {munge_src} && make -j{NPROC} install", check=True)
        print("  [OK] Munge compiled.")

    # Munge key
    if not os.path.isfile("/etc/munge/munge.key"):
        print("  [GENERATE] munge key")
        run("/usr/local/sbin/mungekey", check=True)
    else:
        print("  [SKIP]   munge.key already exists")

    # Permissions
    print("  [PERMS]  setting munge permissions")
    run("chown -R munge: /etc/munge/")
    run("chown -R munge:munge /usr/local/var/log/munge/ 2>/dev/null || true")
    run("mkdir -p /usr/local/var/run/munge")
    run("chmod 0700 /etc/munge/ /usr/local/var/run/munge")
    run("chmod 755 /usr/local/var/run/munge/")
    run("chown munge:munge /usr/local/var/run/munge")

    # Start munge
    run("systemctl enable munge")
    run("systemctl restart munge")
    time.sleep(2)

    if run_quiet("systemctl is-active --quiet munge") == 0:
        print("  [OK] Munge is active.\n")
    else:
        print("  [ERROR] Munge failed to start.")
        run("journalctl -u munge -n 20 --no-pager")
        sys.exit(1)


# ── Step 4 — Build hwloc ─────────────────────────────────────────

def build_hwloc():
    section("STEP 4: Building hwloc from source")

    hwloc_src = os.path.join(DOWNLOAD_DIR, f"hwloc-{HWLOC_VERSION}")

    if not os.path.isdir(hwloc_src):
        print("  [EXTRACT] hwloc tarball")
        run(f"tar -xf {DOWNLOAD_DIR}/{HWLOC_TAR} -C {DOWNLOAD_DIR}", check=True)

    if os.path.isfile("/usr/local/lib/libhwloc.so") or \
       os.path.isfile("/usr/local/lib/libhwloc.a"):
        print("  [SKIP]   hwloc already built/installed")
        return

    print(f"  [BUILD]  hwloc using {NPROC} cores")
    run(f"cd {hwloc_src} && ./configure", check=True)
    run(f"cd {hwloc_src} && make -j{NPROC}", check=True)
    run(f"cd {hwloc_src} && make -j{NPROC} install", check=True)
    print("  [OK] hwloc installed.")


# ── Step 5 — Build Slurm ─────────────────────────────────────────

def build_slurm():
    section("STEP 5: Building Slurm from source")

    # Create slurm user
    if not user_exists("slurm"):
        print("  [CREATE] slurm user")
        run("useradd --system --no-create-home slurm 2>/dev/null || true")
    else:
        print("  [SKIP]   slurm user already exists")

    # Create /etc/slurm
    os.makedirs("/etc/slurm", exist_ok=True)
    run("chown slurm:slurm /etc/slurm")

    slurm_src = os.path.join(DOWNLOAD_DIR, f"slurm-{SLURM_VERSION}")

    if not os.path.isdir(slurm_src):
        print("  [EXTRACT] slurm tarball")
        run(f"tar -xf {DOWNLOAD_DIR}/{SLURM_TAR} -C {DOWNLOAD_DIR}", check=True)

    if shutil.which("sinfo"):
        print("  [SKIP]   Slurm already built/installed")
        return

    print(f"  [BUILD]  Slurm {SLURM_VERSION} using {NPROC} cores")
    run(f"cd {slurm_src} && ./configure "
        f"--sysconfdir=/etc/slurm "
        f"--with-munge=/usr/local/ "
        f"--with-hwloc=/usr/local/", check=True)
    run(f"cd {slurm_src} && make -j{NPROC}", check=True)
    run(f"cd {slurm_src} && make -j{NPROC} install", check=True)
    print("  [OK] Slurm installed.")


# ── Step 6 — Create configs ───────────────────────────────────────

def create_configs():
    section("STEP 6: Creating configuration files")

    hostname = platform.node()

    # ── slurm.conf ────────────────────────────────────────────────
    if not os.path.isfile(SLURM_CONF):
        print("  [CREATE] slurm.conf")

        # Get node hardware info from slurmd -C
        result = subprocess.run("slurmd -C 2>/dev/null | head -n1",
                                shell=True, capture_output=True, text=True)
        node_line = result.stdout.strip() if result.returncode == 0 else \
            f"NodeName={hostname} CPUs={NPROC} RealMemory=1024 State=UNKNOWN"

        conf = f"""ClusterName=HPC
SlurmctldHost={hostname}
MpiDefault=none
ProctrackType=proctrack/cgroup
SlurmctldPidFile=/var/run/slurmctld.pid
SlurmctldPort=6817
SlurmdPidFile=/var/run/slurmd.pid
SlurmdPort=6818
SlurmdSpoolDir=/var/spool/slurmd
SlurmUser=slurm
StateSaveLocation=/var/spool/slurmctld
SwitchType=switch/none
TaskPlugin=task/affinity
AuthType=auth/munge
SlurmctldTimeout=120
SlurmdTimeout=300
SchedulerType=sched/backfill
SelectType=select/cons_tres
AccountingStorageType=accounting_storage/slurmdbd
JobCompType=jobcomp/none
JobAcctGatherFrequency=30
JobAcctGatherType=jobacct_gather/none
SlurmctldDebug=info
SlurmctldLogFile=/var/log/slurm/slurmctld.log
SlurmdDebug=info
SlurmdLogFile=/var/log/slurm/slurmd.log
{node_line}
PartitionName=caribou_node Nodes=ALL Default=YES MaxTime=INFINITE State=UP
"""
        with open(SLURM_CONF, "w") as f:
            f.write(conf)
        print(f"  [OK]    {SLURM_CONF}")
    else:
        print(f"  [SKIP]  {SLURM_CONF} already exists")

    # ── cgroup.conf ───────────────────────────────────────────────
    if not os.path.isfile(CGROUP_CONF):
        print("  [CREATE] cgroup.conf")
        with open(CGROUP_CONF, "w") as f:
            f.write("ConstrainCores=yes\n"
                    "ConstrainDevices=yes\n"
                    "ConstrainRAMSpace=yes\n"
                    "ConstrainSwapSpace=yes\n")
        print(f"  [OK]    {CGROUP_CONF}")
    else:
        print(f"  [SKIP]  {CGROUP_CONF} already exists")

    # ── slurmdbd.conf ─────────────────────────────────────────────
    if not os.path.isfile(SLURMDBD_CONF):
        print("  [CREATE] slurmdbd.conf")
        dbd = """AuthType=auth/munge
DbdHost=localhost
SlurmUser=slurm
DebugLevel=verbose
LogFile=/var/log/slurmdbd.log
PidFile=/etc/slurm/slurmdbd.pid
StorageType=accounting_storage/mysql
StorageLoc=slurm_acct_db
"""
        with open(SLURMDBD_CONF, "w") as f:
            f.write(dbd)
        print(f"  [OK]    {SLURMDBD_CONF}")
    else:
        print(f"  [SKIP]  {SLURMDBD_CONF} already exists")


# ── Step 7 — MySQL setup ──────────────────────────────────────────

def configure_mysql():
    section("STEP 7: Configuring MySQL for Slurm accounting")

    # Check if DB already exists
    r = subprocess.run("mysql -u root -e 'SHOW DATABASES LIKE \"slurm_acct_db\";'",
                       shell=True, capture_output=True, text=True)
    if "slurm_acct_db" in r.stdout:
        print("  [SKIP]  slurm_acct_db already exists")
        return

    print("  [CREATE] MySQL database and user for Slurm")
    run("mysql -u root -e \"CREATE USER IF NOT EXISTS slurm@localhost\"")
    run("mysql -u root -e \"CREATE DATABASE IF NOT EXISTS slurm_acct_db\"")
    run("mysql -u root -e \"GRANT ALL PRIVILEGES ON slurm_acct_db.* TO slurm@localhost\"")
    run("mysql -u root -e \"FLUSH PRIVILEGES\"")
    run("systemctl restart mysql")
    print("  [OK] MySQL configured.")


# ── Step 8 — Permissions & directories ───────────────────────────

def setup_permissions():
    section("STEP 8: Setting up directories and permissions")

    dirs = [
        "/var/spool/slurmctld",
        "/var/spool/slurmd",
        "/var/log/slurm",
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        print(f"  [MKDIR]  {d}")

    run(f"chown slurm:slurm /var/spool/slurmctld /var/spool/slurmd")
    run(f"chown slurm:slurm {SLURM_CONF} {SLURMDBD_CONF} {CGROUP_CONF}")
    run(f"chmod 600 {SLURMDBD_CONF}")

    for log in ("/var/log/slurmctld.log", "/var/log/slurmdbd.log"):
        if not os.path.isfile(log):
            open(log, "w").close()
        run(f"chown slurm:slurm {log}")

    print("  [OK] Permissions set.")


# ── Step 9 — Systemd units ────────────────────────────────────────

def install_systemd_units():
    section("STEP 9: Installing systemd service units")

    slurm_src = os.path.join(DOWNLOAD_DIR, f"slurm-{SLURM_VERSION}")
    etc_src   = os.path.join(slurm_src, "etc")
    dest      = "/usr/local/lib/systemd/system"

    os.makedirs(dest, exist_ok=True)

    if os.path.isdir(etc_src):
        run(f"cp -v {etc_src}/*.service {dest}/ 2>/dev/null || true")
        run(f"cp -v {etc_src}/*.service.in {dest}/ 2>/dev/null || true")

    run("systemctl daemon-reload")
    print("  [OK] Systemd units installed.")


# ── Step 10 — Start services ──────────────────────────────────────

def start_services():
    section("STEP 10: Starting Slurm services")

    services = ["mysql", "munge", "slurmdbd", "slurmctld", "slurmd"]
    run(f"systemctl enable {' '.join(services)}")

    # Start in order with wait loops
    for svc in ("slurmdbd", "slurmctld", "slurmd"):
        print(f"  [START]  {svc}")
        run(f"systemctl start {svc}")
        for _ in range(15):
            if run_quiet(f"systemctl is-active --quiet {svc}") == 0:
                print(f"  [OK]     {svc} is active")
                break
            print(f"           waiting for {svc}...")
            time.sleep(2)
        else:
            print(f"  [ERROR]  {svc} did not start in time")
            run(f"journalctl -u {svc} -n 20 --no-pager")
            sys.exit(1)

    # Final sinfo
    print()
    run("sinfo")

    # Set node to idle
    hostname = platform.node()
    run(f"scontrol update node={hostname} state=idle")


# ── Main ──────────────────────────────────────────────────────────

def main():
    print("===== SLURM INSTALL MODULE (WSL Edition) =====\n")
    print(f"  Slurm version  : {SLURM_VERSION}")
    print(f"  Munge version  : {MUNGE_VERSION}")
    print(f"  hwloc version  : {HWLOC_VERSION}")
    print(f"  Download dir   : {DOWNLOAD_DIR}")
    print(f"  CPU cores      : {NPROC}\n")

    if os.geteuid() != 0:
        print("[ERROR] Run with sudo.")
        sys.exit(1)

    state = check_health()

    if state == HEALTHY:
        print("[OK] Slurm is already HEALTHY. Nothing to do.\n")
        subprocess.run("sinfo", shell=True)
        sys.exit(0)

    if state == BROKEN:
        print("[WARN] Slurm is BROKEN.")
        print("       Run:  sudo slurmfw repair slurm\n")
        sys.exit(1)

    # NOT_INSTALLED — full install
    install_system_packages()
    download_files()
    build_munge()
    build_hwloc()
    build_slurm()
    create_configs()
    configure_mysql()
    setup_permissions()
    install_systemd_units()
    start_services()

    print("\n[SUCCESS] Slurm installation complete ✔\n")


if __name__ == "__main__":
    main()
