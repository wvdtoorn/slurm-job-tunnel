from setuptools import setup, find_packages

setup(
    name="slurm-job-tunnel",
    version="0.1.0",
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
