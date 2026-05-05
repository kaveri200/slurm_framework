#!/usr/bin/env python3

import os
import sys
import shutil

INSTALL_DIR = "/usr/local/openmpi"
MODULE_BASE = os.path.expanduser("~/modules")
MODULE_DIR = os.path.join(MODULE_BASE, "openmpi")


# -------------------------------
# DETECT INSTALLED VERSIONS
# -------------------------------
def get_installed_versions():
    versions = []

    # Case 1: versioned installs
    if os.path.exists(INSTALL_DIR):
        for d in os.listdir(INSTALL_DIR):
            if os.path.isdir(os.path.join(INSTALL_DIR, d)):
                versions.append(d)

    # Case 2: single install (no version folder)
    if os.path.exists(os.path.join(INSTALL_DIR, "bin")):
        versions.append("system")

    return list(set(versions))


# -------------------------------
# REMOVE MODULEFILE
# -------------------------------
def remove_modulefile(version):
    module_path = os.path.join(MODULE_DIR, version)

    if os.path.exists(module_path):
        os.remove(module_path)
        print(f"[OK] Removed modulefile: {module_path}")

    # Optional: remove empty module directory
    if os.path.exists(MODULE_DIR) and not os.listdir(MODULE_DIR):
        os.rmdir(MODULE_DIR)
        print(f"[INFO] Removed empty module dir: {MODULE_DIR}")


# -------------------------------
# DELETE INSTALL
# -------------------------------
def delete_version(version):
    print(f"[INFO] Removing OpenMPI {version}...")

    # Case 1: versioned install
    version_path = os.path.join(INSTALL_DIR, version)

    if os.path.exists(version_path):
        shutil.rmtree(version_path)
        print(f"[OK] Removed: {version_path}")

    # Case 2: single install
    elif version == "system" and os.path.exists(INSTALL_DIR):
        shutil.rmtree(INSTALL_DIR)
        print(f"[OK] Removed: {INSTALL_DIR}")

    else:
        print(f"[ERROR] Version {version} not found.")
        sys.exit(1)

    # Remove modulefile
    remove_modulefile(version)

    print(f"[SUCCESS] OpenMPI {version} removed.")


# -------------------------------
# MAIN
# -------------------------------
def main():
    version = sys.argv[1] if len(sys.argv) > 1 else None

    installed = get_installed_versions()

    if not installed:
        print("[INFO] No OpenMPI versions installed.")
        return

    print("Installed OpenMPI versions:")
    for v in installed:
        print(f"  - {v}")

    if not version:
        version = input("Enter version to remove: ").strip()

    if version not in installed:
        print(f"[ERROR] OpenMPI version {version} is not installed.")
        sys.exit(1)

    delete_version(version)


if __name__ == "__main__":
    main()
