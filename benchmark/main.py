import yaml
import os
import subprocess
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def generate_sbatch(job, modules, envs, runner, mode, output_dir, name_prefix):

    module_lines = "\n".join(
        [f"module load {m}" for m in modules]
    )

    env_lines = "\n".join(
        [f"export {k}={v}" for k, v in envs.items()]
    )

    return f"""#!/bin/bash
#SBATCH --job-name={job['name']}
#SBATCH --nodes={job['nodes']}
#SBATCH --ntasks={job['ntasks']}
#SBATCH --cpus-per-task={job['cpus_per_task']}
#SBATCH --time={job['time']}
#SBATCH --output={output_dir}/{name_prefix}.out
#SBATCH --error={output_dir}/{name_prefix}.err

source /etc/profile.d/modules.sh
module purge

{module_lines}

{env_lines}

cd {os.path.dirname(runner)}

python3 {runner} {mode}
"""


def save_sbatch(script, name_prefix, tag):

    temp_file = f"/tmp/{name_prefix}_{tag}.sh"

    with open(temp_file, "w") as f:
        f.write(script)

    return temp_file


def submit_job(script_file, dependency=None):

    cmd = ["sbatch"]

    if dependency:
        cmd.append(f"--dependency=afterok:{dependency}")

    cmd.append(script_file)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"SBATCH ERROR: {result.stderr}")
        sys.exit(1)

    return result.stdout.strip().split()[-1]


def get_binary_path(benchmark):

    paths = {
        "hpl": os.path.join(
            BASE_DIR,
            "hpl",
            "hpl-2.3",
            "bin",
            "Linux_PII_CBLAS",
            "xhpl"
        ),

        "stream": os.path.join(
            BASE_DIR,
            "stream",
            "stream_src",
            "stream"
        ),
    }

    return paths.get(benchmark, "")


def binary_exists(benchmark):

    return os.path.exists(
        get_binary_path(benchmark)
    )


def run(benchmark):

    run_yaml = os.path.join(
        BASE_DIR,
        benchmark,
        "run_recipe.yaml"
    )

    build_yaml = os.path.join(
        BASE_DIR,
        "build_recipe.yaml"
    )

    run_config = load_yaml(run_yaml)
    build_config = load_yaml(build_yaml)

    job = run_config["job"]

    modules = build_config.get("modules", [])
    envs = build_config.get("env", {})

    runner = os.path.join(
        BASE_DIR,
        benchmark,
        f"{benchmark}_runner.py"
    )

    # ==========================================
    # STRUCTURED OUTPUT DIRECTORIES
    # ==========================================

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    base_output_dir = os.path.join(
        BASE_DIR,
        benchmark,
        f"{benchmark}_outputs"
    )

    build_output_dir = os.path.join(
        base_output_dir,
        f"case_{timestamp}_build"
    )

    run_output_dir = os.path.join(
        base_output_dir,
        f"case_{timestamp}_run"
    )

    os.makedirs(build_output_dir, exist_ok=True)
    os.makedirs(run_output_dir, exist_ok=True)

    binary_path = get_binary_path(benchmark)

    skip_build = binary_exists(benchmark)

    # ==========================================
    # BUILD SKIPPED
    # ==========================================

    if skip_build:

        # --------------------------------------
        # BUILD SBATCH
        # --------------------------------------

        envs["OUTPUT_DIR"] = build_output_dir

        build_script = generate_sbatch(
            job,
            modules,
            envs,
            runner,
            "build",
            build_output_dir,
            "build"
        )

        with open(
            os.path.join(build_output_dir, "build.sbatch"),
            "w"
        ) as f:
            f.write(build_script)

        # --------------------------------------
        # BUILD OUT
        # --------------------------------------

        with open(
            os.path.join(build_output_dir, "build.out"),
            "w"
        ) as f:

            f.write(
                "BUILD STATUS : SKIPPED\n"
                f"BINARY EXISTS : {binary_path}\n"
            )

        # --------------------------------------
        # BUILD ERR
        # --------------------------------------

        with open(
            os.path.join(build_output_dir, "build.err"),
            "w"
        ) as f:
            f.write("")

        # --------------------------------------
        # RUN JOB
        # --------------------------------------

        envs["OUTPUT_DIR"] = run_output_dir

        run_script = generate_sbatch(
            job,
            modules,
            envs,
            runner,
            "run",
            run_output_dir,
            "run"
        )

        run_file = save_sbatch(
            run_script,
            benchmark,
            "run"
        )

        run_job_id = submit_job(run_file)

        with open(
            os.path.join(run_output_dir, "run.sbatch"),
            "w"
        ) as f:
            f.write(run_script)

        print(f"\n▶ Benchmark : {benchmark}")
        print(f"   Build job : SKIPPED")
        print(f"   Binary    : {binary_path}")
        print(f"   Run job   : {run_job_id}")
        print(f"   Build out : {build_output_dir}")
        print(f"   Run out   : {run_output_dir}")

    # ==========================================
    # BUILD + RUN
    # ==========================================

    else:

        # --------------------------------------
        # BUILD JOB
        # --------------------------------------

        envs["OUTPUT_DIR"] = build_output_dir

        build_script = generate_sbatch(
            job,
            modules,
            envs,
            runner,
            "build",
            build_output_dir,
            "build"
        )

        build_file = save_sbatch(
            build_script,
            benchmark,
            "build"
        )

        build_job_id = submit_job(build_file)

        with open(
            os.path.join(build_output_dir, "build.sbatch"),
            "w"
        ) as f:
            f.write(build_script)

        with open(
            os.path.join(build_output_dir, "build.out"),
            "w"
        ) as f:

            f.write(
                "BUILD STATUS : SUBMITTED\n"
                f"BINARY PATH  : {binary_path}\n"
            )

        with open(
            os.path.join(build_output_dir, "build.err"),
            "w"
        ) as f:
            f.write("")

        # --------------------------------------
        # RUN JOB
        # --------------------------------------

        envs["OUTPUT_DIR"] = run_output_dir

        run_script = generate_sbatch(
            job,
            modules,
            envs,
            runner,
            "run",
            run_output_dir,
            "run"
        )

        run_file = save_sbatch(
            run_script,
            benchmark,
            "run"
        )

        run_job_id = submit_job(
            run_file,
            dependency=build_job_id
        )

        with open(
            os.path.join(run_output_dir, "run.sbatch"),
            "w"
        ) as f:
            f.write(run_script)

        print(f"\n▶ Benchmark : {benchmark}")
        print(f"   Build job : {build_job_id}")
        print(f"   Run job   : {run_job_id}")
        print(f"   Build out : {build_output_dir}")
        print(f"   Run out   : {run_output_dir}")


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage: python main.py <hpl|stream>")
        sys.exit(1)

    run(sys.argv[1])
