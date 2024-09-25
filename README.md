# SLURM Job Tunnel

## Overview

`slurm-job-tunnel` is a utility to submit a SLURM job with specified resources and establish an SSH tunnel to the allocated compute node.

A tunnel sbatch script is run to find an available port on the compute node and start up an SSH server within a `singularity` image.
The script writes the port and hostname of the SSH server to the SBATCH output file.

The port and hostname are retreived locally, and a corresponding host entry is created in your `~/.ssh/config`.
This entry can be used to connect to the SLURM job from your local machine over SSH.

In addition, a separate ssh process is started on your local machine to forward a local port to the port of the job tunnel on the remote. You can use this an an alternative way to connect to the SLURM job for use cases that have trouble with the standard tunnel, using `ssh <remote_user>@localhost:<local_port>`.

The tunnel and port forwarding will remain open until the time limit of the job runs out or you terminate the local process, whatever comes first.

To stop the SLURM job and close the tunnel, terminate the local process (`CTRL+C`).

## Prerequisites

### Local machine

In `PATH` on the local machine:

- `python>=3.12`
- `rsync`
- `singularity`
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

This will install the `slurm-job-tunnel` package along with its dependencies: the [`slurm-job-util`](https://github.com/wvdtoorn/slurm-job-util) package, `pexpect`.
After installation, the commands `slurm-job-tunnel` and `sjt` (for short) are available.

### Copy tunnel.sbatch to remote host

Copy `tunnel.sbatch` to the remote host, for example:

```sh
rsync -avz tunnel.sbatch <REMOTE_HOST>:~/<REMOTE_SBATCH_PATH>
```

- `<REMOTE_HOST>`: The hostname of the SLURM login node (for example: `hpc-login`)
- `<REMOTE_SBATCH_PATH>`: The path to the tunnel.sbatch script on the remote, from the home directory of the remote user (for example: `tunnel.sbatch`)

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
- `<REMOTE_SIF_PATH>`: The path to the singularity image on the remote, from the home directory of the remote user (for example, `singularity/openssh.sif`)

The path used for `<REMOTE_SIF_PATH>` should be set once during `slurm-job-tunnel init` (see below).

## Usage

```
usage: slurm-job-tunnel [-h] {init,run,reset} ...

positional arguments:
  {init,run,reset}
    init            Initialize the SLURM job tunnel by creating a configuration file.
    run             Allocate the requested resources and establish the SSH tunnel.
    reset           Reset the tool configuration to default values.
    show            Show the configuration.
```

### Options for `init` and `run`

```
usage: slurm-job-tunnel {init,run} [-h]
                             [--remote_host REMOTE_HOST]
                             [--time TIME]
                             [--cpus CPUS]
                             [--mem MEM]
                             [--qos QOS]
                             [--partition PARTITION]
                             [--remote_sbatch_path REMOTE_SBATCH_PATH]
                             [--remote_sif_path REMOTE_SIF_PATH]
                             [--sif_bind_path SIF_BIND_PATH]

options:
  -h, --help            show this help message and exit
  --time TIME           The time to run the tunnel for, which is the time limit for the SLURM job.
                        Format is DD-HH:MM:SS, HH:MM:SS, or MM:SS.
  --remote_host REMOTE_HOST
                        The remote host for the SLURM login node, as defined in ~/.ssh/config.
  --cpus CPUS           The number of CPUs to use for the SLURM job.
  --mem MEM             The amount of memory to use for the SLURM job.
  --qos QOS             The QOS to use for the SLURM job.
  --partition PARTITION
                        The partition to use for the SLURM job.
  --remote_sbatch_path REMOTE_SBATCH_PATH
                        The path to the tunnel.sbatch script on the remote, from the home directory 
                        of the remote user.
  --remote_sif_path REMOTE_SIF_PATH
                        The path to the singularity image on the remote, from the home directory 
                        of the remote user.
  --sif_bind_path SIF_BIND_PATH
                        The path to bind the singularity image to on the remote.
```

### Initialization

It's recommended to initialize the tunnel once, by running:

```sh
slurm-job-tunnel init [options]
```

This will create a (local) config file located at `~/.slurm-job-tunnel/config.json` with the provided arguments, which henceforth will be used as defaults for the `run` command.

### Create a job tunnel

To create a job tunnel, run:

```sh
slurm-job-tunnel run [options]
```

### Install packages in the singularity image

The singularity image contains the following packages:

- `ssh`
- `openssh`

Any additional packages can be installed in the image by adding them to the `openssh.def` file, as follows:

```def
%post
    # ... existing code ...

    # Install additional packages
    apt-get install -y <PACKAGE_NAME>

    # ... existing code ...
```

After updating the `openssh.def` file, the image has to be rebuilt and copied to the remote host, as described above.

### Manual cleanup

If something goes wrong with the job tunnel cleanup, you can manually remove the job tunnel by canceling the SLURM job on the remote host (`scancel <JobID>`), removing the `<host>-job` and `<host>-job-port-forward` entries in `~/.ssh/config`, and stopping the local port forwarding tunnel by killing the `ssh` process (`kill <PID>`). You can find the PID of the `ssh` process by running `netstat -tpln` (from the `net-tools` package). Look for the line with a listening port on `localhost`.

## Future work

- [ ] Update ssh-server settings to make sure only `USER` can access the tunnel

## License

This project is licensed under the MIT License.
