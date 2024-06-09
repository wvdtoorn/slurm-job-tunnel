import argparse
import os
import json
from dataclasses import fields

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

    subparsers = parser.add_subparsers(dest="mode", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help="Initialize the SLURM job tunnel by creating a configuration file.",
    )
    run_parser = subparsers.add_parser(
        "run",
        help="Allocate the requested resources and establish the SSH tunnel.",
    )
    reset_parser = subparsers.add_parser(
        "reset",
        help="Reset the tool configuration to default values.",
    )

    for field in fields(TunnelConfig):
        if not field.name.startswith("_"):
            field_type = field.type
            help_text = TunnelConfig.help(field.name)
            init_parser.add_argument(
                f"--{field.name}",
                type=field_type,
                default=get_from_config(field.name),
                help=help_text,
            )
            run_parser.add_argument(
                f"--{field.name}",
                type=field_type,
                default=get_from_config(field.name),
                help=help_text,
            )

    args = parser.parse_args()
    return args.mode, TunnelConfig(
        **{k: v for k, v in args.__dict__.items() if k != "mode"}
    )


def main():

    mode, tunnel_config = parse_args()
    if mode == "reset":
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
            print(f"Removed configuration file {CONFIG_FILE}")
        else:
            print(f"Configuration file {CONFIG_FILE} does not exist. Nothing to do.")
        return

    if mode == "init":

        if os.path.exists(CONFIG_FILE):
            print(
                f"Config file {CONFIG_FILE} already exists. Instead of running 'init', "
                f"you can edit the file directly, or run 'reset' before running 'init' again."
            )
            return

        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(tunnel_config.to_dict(), f, indent=4)

        print(f"Default job tunnel configuration saved to {CONFIG_FILE}")

    elif mode == "run":
        run_tunnel(tunnel_config)
