import os

def create_modulefile(name, version, install_path):
    """
    Generic modulefile creator
    name: python / gcc / openmpi
    version: 3.14.4 / 13.2.0
    install_path: /usr/local/python/3.14.4
    """

    user_home = os.environ.get("SUDO_USER")

    if user_home:
        base_home = f"/home/{user_home}"
    else:
        base_home = os.path.expanduser("~")

    module_dir = os.path.join(base_home, "modules", name)
    os.makedirs(module_dir, exist_ok=True)

    modulefile_path = os.path.join(module_dir, version)

    content = f"""#%Module1.0#####################################################################

proc ModulesHelp {{ }} {{
    puts stderr "{name} {version}"
}}

module-whatis "{name} {version}"

set root {install_path}

prepend-path PATH $root/bin
prepend-path LD_LIBRARY_PATH $root/lib
prepend-path MANPATH $root/share/man
"""

    with open(modulefile_path, "w") as f:
        f.write(content)

    print(f"[INFO] Modulefile created: {modulefile_path}")
