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
INSTALL_DIR = "/usr/local/gcc"
GCC_URL = "https://ftp.gnu.org/gnu/gcc"

DEPENDENCIES = [
    "build-essential",
    "wget",
    "libgmp-dev",
    "libmpfr-dev",
    "libmpc-dev",
    "flex",
    "bison"
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


def url_exists(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        urllib.request.urlopen(req)
        return True
    except:
        return False


def get_available_versions():
    print("[INFO] Fetching GCC versions...")
    data = urllib.request.urlopen(GCC_URL).read().decode()

    versions = re.findall(r"gcc-(\d+\.\d+\.\d+)/", data)

    valid = []
    for v in versions:
        tar_url = f"{GCC_URL}/gcc-{v}/gcc-{v}.tar.gz"
        if url_exists(tar_url):
            valid.append(v)

    return valid


def get_latest_version(versions):
    return sorted(
        versions,
        key=lambda x: list(map(int, x.split(".")))
    )[-1]


def download_and_build(version):
    print(f"[INFO] Installing GCC {version} from source...")

    tar = f"gcc-{version}.tar.gz"
    url = f"{GCC_URL}/gcc-{version}/{tar}"

    if not url_exists(url):
        print(f"[ERROR] Source not found for GCC {version}")
        sys.exit(1)

    run(f"wget {url}")
    run(f"tar -xzf {tar}")
    os.chdir(f"gcc-{version}")

    # GCC requires downloading prerequisites
    run("./contrib/download_prerequisites")

    build_dir = "build"
    os.makedirs(build_dir, exist_ok=True)
    os.chdir(build_dir)

    prefix = os.path.join(INSTALL_DIR, version)

    run(f"../configure --disable-multilib --enable-languages=c,c++ --prefix={prefix}")
    run("make -j$(nproc)")
    run("make install")

    print(f"[SUCCESS] GCC {version} installed at {prefix}")
    create_modulefile("gcc", version, prefix)

# -------------------------------
# MAIN
# -------------------------------

def main():

    version = sys.argv[1].strip() if len(sys.argv) > 1 else None
    print(f"[DEBUG] Requested version: {version}")

    os.makedirs(INSTALL_DIR, exist_ok=True)

    installed = get_installed_versions()
    available = get_available_versions()

    if version is not None:
        print("[DEBUG] Entering specific version flow")

        if version not in available:
            print(f"[ERROR] GCC version {version} does not exist.")
            sys.exit(1)

        if version in installed:
            print(f"[INFO] GCC {version} already installed.")
            return

    else:
        print("[DEBUG] Entering latest version flow")

        version = get_latest_version(available)
        print(f"[INFO] Latest GCC version: {version}")

        if version in installed:
            print(f"[INFO] GCC {version} already installed.")
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
