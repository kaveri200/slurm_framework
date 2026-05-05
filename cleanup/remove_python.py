#!/usr/bin/env python3

import os
import sys
import shutil

INSTALL_DIR = "/usr/local/python"
MODULE_DIR = os.path.expanduser("~/.modules/python") if False else os.path.expanduser("~/modules/python")


def get_installed_versions():
    if not os.path.exists(INSTALL_DIR):
        return []
    return [d for d in os.listdir(INSTALL_DIR)]


def delete_version(version):
    install_path = os.path.join(INSTALL_DIR, version)
    module_path = os.path.join(MODULE_DIR, version)

    print(f"[INFO] Removing Python {version}...")

    if os.path.exists(install_path):
        shutil.rmtree(install_path)
        print(f"[OK] Removed: {install_path}")

    if os.path.exists(module_path):
        os.remove(module_path)
        print(f"[OK] Removed modulefile: {module_path}")

    print(f"[SUCCESS] Python {version} removed completely.")


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else None

    installed = get_installed_versions()

    if not installed:
        print("[INFO] No Python versions installed.")
        return

    print("Installed Python versions:")
    for v in installed:
        print(f"  - {v}")

    if not version:
        version = input("Enter version to remove: ").strip()

    if version not in installed:
        print(f"[ERROR] Python version {version} is not installed.")
        sys.exit(1)

    delete_version(version)


if __name__ == "__main__":
    main()
