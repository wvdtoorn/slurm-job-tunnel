from dataclasses import dataclass, asdict

from slurm_job_util.slurm_job import SBatchCommand


@dataclass
class TunnelConfig:
    remote_host: str = "hpc-login"
    time: str = "1:00:00"
    cpus_per_task: int = None
    cpus_per_gpu: int = None
    mem_per_cpu: str = None
    mem_per_gpu: str = None
    qos: str = None
    partition: str = None
    gpus: int = None
    nodes: int = None
    ntasks: int = None
    ntasks_per_node: int = None
    remote_sbatch_path: str = "tunnel.sbatch"
    remote_sif_path: str = "singularity/openssh.sif"
    sif_bind_path: str = "/scratch/$USER"

    def to_dict(self):
        return asdict(self)

    def get(self, key: str):
        return getattr(self, key, None)

    def sbatch_kwargs(self) -> dict:
        return {
            k: self.get(k)
            for k in SBatchCommand.__dict__["__dataclass_fields__"].keys()
            if self.get(k) is not None
        }

    @staticmethod
    def _help_all() -> dict:
        return {
            "remote_host": "The remote host for the SLURM login node, as defined in ~/.ssh/config.",
            "time": "The time to run the tunnel for, which is the time limit for the SLURM job. Format is DD-HH:MM:SS, HH:MM:SS, or MM:SS.",
            "cpus_per_task": "The number of CPUs to use for each task in the SLURM job.",
            "cpus_per_gpu": "The number of CPUs to use for each GPU in the SLURM job.",
            "mem_per_cpu": "The amount of memory to use for each CPU in the SLURM job.",
            "mem_per_gpu": "The amount of memory to use for each GPU in the SLURM job.",
            "qos": "The QOS to use for the SLURM job.",
            "export": "The environment variables to export to the SLURM job.",
            "partition": "The partition to use for the SLURM job.",
            "gpus": "The number of GPUs to use for the SLURM job.",
            "nodes": "The number of nodes to use for the SLURM job.",
            "ntasks": "The number of tasks to use for the SLURM job.",
            "ntasks_per_node": "The number of tasks to use for each node in the SLURM job.",
            "remote_sbatch_path": "The path to the tunnel.sbatch script on the remote, from the home directory of the remote user.",
            "remote_sif_path": "The path to the singularity image on the remote, from the home directory of the remote user.",
            "sif_bind_path": "The path to bind the singularity image to on the remote.",
        }

    @staticmethod
    def help(key: str = None) -> str:
        if key is None:
            return "\n".join([f"{k}: {v}" for k, v in TunnelConfig._help_all().items()])
        return TunnelConfig._help_all().get(key, "")
