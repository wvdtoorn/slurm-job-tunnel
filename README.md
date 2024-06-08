# SLURM Job Tunnel

## Overview

`slurm-job-tunnel` is a utility to submit a SLURM job with specified resources and establish an SSH tunnel to the allocated compute node.

A tunnel sbatch script is run to find an available port on the compute node and start up an SSH server within a singularity image. The script writes the port and hostname of the SSH server to the SBATCH output file.

The port and hostname are retreived locally, and a corresponding host entry is created in your `~/.ssh/config`.
This entry is then used to connect to the SLURM job from your local machine over SSH.

When available, a VSCode instance is opened locally when the tunnel has been succesfully established.
You can now connect to the SLURM job from your local VSCode instance (CTRL+SHIFT+P, then `Remote-SSH`), and the tunnel will remain open until the time limit of the job runs out or you terminate the local process.

To stop the SLURM job and close the tunnel, terminate the local process (`CTRL+C`).

## Prerequisites

### Local machine

In `PATH` on the local machine:

- `python` (Python 3.6+)
- `singularity`
- `code` (VSCode)
- `ssh`

In addition, you're ssh config, located at `~/.ssh/config`, should contain a valid host for the login node of the HPC.
For example, if you named this host `hpc-login`, running `ssh hpc-login` should connect you to the login node.

### Remote machine

- `singularity` should be installed and in `$PATH` on the remote machine.

## Installation

Clone the repository and navigate to the project directory:

```sh
git clone https://github.com/wvdtoorn/slurm-job-tunnel.git
cd slurm-job-tunnel
pip install .
```

### Copy tunnel.sbatch to remote host

Copy `tunnel.sbatch` to the remote host, for example:

```sh
rsync -avz tunnel.sbatch <REMOTE_HOST>:<REMOTE_SBATCH_PATH>
```

- `<REMOTE_HOST>`: The hostname of the SLURM login node (for example: `hpc-login`)
- `<REMOTE_SBATCH_PATH>`: The path to the tunnel.sbatch script on the remote (for example: `tunnel.sbatch`)

The path used for `<REMOTE_SBATCH_PATH>` should be set once during `slurm-job-tunnel init` (see below).

### Build and copy singularity image

The singularity image to be executed on the remote host has to be build once.
This is best done locally, as it requires elevated permissions (`sudo`).
The image can then be transferred to the remote machine, for example using `rsync`.

For example, from within the repo root, run:

```sh
sudo singularity build openssh.sif openssh.def
rsync -avz openssh.sif <REMOTE_HOST>:~/<REMOTE_SIF_PATH>
```

- `<REMOTE_HOST>`: The hostname of the SLURM login node (for example, `hpc-login`)
- `<REMOTE_SIF_PATH>`: The path to the singularity image on the remote (for example, `singularity/openssh.sif`)

The path used for `<REMOTE_SIF_PATH>` should be set once during `slurm-job-tunnel init` (see below).

## Usage

```
usage: slurm-job-tunnel [-h] [--remote_host REMOTE_HOST] [--time TIME] [--cpus CPUS] [--mem MEM] [--qos QOS] [--partition PARTITION]
                        [--remote_sbatch_path REMOTE_SBATCH_PATH] [--remote_sif_path REMOTE_SIF_PATH] [--sif_bind_path SIF_BIND_PATH]
                        {init,run}

SLURM Job Tunnel: A utility to submit a SLURM job with specified resources and establish an SSH tunnel to the allocated compute node. It also integrates with
Visual Studio Code to provide a seamless development environment on the remote host.

positional arguments:
  {init,run}            The mode to run the SLURM job tunnel in. 'init' initializes the SLURM job tunnel by creating a default configuration file. 'run'
                        allocates the requested resources and establishes the SSH tunnel.

optional arguments:
  -h, --help            show this help message and exit
  --remote_host REMOTE_HOST
                        The remote host for the SLURM login node, as defined in ~/.ssh/config.
  --time TIME           Time limit for the SLURM job. Format is DD-HH:MM:SS, HH:MM:SS, or MM:SS.
  --cpus CPUS           The number of CPUs for the SLURM job.
  --mem MEM             The amount of memory for the SLURM job.
  --qos QOS             The QOS for the SLURM job
  --partition PARTITION
                        The partition for the SLURM job
  --remote_sbatch_path REMOTE_SBATCH_PATH
                        Path from the home directory of the remote user to where the sbatch script should be placed.
  --remote_sif_path REMOTE_SIF_PATH
                        Path from the home directory of the remote user to the remote singularity image to be executed.
  --sif_bind_path SIF_BIND_PATH
                        Path on the remote host to bind to the singularity image. Default is '/scratch/$USER'.
```

### Initialize

It's recommended to initialize the tunnel once, by running:

```sh
slurm-job-tunnel init [options]
```

This will create a config file located at `~/.slurm-job-tunnel/config.json` with the provided arguments, which henceforth will be used as defaults for the `run` command.

### Create a job tunnel

To create a job tunnel, run:

```sh
slurm-job-tunnel run [options]
```

## Future work

- [ ] Make sure only `USER` can access the tunnel

## License

This project is licensed under the MIT License.
