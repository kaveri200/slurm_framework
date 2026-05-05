#!/bin/bash
#SBATCH --job-name=stream_test
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:10:00
#SBATCH --output=/home/kaveri/slurmfw/benchmark/stream/stream_outputs/stream_%j.out
#SBATCH --error=/home/kaveri/slurmfw/benchmark/stream/stream_outputs/stream_%j.err

source /etc/profile.d/modules.sh
module purge

module load openmpi/5.0.9

export OMPI_MCA_rmaps_base_oversubscribe=1

cd /home/kaveri/slurmfw/benchmark/stream

python3 /home/kaveri/slurmfw/benchmark/stream/stream_runner.py build
