"""Catch accidental capture files and common secret/identifier formats."""
from pathlib import Path
import re
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
paths = subprocess.run(
    ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
    cwd=root, capture_output=True, check=True,
).stdout.decode().split("\0")
bad = []
for name in sorted(set(filter(None, paths))):
    path = root / name
    if not path.is_file():
        continue
    if path.suffix.lower() in {".xml", ".bin", ".elf", ".7z", ".har", ".cookies", ".log", ".png", ".jpg"}:
        bad.append((name, "private capture or vendor artifact type"))
    if path.name in {"pin", "iccid", "pin.previous", "iccid.previous", ".env"}:
        bad.append((name, "private configuration filename"))
    try:
        content = path.read_text()
    except UnicodeDecodeError:
        bad.append((name, "unexpected binary file"))
        continue
    checks = {
        "local user path": r"/(?:Users|home)/[^/\s]+/",
        "SIM/device-sized numeric identifier": r"(?<!\d)\d{14,22}(?!\d)",
        "MAC address": r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b",
        "private key": r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----",
        "GitHub token": r"\b(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}\b",
    }
    for label, expression in checks.items():
        if re.search(expression, content):
            bad.append((name, label))
    if name.startswith("router/") and re.search(r"\bpin=['\"]?\d{4,8}\b", content):
        bad.append((name, "literal PIN in production script"))

if bad:
    # Print only locations and categories, never matching secret values.
    for name, label in bad:
        print(f"{name}: {label}", file=sys.stderr)
    sys.exit(1)
print("Public-file checks passed. Review still required before publishing.")
