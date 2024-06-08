import argparse
import os
import json

from .tunnel_config import TunnelConfig
from .run_tunnel import run_tunnel

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".slurm-job-tunnel")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def load_config() -> TunnelConfig:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return TunnelConfig(**json.load(f))
    return TunnelConfig()


def parse_args() -> TunnelConfig:

    config = load_config()
    DEFAULT_CONFIG = TunnelConfig()

    def get_from_config(key):
        return getattr(config, key, getattr(DEFAULT_CONFIG, key))

    parser = argparse.ArgumentParser(
        description=(
            "SLURM Job Tunnel: A utility to submit a SLURM job with specified resources "
            "and establish an SSH tunnel to the allocated compute node. It also integrates "
            "with Visual Studio Code to provide a seamless development environment "
            "on the remote host."
        )
    )

    parser.add_argument(
        "mode",
        type=str,
        choices=["init", "run"],
        help=(
            "The mode to run the SLURM job tunnel in. 'init' initializes the SLURM job tunnel by creating "
            "a default configuration file. 'run' allocates the requested resources and establishes the "
            "SSH tunnel."
        ),
    )

    parser.add_argument(
        "--remote_host",
        type=str,
        default=get_from_config("remote_host"),
        help="The remote host for the SLURM login node, as defined in ~/.ssh/config.",
    )
    parser.add_argument(
        "--time",
        type=str,
        default=get_from_config("time"),
        help="Time limit for the SLURM job. Format is DD-HH:MM:SS, HH:MM:SS, or MM:SS.",
    )
    parser.add_argument(
        "--cpus",
        type=int,
        default=get_from_config("cpus"),
        help="The number of CPUs for the SLURM job",
    )
    parser.add_argument(
        "--mem",
        type=str,
        default=get_from_config("mem"),
        help="The amount of memory for the SLURM job",
    )

    parser.add_argument(
        "--qos",
        type=str,
        default=get_from_config("qos"),
        help="The QOS for the SLURM job",
    )

    parser.add_argument(
        "--partition",
        type=str,
        default=get_from_config("partition"),
        help="The partition for the SLURM job",
    )

    parser.add_argument(
        "--remote_sbatch_path",
        type=str,
        default=get_from_config("remote_sbatch_path"),
        help="Path from the home directory of the remote user to where the sbatch script should be placed. Default is 'tunnel.sbatch'.",
    )
    parser.add_argument(
        "--remote_sif_path",
        type=str,
        default=get_from_config("remote_sif_path"),
        help="Path from the home directory of the remote user to the remote singularity image to be executed. Default is 'singularity/openssh.sif'.",
    )
    parser.add_argument(
        "--sif_bind_path",
        type=str,
        default=get_from_config("sif_bind_path"),
        help="Path on the remote host to bind to the singularity image. Default is '/scratch/$USER'.",
    )

    args = parser.parse_args()
    return args.mode, TunnelConfig(
        **{k: v for k, v in args.__dict__.items() if k != "mode"}
    )


def main():

    mode, tunnel_config = parse_args()
    if mode == "init":

        if os.path.exists(CONFIG_FILE):
            print(
                f"Config file {CONFIG_FILE} already exists. Instead of running 'init', "
                f"you can edit the file directly, or remove the file ('rm {CONFIG_FILE}') and run 'init' again."
            )
            return
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(tunnel_config.to_dict(), f, indent=4)

        print(f"Default job tunnel configuration saved to {CONFIG_FILE}")

    elif mode == "run":
        run_tunnel(tunnel_config)
