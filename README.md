# slurm-job-tunnel

## Overview

`slurm-job-tunnel` is tool to setup an SSH tunnel to connect VSCode to a SLURM job running on a HPC.
The tunnel is created by submitting a SLURM job to the HPC. The job runs an SSHD server in a singularity image on an available port.
The tool then retrieves the port number of the SSHD server and the hostname of the compute node it is running on, and creates a corresponding host entry in your `~/.ssh/config`.
This entry is then used to connect to the SLURM job from your local machine using VSCode.
To stop the SLURM job and close the tunnel, you can simply terminate the local process.

## Prerequisites

### Local machine

In `PATH` on the local machine:

- `python` (Python 3.x)
- `singularity`
- `code` (VSCode)
- `ssh`
- `rsync`

In addition, you're ssh config, located at `~/.ssh/config`, should contain a valid host for the login node of the HPC.
For example, if you named this host `hpc-login`, running `ssh hpc-login` should connect you to the login node.

### Remote machine

- `singularity` should be installed and in `$PATH` on the remote machine.

## Installation

Clone the repository and navigate to the project directory:

```sh
git clone https://github.com/wvdtoorn/slurm-job-tunnel.git
cd slurm-job-tunnel
```

### Singularity image

The singularity image to be executed on the remote host has to be build once.
This is best done locally, as it requires elevated permissions (`sudo`).
The image can then be transferred to the remote machine, for example using `rsync`.

For example, from within the repo root, run:

```sh
sudo singularity build openssh.sif openssh.def
rsync -avz openssh.sif [REMOTE_HOST]:[REMOTE_PATH]
```

Where `[REMOTE_HOST]` is your HPC host (for example, `hpc-login`), and `[REMOTE_PATH]` is the path where the image should be placed (for example, `~/singularity/openssh.sif`).

## Usage

To create a job tunnel, run:

```sh
python job_tunnel.py --time <minutes> --remote_host <host> [options]
```

- `<minutes>`: Time limit in minutes for the SLURM job / tunnel (required)
- `<host>`: The remote host for the SLURM login node (required)

## Options

- `--cpus`: The number of CPUs for the SLURM job (default: 8)
- `--mem`: The amount of memory for the SLURM job (default: 16G)
- `--remote_script_path`: Path from the home directory of the remote user to the remote script to be executed (default: tunnel.sbatch)
- `--remote_sif_path`: Path from the home directory of the remote user to the remote singularity image to be executed (default: singularity/openssh.sif)

## Future work

- [ ] Make sure only `USER` can access the tunnel

## License

This project is licensed under the MIT License.
