import os
import shutil
import signal
import subprocess
import time
import logging
from datetime import datetime
from typing import List, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
import psutil
import sys

from .ssh_config import SSHConfig, SSHEntry

if TYPE_CHECKING:
    from .tunnel_config import TunnelConfig

SBATCH_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "tunnel.sbatch"
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s %(message)s", datefmt="%H:%M:%S", level=logging.INFO
)


@dataclass
class SBatchCommand:
    """
    A class to represent a SLURM sbatch command.
    """

    script: str = "tunnel.sbatch"
    time: str = "3:00:00"
    cpus: int = 8
    mem: str = "16G"
    qos: str = "hiprio"
    output: str = "tunnel.out"
    export: List[str] = field(default_factory=["SIF_IMAGE=singularity/openssh.sif"])
    partition: str = None
    gpus: int = None
    mem_per_gpu: int = None

    def command(self) -> str:
        command = ["sbatch"]
        if self.time:
            command.append(f"--time={self.time}")
        if self.cpus:
            command.append(f"--cpus-per-task={self.cpus}")
        if self.mem:
            command.append(f"--mem={self.mem}")
        if self.qos:
            command.append(f"--qos={self.qos}")
        if self.partition:
            command.append(f"--partition={self.partition}")
        if self.output:
            command.append(f"--output={self.output}")
        if self.export:
            command.append(f"--export={','.join(self.export)}")

        command.append(self.script)
        command = " ".join(command)
        return command


@dataclass
class JobTunnel:
    job_command: SBatchCommand
    remote_host: str

    # post-init attributes
    job_id: int = None
    port: int = None
    node: str = None
    termination_time: datetime = None

    def submit_slurm_job(self) -> int:

        result = subprocess.run(
            [
                "ssh",
                self.remote_host,
                self.job_command.command(),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise ValueError(f"Failed to submit SLURM job: {result.stderr}")

        self.job_id = int(result.stdout.strip().split()[-1])
        return self.job_id

    def cancel_slurm_job(self) -> None:
        if self.job_status in ["PENDING", "RUNNING", "STOPPED"]:
            subprocess.run(["ssh", self.remote_host, f"scancel {self.job_id}"])
            logging.info("Cancelled the SLURM job")

    @property
    def job_status(self) -> str:
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
        return job_status

    @property
    def job_running(self) -> bool:
        return self.job_status == "RUNNING"

    def watch_output_for_text(
        self, watch_texts: List[str], wait_time: float = 0.01
    ) -> List[str]:
        while True:
            result = subprocess.run(
                ["ssh", self.remote_host, f"cat {self.job_command.output}"],
                capture_output=True,
                text=True,
            )
            output = result.stdout
            found_texts = []
            for line in output.splitlines():
                for watch_text in watch_texts:
                    if watch_text in line:
                        found_texts.append(line)
                if len(found_texts) == len(watch_texts):
                    return found_texts
            time.sleep(wait_time)

    def get_tunnel_info(self) -> Tuple[int, str, datetime]:
        if not self.job_running:
            raise ValueError("Job is not running")

        output_lines = self.watch_output_for_text(
            ["PORT=", "NODE=", "This tunnel will close at: "]
        )

        port = next(line.split("=")[1] for line in output_lines if "PORT=" in line)
        node = next(line.split("=")[1] for line in output_lines if "NODE=" in line)
        termination_time = next(
            line.split("at: ")[1]
            for line in output_lines
            if "This tunnel will close at: " in line
        )

        self.port = int(port)
        self.node = node
        self.termination_time = datetime.strptime(termination_time, "%Y-%m-%d %H:%M:%S")

        return self.port, self.node, self.termination_time


def is_code_installed() -> bool:
    """Check if 'code' (Visual Studio Code) is installed in the system's PATH."""
    return shutil.which("code") is not None


def get_code_pids():
    code_pids = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            if f"{os.sep}code" in " ".join(proc.info["cmdline"]):
                code_pids.append(proc.info["pid"])
        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
            FileNotFoundError,
        ):
            pass

    return code_pids


def kill_code_processes(dont_kill_pids: List[int] = None):
    code_pids = get_code_pids()
    for pid in code_pids:
        if dont_kill_pids and pid in dont_kill_pids:
            continue
        try:
            psutil.Process(pid).terminate()
            psutil.wait_procs([psutil.Process(pid)], timeout=0.1)
        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
            FileNotFoundError,
        ):
            pass

    logging.info("Killed code processes")


