import os
import subprocess
import sys
import yaml
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STREAM_DIR = os.path.join(BASE_DIR, "stream_src")
BUILD_DIR  = os.path.join(STREAM_DIR, "build")
BIN        = os.path.join(BUILD_DIR, "stream")


# -------------------------------
# BUILD
# -------------------------------
def build(array_size):

    # Skip build if binary already exists
    if os.path.exists(BIN):
        print("BUILD STATUS: SKIPPED (binary exists)")
        print(f"BINARY PATH: {BIN}")
        return

    try:
        os.makedirs(STREAM_DIR, exist_ok=True)
        os.makedirs(os.path.join(BASE_DIR, "stream_outputs"), exist_ok=True)

        src = os.path.join(STREAM_DIR, "stream.c")

        # Download stream.c
        print("Downloading stream.c...")

        subprocess.run(
            [
                "wget",
                "-q",
                "https://www.cs.virginia.edu/stream/FTP/Code/stream.c",
                "-O",
                src
            ],
            check=True
        )

        # Write CMakeLists.txt
        cmake_lists = os.path.join(
            STREAM_DIR,
            "CMakeLists.txt"
        )

        with open(cmake_lists, "w") as f:

            f.write(f"""cmake_minimum_required(VERSION 3.10)
project(stream C)

find_package(OpenMP REQUIRED)

add_executable(stream stream.c)

target_compile_options(stream PRIVATE
    -O3
    -DSTREAM_ARRAY_SIZE={array_size}
    -DNTIMES=10
)

target_link_libraries(stream PRIVATE OpenMP::OpenMP_C)
""")

        # -----------------------------------
        # CMAKE CONFIGURE
        # -----------------------------------

        print("Configuring with cmake...")

        os.makedirs(BUILD_DIR, exist_ok=True)

        result = subprocess.run(
            [
                "cmake",
                "-S",
                STREAM_DIR,
                "-B",
                BUILD_DIR,
                "-DCMAKE_BUILD_TYPE=Release"
            ],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:

            print("BUILD STATUS: 0")
            print(result.stdout)
            print(result.stderr)

            sys.exit(1)

        # -----------------------------------
        # CMAKE BUILD
        # -----------------------------------

        print("Building with cmake...")

        result = subprocess.run(
            [
                "cmake",
                "--build",
                BUILD_DIR,
                "--config",
                "Release"
            ],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:

            print("BUILD STATUS: 0")
            print(result.stdout)
            print(result.stderr)

            sys.exit(1)

        if not os.path.exists(BIN):

            print("BUILD STATUS: 0")
            print(f"Binary not found at {BIN} after build.")

            sys.exit(1)

        print("BUILD STATUS: 1")
        print(f"BINARY PATH: {BIN}")

    except Exception as e:

        print("BUILD STATUS: 0")
        print(e)

        sys.exit(1)


# -------------------------------
# PARSE OUTPUT
# -------------------------------
def parse_output(output):

    results = {}

    for line in output.splitlines():

        for kernel in ["Copy", "Scale", "Add", "Triad"]:

            if line.startswith(kernel + ":"):

                parts = line.split()

                if len(parts) >= 2:
                    results[kernel] = float(parts[1])

    return results


# -------------------------------
# PRINT TABLES
# -------------------------------
def print_iteration_table(all_results):

    print("+------+------------+------------+------------+------------+")
    print("| Iter |    Copy    |   Scale    |    Add     |   Triad    |")
    print("|      |   (MB/s)   |   (MB/s)   |   (MB/s)   |   (MB/s)   |")
    print("+------+------------+------------+------------+------------+")

    for i, res in enumerate(all_results, 1):

        copy  = res.get("Copy",  0.0)
        scale = res.get("Scale", 0.0)
        add   = res.get("Add",   0.0)
        triad = res.get("Triad", 0.0)

        print(
            f"|  {i:<3} | "
            f"{copy:>10.2f} | "
            f"{scale:>10.2f} | "
            f"{add:>10.2f} | "
            f"{triad:>10.2f} |"
        )

    print("+------+------------+------------+------------+------------+")


def print_summary(threads, iterations, avg, status):

    run_status = "COMPLETED" if status == 1 else "FAILED   "

    print("+---------+------------+------------+-----------+")
    print("| Threads | Iterations | Avg Triad  |    Status |")
    print("|         |            |   (MB/s)   |           |")
    print("+---------+------------+------------+-----------+")

    print(
        f"| {threads:>7} | "
        f"{iterations:>10} | "
        f"{avg:>10.2f} | "
        f"{run_status} |"
    )

    print("+---------+------------+------------+-----------+")


# -------------------------------
# RUN
# -------------------------------
def run():

    try:

        if not os.path.exists(BIN):
            raise Exception(
                f"Binary not found at {BIN}. Run build first."
            )

        with open(
            os.path.join(BASE_DIR, "run_recipe.yaml")
        ) as f:

            config = yaml.safe_load(f)

        user = config["user_inputs"]

        threads = int(user.get("threads", 1))
        iterations = int(user.get("iterations", 3))

        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = str(threads)

        output_dir = os.environ.get(
            "OUTPUT_DIR",
            BASE_DIR
        )

        all_results = []

        for i in range(iterations):

            out_file = os.path.join(
                output_dir,
                f"iteration_{i+1}.out"
            )

            result = subprocess.run(
                [BIN],
                capture_output=True,
                text=True,
                env=env
            )

            with open(out_file, "w") as f:

                f.write(
                    f"THREADS: {threads}\n\n"
                )

                f.write(result.stdout)

                if result.stderr:
                    f.write("\nERRORS:\n")
                    f.write(result.stderr)

            if result.returncode != 0:

                print(result.stderr)

                raise Exception(
                    f"stream failed on iteration {i+1}"
                )

            parsed = parse_output(result.stdout)

            if parsed:
                all_results.append(parsed)

            time.sleep(1)

        if not all_results:
            raise Exception(
                "No valid results parsed from any iteration."
            )

        print("\nSTREAM BENCHMARK RESULTS")

        print_iteration_table(all_results)

        print()

        avg_triad = (
            sum(
                r.get("Triad", 0.0)
                for r in all_results
            ) / len(all_results)
        )

        print_summary(
            threads,
            iterations,
            avg_triad,
            1
        )

    except Exception as e:

        print(f"ERROR: {e}")

        print_summary(0, 0, 0.0, 0)

        sys.exit(1)


# -------------------------------
# ENTRY
# -------------------------------
if __name__ == "__main__":

    if len(sys.argv) < 2:

        print(
            "Usage: python stream_runner.py [build|run]"
        )

        sys.exit(1)

    if sys.argv[1] == "build":

        with open(
            os.path.join(BASE_DIR, "run_recipe.yaml")
        ) as f:

            config = yaml.safe_load(f)

        user = config["user_inputs"]

        build(
            array_size=int(
                user.get(
                    "array_size",
                    10000000
                )
            )
        )

    elif sys.argv[1] == "run":

        run()

    else:

        print(
            "Invalid mode. Use 'build' or 'run'."
        )

        sys.exit(1)
