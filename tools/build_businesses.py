"""Compatibility entry point for the shared static website card builder."""
from pathlib import Path
import subprocess

if __name__ == "__main__":
    subprocess.run(["node", str(Path(__file__).with_suffix(".cjs"))], check=True)