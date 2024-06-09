import os
import shutil
import signal
import subprocess
import time
import logging
from datetime import datetime
from typing import List, Tuple, TYPE_CHECKING
from dataclasses import dataclass
import psutil
import sys

from slurm_job_util.slurm_job import SBatchCommand, RemoteHost
from slurm_job_util.ssh_config import SSHConfig, SSHConfigEntry

if TYPE_CHECKING:
    from .tunnel_config import TunnelConfig

SBATCH_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "tunnel.sbatch"
)


@dataclass
class JobTunnel:
    job_command: "SBatchCommand"
    remote_host: "RemoteHost"

    # post-init attributes
    job_id: int = None
    port: int = None
    node: str = None
    termination_time: datetime = None

    def submit_slurm_job(self) -> int:

        result = self.remote_host.execute(self.job_command.command, stdout=False)

        if result.returncode != 0:
            raise ValueError(f"Failed to submit SLURM job: {result.stderr}")

        self.job_id = int(result.stdout.strip().split()[-1])
        return self.job_id

    def cancel_slurm_job(self) -> None:
        if self.job_status in ["PENDING", "RUNNING", "STOPPED"]:
            self.remote_host.execute(f"scancel {self.job_id}")
            logging.info("Cancelled the SLURM job")

    @property
    def job_status(self) -> str:
        job_status = self.remote_host.execute(
            f"squeue -j {self.job_id} -h -o %T"
        ).stdout.strip()
        return job_status

    @property
    def is_running(self) -> bool:
        return self.job_status == "RUNNING"

    def watch_output_for_text(
        self, watch_texts: List[str], wait_time: float = 0.01, timeout: float = 60
    ) -> List[str]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            output = self.remote_host.execute(f"cat {self.job_command.output}").stdout
            found_texts = []
            for line in output.splitlines():
                for watch_text in watch_texts:
                    if watch_text in line:
                        found_texts.append(line)
                if len(found_texts) == len(watch_texts):
                    return found_texts
            time.sleep(wait_time)
        raise TimeoutError(f"Timed out waiting for {watch_texts}")

    def get_tunnel_info(self) -> Tuple[int, str, datetime]:
        if not self.is_running:
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
    tunnel_entry: SSHConfigEntry = None,
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

    script_ext = os.path.splitext(config.remote_sbatch_path)[1]
    output = config.remote_sbatch_path.replace(f"{script_ext}", ".out")
    job_command = SBatchCommand(
        script=config.remote_sbatch_path,
        time=config.time,
        cpus_per_task=config.cpus,
        mem_per_cpu=config.mem,
        qos=config.qos,
        partition=config.partition,
        output=output,
        export=[
            (
                f"SIF_BIND_PATH=" + f"{config.sif_bind_path}"
                if config.sif_bind_path
                else ""
            ),
            f"SIF_IMAGE={config.remote_sif_path}",
        ],
    )

    logging.info(f"Validating SSH config")
    job_tunnel = JobTunnel(
        job_command=job_command,
        remote_host=RemoteHost(config.remote_host),
    )

    signal.signal(
        signal.SIGINT,
        lambda sig, frame: cleanup(job_tunnel=job_tunnel, exit=True),
    )

    logging.info(
        f"Submitting {job_command.script} to {job_tunnel.remote_host.host} with command: {job_command.command}"
    )

    job_id = job_tunnel.submit_slurm_job()
    logging.info(f"Submitted job. Job ID: {job_id}")
    logging.info("Waiting for job to start")

    while not job_tunnel.is_running:
        logging.info("Job is queued, sleeping for 5 seconds")
        time.sleep(5)

    logging.info("Job is running")
    port, node, termination_time = job_tunnel.get_tunnel_info()

    logging.info(f"Tunnel established (node={node}, port={port})")
    logging.info(
        f"This tunnel will terminate at {termination_time.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    tunnel_entry = SSHConfigEntry(
        host=f"{job_tunnel.remote_host.host}-job",
        node=node,
        port=port,
        user=job_tunnel.remote_host.entry.user,
        proxy=job_tunnel.remote_host.host,
    )
    logging.info(f"Updating SSH config: adding tunnel host '{tunnel_entry.host}'")

    ssh_config_path = os.path.join(os.path.expanduser("~"), ".ssh", "config")
    ssh_config = SSHConfig(ssh_config_path)
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
