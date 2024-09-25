"""
Slurm Job Tunnel

Copyright (c) 2024 by Wiep K. van der Toorn

"""

import os
import signal
import subprocess
import time
import logging
from datetime import datetime
from typing import List, Tuple, TYPE_CHECKING
from dataclasses import dataclass
import sys
import tkinter as tk
from tkinter import messagebox
import socket
import threading
import pexpect

from slurm_job_util.slurm_job import SBatchCommand, SlurmJob
from slurm_job_util.ssh_config import SSHConfig, SSHConfigEntry
from slurm_job_util.utils import execute_on_host

if TYPE_CHECKING:
    from .tunnel_config import TunnelConfig

SBATCH_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "tunnel.sbatch"
)


def show_time_limit_warning():
    """
    Show a blocking popup with the time limit warning.
    """
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    messagebox.showwarning(
        "Warning",
        "The tunnel on the HPC will close in less than 1 minute! Save your work and close the IDE."
        " After accepting this warning, the tunnel will be closed locally.",
    )
    root.destroy()


def show_tunnel_ready_info(
    tunnel_entry: SSHConfigEntry, local_tunnel_entry: SSHConfigEntry
):
    """
    Show a non-blocking popup with the tunnel ready info.
    """

    def show_popup():
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showinfo(
            "Info",
            f"The tunnel on the HPC is ready! You can now connect to the tunnel using "
            f"'ssh {tunnel_entry.host}' or 'ssh {local_tunnel_entry.host}'.",
        )
        root.destroy()

    threading.Thread(target=show_popup).start()


@dataclass
class JobTunnel:
    job_command: "SBatchCommand"
    host: "SSHConfigEntry"

    # post-init attributes
    job_id: int | None = None
    port: int | None = None
    node: str | None = None
    termination_time: datetime | None = None
    job: SlurmJob = None

    def execute_on_host(self, command: str) -> subprocess.CompletedProcess:
        return execute_on_host(self.host.host, command)

    def submit_slurm_job(self) -> int:

        result = self.execute_on_host(self.job_command.command)

        self.job_id = int(result.stdout.strip().split()[-1])
        self.job = SlurmJob(job_id=self.job_id, host=self.host.host)
        return self.job_id

    def cancel_slurm_job(self) -> None:
        self.job.cancel()

    @property
    def status_slurm_job(self) -> str:
        return self.job.status

    @property
    def is_running(self) -> bool:
        return self.job.is_running

    def watch_output_for_text(
        self, watch_texts: List[str], wait_time: float = 0.01, timeout: float = 60
    ) -> List[str]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            output = self.execute_on_host(f"cat {self.job_command.output}").stdout
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


class LocalTunnel:
    def __init__(self, remote_tunnel_entry: SSHConfigEntry):

        self.remote_tunnel_entry: SSHConfigEntry = remote_tunnel_entry

        self._port: int | None = None
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event = threading.Event()
        self._created: bool = False

        self._local_tunnel_entry: SSHConfigEntry | None = None

    @property
    def port(self) -> int:
        if self._port is None:
            raise ValueError("Local tunnel port is not set")

        return self._port

    @property
    def thread(self) -> threading.Thread:
        if self._thread is None:
            raise ValueError("Local tunnel thread is not set")

        return self._thread

    @property
    def local_tunnel_entry(self) -> SSHConfigEntry:
        if self._local_tunnel_entry is None:
            raise ValueError("Local tunnel entry is not set")

        return self._local_tunnel_entry

    def find_free_port(
        self,
    ) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            return s.getsockname()[1]

    def create(self):
        self._port = self.find_free_port()
        self._thread = threading.Thread(
            target=self.thread_target,
            daemon=False,
        )
        self._thread.start()

        while not self._created:
            time.sleep(0.1)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def thread_target(self):
        ssh_command = f"ssh -N -L {self.port}:localhost:{self.remote_tunnel_entry.port} {self.remote_tunnel_entry.host}"
        logging.info(f"Local tunnel command: {ssh_command}")

        try:
            child = pexpect.spawn(ssh_command)
            i = child.expect(
                [
                    "Are you sure you want to continue connecting",
                    pexpect.EOF,
                    pexpect.TIMEOUT,
                ],
                timeout=30,
            )
            if i == 0:
                child.sendline("yes")
            child.expect(["Warning: Permanently added", pexpect.EOF], timeout=30)
        except Exception as e:
            logging.error(f"Error creating local tunnel: {e}")

        self._local_tunnel_entry = SSHConfigEntry(
            host=f"{self.remote_tunnel_entry.host}-port-forward",
            hostname="localhost",
            port=self.port,
            user=self.remote_tunnel_entry.user,
        )

        SSHConfig().update_config(self.local_tunnel_entry)
        self._created = True

        # listen for stop_event
        self._stop_event.wait()

    def _set_stop(self):
        self._stop_event.set()

    def cleanup(self):

        SSHConfig().remove_entry(self.local_tunnel_entry.host)

        if not self.is_running:
            return

        self._set_stop()
        self.thread.join()


