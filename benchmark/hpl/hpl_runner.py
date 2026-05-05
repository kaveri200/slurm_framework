import os
import subprocess
import sys
import yaml
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HPL_DIR = os.path.join(BASE_DIR, "hpl-2.3")
ARCH = "Linux_PII_CBLAS"
BIN = os.path.join(HPL_DIR, "bin", ARCH, "xhpl")


# -------------------------------
# BUILD
# -------------------------------
def build():
    try:
        os.makedirs(os.path.join(BASE_DIR, "hpl_outputs"), exist_ok=True)

        tar_path = os.path.join(BASE_DIR, "hpl-2.3.tar.gz")
        hpl_src  = os.path.join(BASE_DIR, "hpl-2.3")

        subprocess.run(["rm", "-rf", hpl_src, tar_path], check=True)

        subprocess.run(
            ["wget", "-q", "https://www.netlib.org/benchmark/hpl/hpl-2.3.tar.gz",
             "-O", tar_path],
            cwd=BASE_DIR, check=True
        )

        subprocess.run(["tar", "-xzf", tar_path], cwd=BASE_DIR, check=True)

        make_file = os.path.join(hpl_src, "Make.Linux_PII_CBLAS")
        make_inc  = os.path.join(hpl_src, "Make.inc")

        subprocess.run(
            ["cp", os.path.join(hpl_src, "setup", "Make.Linux_PII_CBLAS"), make_file],
            check=True
        )

        ladir = "/usr/lib/x86_64-linux-gnu"

        patches = [
            f"s|^TOPdir *=.*|TOPdir = {hpl_src}|",
            f"s|^LAdir *=.*|LAdir = {ladir}|",
            r"s|^LAlib *=.*|LAlib = -L/usr/lib/x86_64-linux-gnu -lopenblas|",
            r"/mpich/d",
            r"s|^CC *=.*|CC = mpicc|",
            r"s|^LINKER *=.*|LINKER = mpicc|",
            r"s|^MPdir *=.*|MPdir = /usr/lib/x86_64-linux-gnu/openmpi|",
            r"s|^MPinc *=.*|MPinc = -I/usr/lib/x86_64-linux-gnu/openmpi/include|",
            r"s|^MPlib *=.*|MPlib = |",
        ]

        for patch in patches:
            subprocess.run(["sed", "-i", patch, make_file], check=True)

        if os.path.lexists(make_inc):
            os.remove(make_inc)
        os.symlink(make_file, make_inc)

        result = subprocess.run(
            ["make", f"arch={ARCH}"],
            cwd=hpl_src,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print("BUILD STATUS: 0")
            print(result.stderr[-2000:])
            sys.exit(1)

        if not os.path.exists(BIN):
            print("BUILD STATUS: 0")
            print(f"Binary not found at {BIN} even though make succeeded.")
            sys.exit(1)

        print("BUILD STATUS: 1")

    except Exception as e:
        print("BUILD STATUS: 0")
        print(e)
        sys.exit(1)


# -------------------------------
# WRITE HPL.DAT
# -------------------------------
def write_hpl_dat(path, N, NB, P, Q):
    content = (
        "HPLinpack benchmark input file\n"
        "Innovative Computing Laboratory, University of Tennessee\n"
        "HPL.out      output file name (if any)\n"
        "6            device out (6=stdout,7=stderr,file)\n"
        "1            # of problems sizes (N)\n"
        + str(N) + "          Ns\n"
        "1            # of NBs\n"
        + str(NB) + "         NBs\n"
        "0            PMAP process mapping (0=Row-,1=Column-major)\n"
        "1            # of process grids (P x Q)\n"
        + str(P) + "          Ps\n"
        + str(Q) + "          Qs\n"
        "16.0         threshold\n"
        "1            # of panel fact\n"
        "2            PFACTs (0=left, 1=Crout, 2=Right)\n"
        "1            # of recursive stopping criterium\n"
        "4            NBMINs (>= 1)\n"
        "1            # of panels in recursion\n"
        "2            NDIVs\n"
        "1            # of recursive panel fact.\n"
        "1            RFACTs (0=left, 1=Crout, 2=Right)\n"
        "1            # of broadcast\n"
        "1            BCASTs (0=1rg,1=1rM,2=2rg,3=2rM,4=Lng,5=LnM)\n"
        "1            # of lookahead depth\n"
        "1            DEPTHs (>=0)\n"
        "2            SWAP (0=bin-exch,1=long,2=mix)\n"
        "64           swapping threshold\n"
        "0            L1 in (0=transposed,1=no-transposed) form\n"
        "0            U  in (0=transposed,1=no-transposed) form\n"
        "1            Equilibration (0=no,1=yes)\n"
        "8            memory alignment in double (> 0)\n"
    )
    with open(path, "w") as f:
        f.write(content)


# -------------------------------
# PARSE OUTPUT
# -------------------------------
def parse_output(file):
    with open(file) as f:
        for line in f:
            if line.startswith("WR"):
                parts = line.split()
                if len(parts) >= 7:
                    return float(parts[5]), float(parts[6])
    return None, None


# -------------------------------
# PRINT TABLES
# -------------------------------
def print_iteration_table(results):
    print("+------+------------+------------+")
    print("| Iter |    Time(s) |     GFLOPS |")
    print("+------+------------+------------+")
    for i, (t, g) in enumerate(results, 1):
        print(f"|  {i:<3} | {t:>10.2f} | {g:>10.4f} |")
    print("+------+------------+------------+")


def print_summary(P, Q, iterations, avg, status):
    processes  = P * Q
    run_status = "COMPLETED" if status == 1 else "FAILED   "
    print("+-----+-----+-----------+------------+------------+-----------+")
    print("|  P  |  Q  | Processes | Iterations | Avg GFLOPS |    Status |")
    print("+-----+-----+-----------+------------+------------+-----------+")
    print(f"|  {P:<3} |  {Q:<3} | {processes:>9} | {iterations:>10} | {avg:>10.4f} | {run_status} |")
    print("+-----+-----+-----------+------------+------------+-----------+")


# -------------------------------
# RUN
# -------------------------------
def run():
    try:
        if not os.path.exists(BIN):
            raise Exception(f"Binary not found at {BIN}. Run build first.")

        with open(os.path.join(BASE_DIR, "run_recipe.yaml")) as f:
            config = yaml.safe_load(f)

        user = config["user_inputs"]

        N          = int(user["N"])
        NB         = int(user["NB"])
        P          = int(user["P"])
        Q          = int(user["Q"])
        iterations = int(user.get("iterations", 3))

        np = P * Q
        run_dir = os.path.join(HPL_DIR, "bin", ARCH)

        dat_path = os.path.join(run_dir, "HPL.dat")
        write_hpl_dat(dat_path, N, NB, P, Q)

        ldd_result = subprocess.run(["ldd", BIN], capture_output=True, text=True)
        missing = [l.strip() for l in ldd_result.stdout.splitlines() if "not found" in l]
        if missing:
            raise Exception("Missing shared libraries:\n" + "\n".join(missing))

        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = (
            "/usr/lib/x86_64-linux-gnu"
            ":/usr/lib/x86_64-linux-gnu/openmpi/lib"
            ":" + env.get("LD_LIBRARY_PATH", "")
        )
        env["OMPI_MCA_rmaps_base_oversubscribe"] = "1"

        results = []

        for i in range(iterations):
            out_file = os.path.join(run_dir, f"temp_{i}.out")

            with open(out_file, "w") as f_out:
                result = subprocess.run(
                    ["mpirun", "--oversubscribe", "-np", str(np), "--wdir", run_dir, BIN],
                    stdout=f_out,
                    stderr=f_out,
                    env=env
                )

            if result.returncode != 0:
                with open(out_file) as f_out:
                    print(f_out.read())
                raise Exception(f"mpirun failed on iteration {i+1} with exit code {result.returncode}")

            t, g = parse_output(out_file)
            if t is not None and g is not None:
                results.append((t, g))

            time.sleep(1)

        if not results:
            raise Exception("No valid results parsed from any iteration.")

        print("\nHPL BENCHMARK RESULTS")
        print_iteration_table(results)
        print()
        print_summary(P, Q, iterations, avg=sum(g for _, g in results) / len(results), status=1)

    except Exception as e:
        print(f"ERROR: {e}")
        print_summary(0, 0, 0, 0.0, 0)
        sys.exit(1)


# -------------------------------
# ENTRY
# -------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python hpl_runner.py [build|run]")
        sys.exit(1)

    if sys.argv[1] == "build":
        build()
    elif sys.argv[1] == "run":
        run()
    else:
        print("Invalid mode. Use 'build' or 'run'.")
        sys.exit(1)
