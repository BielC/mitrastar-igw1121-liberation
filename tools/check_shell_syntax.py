"""Parse public router scripts without executing them."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
subprocess.run(["/bin/sh", "-n", str(root / "router-cli")], check=True)
for script in sorted((root / "router").iterdir()):
    if script.is_file():
        subprocess.run(["/bin/sh", "-n", str(script)], check=True)
print("Shell syntax passed.")