def cleanup(
    job_tunnel: JobTunnel,
    ssh_config: SSHConfig | None = None,
    tunnel_entry: SSHConfigEntry | None = None,
    local_tunnel: LocalTunnel | None = None,
    exit: bool = True,
) -> None:
    logging.info("Cleaning up the job tunnel...")
    if job_tunnel:
        job_tunnel.cancel_slurm_job()  # has own logging

    if ssh_config and tunnel_entry:
        ssh_config.remove_entry(tunnel_entry.host)
        logging.info("Cleaned up SSH config")

    if local_tunnel:
        local_tunnel.cleanup()
        logging.info("Cleaned up local tunnel")

    if exit:
        logging.info("Done. Goodbye!")
        sys.exit(0)


def run_tunnel(config: "TunnelConfig") -> None:

    script_ext = os.path.splitext(config.remote_sbatch_path)[1]
    output = config.remote_sbatch_path.replace(f"{script_ext}", ".out")

    job_command = SBatchCommand(
        script=config.remote_sbatch_path,
        **config.sbatch_kwargs(),
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

    ssh_config_path = os.path.join(os.path.expanduser("~"), ".ssh", "config")
    ssh_config = SSHConfig(ssh_config_path)
    host_entry = ssh_config.get_entry(config.remote_host)
    job_tunnel = JobTunnel(
        job_command=job_command,
        host=host_entry,
    )

    # if SIGINT is received, cleanup the job tunnel and exit
    signal.signal(
        signal.SIGINT,
        lambda sig, frame: cleanup(
            job_tunnel=job_tunnel,
            ssh_config=ssh_config,
            tunnel_entry=tunnel_entry,
        ),
    )

    logging.info(
        f"Submitting {job_command.script} to {job_tunnel.host.host} with command: {job_command.command}"
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
        host=f"{host_entry.host}-job",
        hostname=node,
        port=port,
        user=host_entry.user,
        proxy=host_entry.host,
    )
    logging.info(f"Updating SSH config: adding tunnel host '{tunnel_entry.host}'")

    ssh_config.update_config(tunnel_entry)

    logging.info(f"Added tunnel host '{tunnel_entry.host}' to {ssh_config_path}")

    logging.info(
        f"SSH config tunnel entry: \n\n{ssh_config.get_entry(tunnel_entry.host)}"
    )
    # find random free port on localhost

    logging.info(f"Creating local tunnel to {tunnel_entry.host}:{tunnel_entry.port}")

    local_tunnel = LocalTunnel(tunnel_entry)
    local_tunnel.create()

    logging.info(
        f"Added local port forwarding host '{local_tunnel.local_tunnel_entry.host}' to {ssh_config_path}"
    )

    logging.info(
        f"SSH config local tunnel entry: \n\n{ssh_config.get_entry(local_tunnel.local_tunnel_entry.host)}"
    )

    # if SIGINT is received, cleanup the job tunnel and local tunnel and exit
    signal.signal(
        signal.SIGINT,
        lambda sig, frame: cleanup(
            job_tunnel=job_tunnel,
            ssh_config=ssh_config,
            tunnel_entry=tunnel_entry,
            local_tunnel=local_tunnel,
        ),
    )

    show_tunnel_ready_info(tunnel_entry, local_tunnel.local_tunnel_entry)

    logging.info(
        "To cancel the slurm job and close this job tunnel, stop this script by pressing Ctrl+C. "
    )

    assert job_tunnel.termination_time is not None, "Termination time is not set"

    time.sleep((job_tunnel.termination_time - datetime.now()).total_seconds() - 60)
    logging.info("Tunnel will close in 1 minute!")
    show_time_limit_warning()
    logging.info("Tunnel closed")

    cleanup(
        job_tunnel=job_tunnel,
        ssh_config=ssh_config,
        tunnel_entry=tunnel_entry,
        local_tunnel=local_tunnel,
    )
