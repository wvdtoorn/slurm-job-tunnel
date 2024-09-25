"""
Slurm Job Tunnel

Copyright (c) 2024 by Wiep K. van der Toorn

"""

from setuptools import setup, find_packages
import re

VERSIONFILE = "slurm_job_tunnel/_version.py"
verstrline = open(VERSIONFILE, "rt").read()
VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search(VSRE, verstrline, re.M)
if mo:
    verstr = mo.group(1)
else:
    raise RuntimeError("Unable to find version string in %s." % (VERSIONFILE,))


setup(
    name="slurm-job-tunnel",
    version=verstr,
    packages=find_packages(),
    install_requires=[
        "slurm-job-util @ git+https://github.com/wvdtoorn/slurm-job-util.git"
    ],
    entry_points={
        "console_scripts": [
            "slurm-job-tunnel=slurm_job_tunnel.main:main",
            "sjt=slurm_job_tunnel.main:main",
        ],
    },
    author="Wiep van de Toorn",
    description="A utility to submit a SLURM job with specified resources "
    "and establish an SSH tunnel to the allocated compute node.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/wvdtoorn/slurm-job-tunnel",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
