#!/usr/bin/env python3

import subprocess
import sys
import os
import re
import urllib.request

from module_utils import create_modulefile

# -------------------------------
# CONFIG
# -------------------------------
INSTALL_DIR = "/usr/local/openmpi"
OPENMPI_URL = "https://download.open-mpi.org/release/open-mpi"

DEPENDENCIES = [
    "build-essential",
    "wget",
    "libhwloc-dev",
    "libevent-dev"
]

# -------------------------------
# UTILS
# -------------------------------

def run(cmd):
    print(f"[RUN] {cmd}")
    subprocess.check_call(cmd, shell=True)


def is_package_installed(pkg):
    return subprocess.run(
        f"dpkg -s {pkg}",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    ).returncode == 0


def check_and_install_dependencies(packages):
    missing = [p for p in packages if not is_package_installed(p)]

    if not missing:
        print("[INFO] All dependencies already installed.")
        return

    print(f"[INFO] Installing missing dependencies: {' '.join(missing)}")
    run("apt update")
    run(f"apt install -y {' '.join(missing)}")


def get_installed_versions():
    if not os.path.exists(INSTALL_DIR):
        return []

    return [
        d for d in os.listdir(INSTALL_DIR)
        if re.match(r"\d+\.\d+\.\d+", d)
    ]


def get_major_dir(version):
    parts = version.split(".")
    return f"v{parts[0]}.{parts[1]}"


# -------------------------------
# ⚡ FAST VERSION CHECK (NO SCRAPING)
# -------------------------------

def version_exists(version):
    try:
        major = get_major_dir(version)
        url = f"{OPENMPI_URL}/{major}/openmpi-{version}.tar.gz"

        req = urllib.request.Request(url, method="HEAD")
        urllib.request.urlopen(req, timeout=3)   # fast check
        return True
    except:
        return False


def get_latest_version():
    return "5.0.9"   # update manually if needed


# -------------------------------
# INSTALL
# -------------------------------

def download_and_build(version):
    print(f"[INFO] Installing OpenMPI {version} from source...")

    major_dir = get_major_dir(version)
    tar = f"openmpi-{version}.tar.gz"
    url = f"{OPENMPI_URL}/{major_dir}/{tar}"

    run(f"wget {url}")
    run(f"tar -xzf {tar}")
    os.chdir(f"openmpi-{version}")

    prefix = os.path.join(INSTALL_DIR, version)

    run(f"./configure --prefix={prefix}")
    run("make -j$(nproc)")
    run("make install")

    print(f"[SUCCESS] OpenMPI {version} installed at {prefix}")

    create_modulefile("openmpi", version, prefix)


# -------------------------------
# MAIN
# -------------------------------

def main():

    version = sys.argv[1].strip() if len(sys.argv) > 1 else None
    print(f"[DEBUG] Requested version: {version}")

    os.makedirs(INSTALL_DIR, exist_ok=True)

    installed = get_installed_versions()

    # ---------------------------
    # VERSION HANDLING
    # ---------------------------

    if version is not None:
        print("[DEBUG] Entering specific version flow")

        if not version_exists(version):
            print(f"[ERROR] OpenMPI version {version} does not exist.")
            sys.exit(1)

        if version in installed:
            print(f"[INFO] OpenMPI {version} already installed.")
            return

    else:
        print("[DEBUG] Entering latest version flow")

        version = get_latest_version()
        print(f"[INFO] Latest OpenMPI version: {version}")

        if version in installed:
            print(f"[INFO] OpenMPI {version} already installed.")
            return

    # ---------------------------
    # DEPENDENCIES
    # ---------------------------
    check_and_install_dependencies(DEPENDENCIES)

    # ---------------------------
    # INSTALL
    # ---------------------------
    download_and_build(version)


if __name__ == "__main__":
    main()