def cleanup(
    job_tunnel: JobTunnel = None,
    ssh_config: SSHConfig = None,
    tunnel_entry: SSHEntry = None,
    prev_code_pids: List[int] = None,
    exit: bool = False,
) -> None:
    logging.info("Cleaning up the tunnel...")
    if job_tunnel:
        job_tunnel.cancel_slurm_job()  # has own logging

    if prev_code_pids:
        kill_code_processes(dont_kill_pids=prev_code_pids)  # has own logging

    if ssh_config and tunnel_entry:
        ssh_config.remove_entry(tunnel_entry.host)
        logging.info("Cleaned up SSH config")

    if exit:
        logging.info("Done. Goodbye!")
        sys.exit(0)


def run_tunnel(config: "TunnelConfig") -> None:

    job_command = SBatchCommand(
        script=config.remote_sbatch_path,
        time=config.time,
        cpus=config.cpus,
        mem=config.mem,
        qos=config.qos,
        partition=config.partition,
        output=config.remote_sbatch_path.replace(".sbatch", ".out"),
        export=[
            (
                f"SIF_BIND_PATH=" + f"{config.sif_bind_path}"
                if config.sif_bind_path
                else ""
            ),
            f"SIF_IMAGE={config.remote_sif_path}",
        ],
    )

    job_tunnel = JobTunnel(
        job_command=job_command,
        remote_host=config.remote_host,
    )

    signal.signal(
        signal.SIGINT,
        lambda sig, frame: cleanup(job_tunnel=job_tunnel, exit=True),
    )

    ssh_config_path = os.path.expanduser("~/.ssh/config")
    logging.info(
        f"Validating SSH config ({ssh_config_path}). Host: {job_tunnel.remote_host}"
    )
    ssh_config = SSHConfig(ssh_config_path)
    remote_entry: SSHEntry = ssh_config.get_entry(job_tunnel.remote_host)

    logging.info(f"Validated SSH config")

    logging.info(f"Submitting tunnel.sbatch job to {job_tunnel.remote_host}")
    logging.info(f"Job command: {job_command.command()}")

    job_id = job_tunnel.submit_slurm_job()
    logging.info(f"Submitted tunnel.sbatch job. Job ID: {job_id}")
    logging.info("Waiting for job to start")

    while not job_tunnel.job_running:
        logging.info("Job is queued")
        time.sleep(5)

    logging.info("Job is running")
    port, node, termination_time = job_tunnel.get_tunnel_info()

    logging.info(f"Tunnel established (node={node}, port={port})")
    logging.info(
        f"This tunnel will terminate at {termination_time.strftime('%Y-%m-%d %H:%M:%S')}"
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

    signal.signal(
        signal.SIGINT,
        lambda sig, frame: cleanup(
            job_tunnel=job_tunnel,
            ssh_config=ssh_config,
            tunnel_entry=tunnel_entry,
            exit=True,
        ),
    )

    prev_code_pids = None
    if is_code_installed():
        logging.info("Starting code IDE application")
        # code starts up multiple processes, so we need to kill them later
        prev_code_pids = get_code_pids()
        subprocess.Popen("code")

        signal.signal(
            signal.SIGINT,
            lambda sig, frame: cleanup(
                job_tunnel=job_tunnel,
                ssh_config=ssh_config,
                tunnel_entry=tunnel_entry,
                prev_code_pids=prev_code_pids,
                exit=True,
            ),
        )

    else:
        logging.info("Code is not installed. Skipping code IDE application startup.")
        logging.info(
            f"You can still use the tunnel manually, using 'ssh {tunnel_entry.host}'"
        )

    logging.info(
        "To cancel the slurm job and close this job tunnel, stop this script by pressing Ctrl+C. "
        "This will also terminate any started code IDE processes."
    )

    time.sleep((job_tunnel.termination_time - datetime.now()).total_seconds() - 60)
    logging.info("Tunnel will close in 1 minute!")
    time.sleep(60)
    logging.info("Tunnel closed")

    cleanup(
        job_tunnel=job_tunnel,
        ssh_config=ssh_config,
        tunnel_entry=tunnel_entry,
        prev_code_pids=prev_code_pids,
        exit=True,
    )