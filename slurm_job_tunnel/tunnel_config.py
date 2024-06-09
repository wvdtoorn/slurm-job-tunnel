from dataclasses import dataclass, asdict


@dataclass
class TunnelConfig:
    remote_host: str = "hpc-login"
    time: str = "1:00:00"
    cpus: int = 4
    mem: str = "2G"
    qos: str = "hiprio"
    partition: str = None
    remote_sbatch_path: str = "tunnel.sbatch"
    remote_sif_path: str = "singularity/openssh.sif"
    sif_bind_path: str = "/scratch/$USER"

    def to_dict(self):
        return asdict(self)

    def get(self, key: str):
        return getattr(self, key, None)

    @staticmethod
    def _help_all() -> dict:
        return {
            "remote_host": "The remote host for the SLURM login node, as defined in ~/.ssh/config.",
            "time": "The time to run the tunnel for, which is the time limit for the SLURM job. Format is DD-HH:MM:SS, HH:MM:SS, or MM:SS.",
            "cpus": "The number of CPUs to use for the SLURM job.",
            "mem": "The amount of memory to use for the SLURM job.",
            "qos": "The QOS to use for the SLURM job.",
            "partition": "The partition to use for the SLURM job.",
            "remote_sbatch_path": "The path to the tunnel.sbatch script on the remote, from the home directory of the remote user.",
            "remote_sif_path": "The path to the singularity image on the remote, from the home directory of the remote user.",
            "sif_bind_path": "The path to bind the singularity image to on the remote.",
        }

    @staticmethod
    def help(key: str = None) -> str:
        if key is None:
            return "\n".join([f"{k}: {v}" for k, v in TunnelConfig._help_all().items()])
        return TunnelConfig._help_all().get(key, "")
