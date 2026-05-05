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
INSTALL_DIR = "/usr/local/python"
PYTHON_URL = "https://www.python.org/ftp/python"

DEPENDENCIES = [
    "build-essential",
    "wget",
    "libssl-dev",
    "zlib1g-dev",
    "libncurses-dev",
    "libreadline-dev",
    "libsqlite3-dev",
    "libgdbm-dev",
    "libbz2-dev",
    "libexpat1-dev",
    "liblzma-dev",
    "tk-dev"
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


def get_latest_installed(installed):
    return sorted(installed, key=lambda x: list(map(int, x.split("."))))[-1]


def url_exists(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        urllib.request.urlopen(req)
        return True
    except:
        return False


# -------------------------------
# VERSION HANDLING
# -------------------------------

def version_exists(version):
    url = f"{PYTHON_URL}/{version}/Python-{version}.tgz"
    return url_exists(url)


def get_latest_version():
    # Safe fallback (update when needed)
    return "3.14.4"


# -------------------------------
# INSTALL
# -------------------------------

def download_and_build(version):
    print(f"[INFO] Installing Python {version} from source...")

    tar = f"Python-{version}.tgz"
    url = f"{PYTHON_URL}/{version}/{tar}"

    run(f"wget {url}")
    run(f"tar -xzf {tar}")
    os.chdir(f"Python-{version}")

    prefix = os.path.join(INSTALL_DIR, version)

    run(f"./configure --enable-optimizations --prefix={prefix}")
    run("make -j$(nproc)")
    run("make install")

    print(f"[SUCCESS] Python {version} installed at {prefix}")

    # Create modulefile
    create_modulefile("python", version, prefix)


# -------------------------------
# MAIN
# -------------------------------

def main():

    version = sys.argv[1].strip() if len(sys.argv) > 1 else None
    print(f"[DEBUG] Requested version: {version}")

    os.makedirs(INSTALL_DIR, exist_ok=True)

    installed = get_installed_versions()

    # ---------------------------
    # CHECK INSTALLED FIRST
    # ---------------------------
    if version is None and installed:
        latest_installed = get_latest_installed(installed)
        print(f"[INFO] Latest installed Python: {latest_installed}")
        print(f"[INFO] Python {latest_installed} already installed.")
        return

    # ---------------------------
    # VERSION HANDLING
    # ---------------------------
    if version is not None:
        print("[DEBUG] Entering specific version flow")

        if not version_exists(version):
            print(f"[ERROR] Python version {version} does not exist.")
            sys.exit(1)

        if version in installed:
            print(f"[INFO] Python {version} already installed.")
            return

    else:
        print("[DEBUG] Entering latest version flow")

        version = get_latest_version()
        print(f"[INFO] Latest Python version: {version}")

        if version in installed:
            print(f"[INFO] Python {version} already installed.")
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
