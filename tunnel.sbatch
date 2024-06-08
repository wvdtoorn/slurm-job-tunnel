#!/bin/bash

#SBATCH --job-name=tunnel
#SBATCH --nodes=1
#SBATCH --ntasks=1

# For example, run like:
# $ sbatch --time=120 --mem=8G --qos=hiprio --cpus-per-task=8 tunnel.sbatch
# where time is set in minutes!

echo "
###########################################
SLURM variables
###########################################

SLURM_JOB_START_TIME=${SLURM_JOB_START_TIME}
SLURM_JOB_END_TIME=${SLURM_JOB_END_TIME}

###########################################
"

echo "
SIF_BIND_PATH used for singularity bindings: ${SIF_BIND_PATH}
"

# Get tunneling information
XDG_RUNTIME_DIR=""
NODE=$(hostname -s)
PORT=$(python -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()') # random available port

# Tunneling instructions
echo "
Will open tunnel to:
NODE=${NODE}
PORT=${PORT}
"

# Calculate the time limit in minutes from SLURM_JOB_START_TIME and SLURM_JOB_END_TIME
TIME=$(date -u -d @$(( $SLURM_JOB_END_TIME - $SLURM_JOB_START_TIME )) +%H:%M:%S)


end_time_readable=$(date -d "@$SLURM_JOB_END_TIME" '+%Y-%m-%d %H:%M:%S')
echo "
The time limit for this job is: $TIME
This tunnel will close at: $end_time_readable
"

if [ -n "${SIF_BIND_PATH}" ]; then
    singularity exec -B ${SIF_BIND_PATH}:${SIF_BIND_PATH} ${SIF_IMAGE} /usr/sbin/sshd -p ${PORT} -D
else
    singularity exec ${SIF_IMAGE} /usr/sbin/sshd -p ${PORT} -D
fi
