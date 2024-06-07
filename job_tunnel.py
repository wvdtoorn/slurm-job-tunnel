import argparse
import os
import signal
import subprocess
import sys
import time
import logging
from datetime import datetime, timedelta
from typing import Tuple
from dataclasses import dataclass

from ssh_config import SSHConfig, SSHEntry

SBATCH_SCRIPT = os.path.join(os.path.dirname(__file__), "tunnel.sbatch")

# Configure logging
logging.basicConfig(
    format="%(asctime)s %(message)s", datefmt="%H:%M:%S", level=logging.INFO
)

parser = argparse.ArgumentParser(description="SLURM Tunnel Script")
parser.add_argument(
    "--time",
    type=int,
    required=True,
    help="Time in minutes for the SLURM job / tunnel",
)
parser.add_argument(
    "--remote_host",
    type=str,
    required=True,
    help="The remote host for the SLURM login node",
)
parser.add_argument(
    "--cpus",
    type=int,
    default=8,
    help="The number of CPUs for the SLURM job",
)
parser.add_argument(
    "--mem",
    type=str,
    default="16G",
    help="The amount of memory for the SLURM job",
)
parser.add_argument(
    "--remote_script_path",
    type=str,
    default="tunnel.sbatch",
    help="Path from the home directory of the remote user to the remote script to be executed. Default is tunnel.sbatch",
)
parser.add_argument(
    "--remote_sif_path",
    type=str,
    default="singularity/openssh.sif",
    help="Path from the home directory of the remote user to the remote singularity image to be executed. Default is openssh.sif",
)


@dataclass
class JobTunnel:
    time: int  # in minutes
    remote_host: str
    cpus: int
    mem: str  # e.g. 500M, 16G
    remote_path: str  # script to be executed on the remote host
    remote_sif_path: str  # singularity image to be executed on the remote host

    # post-init attributes
    job_id: str = None
    local_start_time: int = None
    port: int = None
    node: str = None

    def __post_init__(self) -> None:
        self.remote_output_path = self.remote_path.replace(
            os.path.expanduser("~"), ""
        ).replace(".sbatch", ".out")
        self.local_start_time = int(time.time())

    def start_slurm_job(self) -> None:
        result = subprocess.run(
            [
                "ssh",
                self.remote_host,
                f"sbatch --time={self.time} --output={self.remote_output_path} {os.path.join('~', self.remote_path)}",
            ],
            capture_output=True,
            text=True,
        )
        self.job_id = result.stdout.strip().split()[-1]

    def cancel_slurm_job(self) -> None:
        logging.info("Canceling the SLURM job")
        subprocess.run(["ssh", self.remote_host, f"scancel {self.job_id}"])
        sys.exit(1)

    @property
    def job_started(self) -> bool:
        result = subprocess.run(
            [
                "ssh",
                self.remote_host,
                f"squeue -j {self.job_id} -h -o %T",
            ],
            capture_output=True,
            text=True,
        )
        job_status = result.stdout.strip()
        return job_status == "RUNNING"

    def watch_output_for_text(self, watch_text: str, wait_time: float = 0.01) -> str:
        while True:
            result = subprocess.run(
                ["ssh", self.remote_host, f"cat {self.remote_output_path}"],
                capture_output=True,
                text=True,
            )
            output = result.stdout
            for line in output.splitlines():
                if watch_text in line:
                    return line
            time.sleep(wait_time)

    def get_tunnel_info(self) -> Tuple[str, str]:
        if not self.job_started:
            raise ValueError("Job is not running")
        output = self.watch_output_for_text("PORT=")
        port = output.split("=")[1]
        output = self.watch_output_for_text("NODE=")
        node = output.split("=")[1]
        self.port = port
        self.node = node
        return port, node

    def create_job_script(self) -> None:
        lines = []
        with open(SBATCH_SCRIPT, "r") as file:
            for line in file:
                if "CPUS_PER_TASK" in line:
                    lines.append(line.replace("CPUS_PER_TASK", str(self.cpus)))
                elif "MEM" in line:
                    lines.append(line.replace("MEM", self.mem))
                elif "REMOTE_SIF_PATH" in line:
                    lines.append(line.replace("REMOTE_SIF_PATH", self.remote_sif_path))
                else:
                    lines.append(line)

        with open(SBATCH_SCRIPT + ".local", "w") as file:
            file.write("\n".join(lines))

    def sync_job_script(self) -> None:
        command = [
            "rsync",
            "-az",
            SBATCH_SCRIPT + ".local",
            f"{self.remote_host}:~/{self.remote_path}",
        ]
        subprocess.run(command)

    def setup_slurm_job(self) -> None:
        self.create_job_script()
        self.sync_job_script()
        # remove local script
        os.remove(SBATCH_SCRIPT + ".local")


def main() -> None:
    args = parser.parse_args()

    job_tunnel = JobTunnel(
        time=args.time,
        remote_host=args.remote_host,
        cpus=args.cpus,
        mem=args.mem,
        remote_path=args.remote_script_path,
        remote_sif_path=args.remote_sif_path,
    )

    def signal_handler(sig, frame):
        job_tunnel.cancel_slurm_job()

    signal.signal(signal.SIGINT, signal_handler)

    logging.info("Validating SSH config")
    ssh_config_path = os.path.expanduser("~/.ssh/config")
    ssh_config = SSHConfig(ssh_config_path)
    remote_entry = ssh_config.get_entry(job_tunnel.remote_host)

    logging.info("Setting up job script on remote host")
    job_tunnel.setup_slurm_job()

    job_tunnel.start_slurm_job()
    logging.info(f"Submitted batch job {job_tunnel.job_id}")
    logging.info("Waiting for job to start")

    while not job_tunnel.job_started:
        logging.info("Job is queued")
        time.sleep(5)

    logging.info("Job is running")

    port, node = job_tunnel.get_tunnel_info()

    logging.info("Tunnel established")
    logging.info(f"Port={port}")
    logging.info(f"Node={node}")
    termination_time = datetime.now() + timedelta(minutes=job_tunnel.time)
    logging.info(
        f"This tunnel will terminate at {termination_time.strftime('%H:%M:%S')}"
    )

    tunnel_entry = SSHEntry(
        host=f"{job_tunnel.remote_host}-job",
        node=node,
        port=port,
        user=remote_entry.user,
        proxy=job_tunnel.remote_host,
    )
    logging.info(f"Updating SSH config: adding tunnel host '{tunnel_entry.host}'")
    ssh_config.update_config(tunnel_entry)

    logging.info(f"Added tunnel host '{tunnel_entry.host}' to {ssh_config_path}")
    logging.info(
        f"Starting IDE application. Please connect your window to Host'{tunnel_entry.host}'"
    )
    logging.info(
        "To close the tunnel / cancel the slurm job, stop this script by pressing Ctrl+C"
    )

    subprocess.Popen("code")
    time.sleep(job_tunnel.time * 60)
    job_tunnel.cancel_slurm_job()


if __name__ == "__main__":
    main()
