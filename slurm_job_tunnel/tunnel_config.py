from dataclasses import dataclass


@dataclass
class TunnelConfig:
    time: str = "1:00:00"
    remote_host: str = "hpc-login"
    cpus: int = 4
    mem: str = "2G"
    qos: str = "hiprio"
    partition: str = None
    remote_sbatch_path: str = "tunnel.sbatch"
    remote_sif_path: str = "singularity/openssh.sif"
    sif_bind_path: str = "/scratch/$USER"

    def to_dict(self):
        return self.__dict__

    def get(self, key: str):
        return getattr(self, key, None)
