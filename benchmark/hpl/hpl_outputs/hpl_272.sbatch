#!/bin/bash
#SBATCH --job-name=hpl_test
#SBATCH --nodes=1
#SBATCH --ntasks=3
#SBATCH --cpus-per-task=1
#SBATCH --time=00:10:00
#SBATCH --output=/home/kaveri/slurmfw/benchmark/hpl/hpl_outputs/hpl_%j.out
#SBATCH --error=/home/kaveri/slurmfw/benchmark/hpl/hpl_outputs/hpl_%j.err

source /etc/profile.d/modules.sh
module purge

module load openmpi/5.0.9

export OMPI_MCA_rmaps_base_oversubscribe=1

cd /home/kaveri/slurmfw/benchmark/hpl

python3 /home/kaveri/slurmfw/benchmark/hpl/hpl_runner.py run
