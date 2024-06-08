#!/bin/bash

#SBATCH --job-name=tunnel
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=CPUS_PER_TASK
#SBATCH --mem=MEM
#SBATCH --qos=hiprio

# Run like:
# $ sbatch --time=120 tunnel.sbatch
# where time is set in minutes!

# handle time limit (dd-hh:mm:ss, hh:mm:ss, mm:ss, ss)
TIME=$(squeue -j $SLURM_JOB_ID -h --Format TimeLimit | awk -F '[:-]' '{
    if (NF==2) { print $1 }
    else if (NF==3) { print ($1 * 60) + $2 }
    else if (NF==4) { print ($1 * 24 * 60) + ($2 * 60) + $3 }
}')
echo "The time limit for this job is: $TIME minutes"
echo "This tunnel will close at $(date -d "+ $TIME minutes")".


# Get tunneling information
XDG_RUNTIME_DIR=""
node=$(hostname -s)
port=$(python -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()') # random available port

# Tunneling instructions
echo -e "
PORT=${port}
NODE=${node}
"

singularity exec REMOTE_SIF_PATH /usr/sbin/sshd -p ${port} -D
