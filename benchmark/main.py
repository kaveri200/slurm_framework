import yaml
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def generate_sbatch(job, modules, envs, runner, mode, output_dir, name_prefix):
    module_lines = "\n".join([f"module load {m}" for m in modules])
    env_lines = "\n".join([f"export {k}={v}" for k, v in envs.items()])

    return f"""#!/bin/bash
#SBATCH --job-name={job['name']}
#SBATCH --nodes={job['nodes']}
#SBATCH --ntasks={job['ntasks']}
#SBATCH --cpus-per-task={job['cpus_per_task']}
#SBATCH --time={job['time']}
#SBATCH --output={output_dir}/{name_prefix}_%j.out
#SBATCH --error={output_dir}/{name_prefix}_%j.err

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

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"SBATCH ERROR: {result.stderr}")
        sys.exit(1)

    job_id = result.stdout.strip().split()[-1]
    return job_id


def binary_exists(benchmark):
    """Check if the benchmark binary already exists — skip build if so."""
    paths = {
        "hpl":    os.path.join(BASE_DIR, "hpl",    "hpl-2.3", "bin", "Linux_PII_CBLAS", "xhpl"),
        "stream": os.path.join(BASE_DIR, "stream",  "stream_src", "stream"),
    }
    return os.path.exists(paths.get(benchmark, ""))


def run(benchmark):
    run_yaml   = os.path.join(BASE_DIR, benchmark, "run_recipe.yaml")
    build_yaml = os.path.join(BASE_DIR, "build_recipe.yaml")

    run_config   = load_yaml(run_yaml)
    build_config = load_yaml(build_yaml)

    job     = run_config["job"]
    envs    = build_config.get("env", {})
    modules = build_config.get("modules", [])

    runner     = os.path.join(BASE_DIR, benchmark, f"{benchmark}_runner.py")
    output_dir = os.path.join(BASE_DIR, benchmark, f"{benchmark}_outputs")
    os.makedirs(output_dir, exist_ok=True)

    skip_build = binary_exists(benchmark)

    if skip_build:
        # Submit run job directly — no build dependency
        run_script = generate_sbatch(job, modules, envs, runner, "run", output_dir, benchmark)
        run_file   = save_sbatch(run_script, benchmark, "run")
        run_job_id = submit_job(run_file)

        with open(os.path.join(output_dir, f"{benchmark}_{run_job_id}.sbatch"), "w") as f:
            f.write(run_script)

        print(f"\n▶  Benchmark : {benchmark}")
        print(f"   Build job : SKIPPED (binary exists)")
        print(f"   Run job   : {run_job_id}")
        print(f"   Output    : {output_dir}/{benchmark}_{run_job_id}.out")

    else:
        # Submit build then run with dependency
        build_script = generate_sbatch(job, modules, envs, runner, "build", output_dir, benchmark)
        build_file   = save_sbatch(build_script, benchmark, "build")
        build_job_id = submit_job(build_file)

        with open(os.path.join(output_dir, f"{benchmark}_{build_job_id}.sbatch"), "w") as f:
            f.write(build_script)

        run_script = generate_sbatch(job, modules, envs, runner, "run", output_dir, benchmark)
        run_file   = save_sbatch(run_script, benchmark, "run")
        run_job_id = submit_job(run_file, dependency=build_job_id)

        with open(os.path.join(output_dir, f"{benchmark}_{run_job_id}.sbatch"), "w") as f:
            f.write(run_script)

        print(f"\n▶  Benchmark : {benchmark}")
        print(f"   Build job : {build_job_id}")
        print(f"   Run job   : {run_job_id}")
        print(f"   Output    : {output_dir}/{benchmark}_{run_job_id}.out")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <hpl|stream>")
        sys.exit(1)

    run(sys.argv[1])
