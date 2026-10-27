"""Isolated fake router. Never reads credentials or contacts a device."""
from pathlib import Path
import fcntl
import os
import pty
import select
import subprocess
import sys
import termios
import time

ROOT = Path(__file__).resolve().parents[1]
PIN = "0" * 4
ICCID = "89" + "0" * 17
OTHER_ICCID = "89" + "0" * 16 + "1"


class Router:
    def __init__(self, root, state="MIPC_SIM_STATUS_SIM_PIN", result="success"):
        self.root = root
        self.config = root / "config"
        self.config.mkdir()
        (self.config / "pin").write_text(PIN + "\n")
        (self.config / "iccid").write_text(ICCID + "\n")
        self.write("state", state)
        self.write("identity", ICCID)
        self.write("result", result)
        self.write("protection", "1")
        self.write("sim-info", "DEVST_SIM_PIN 3 10 1\n")
        self.bin = root / "bin"
        self.bin.mkdir()
        self.cli = self.executable("cli", '''case "$1" in
 --show_sim_status) cat "$TEST_ROOT/state";;
 --at_cmd)
   case "$2" in
    'AT+CCID')
      value=$(cat "$TEST_ROOT/identity")
      [ -z "$value" ] || printf '+CCID: %sf\\nOK\\n' "$value"
      if [ -f "$TEST_ROOT/change-identity" ]; then
        cp "$TEST_ROOT/change-identity" "$TEST_ROOT/identity"
      fi
      if [ -f "$TEST_ROOT/change-state" ]; then
        cp "$TEST_ROOT/change-state" "$TEST_ROOT/state"
      fi
      ;;
    'AT+CLCK="SC",2') printf '+CLCK: %s\\nOK\\n' "$(cat "$TEST_ROOT/protection")";;
    *) exit 8;;
   esac;;
 --sim_verify_pin)
   printf 'attempt\\n' >> "$TEST_ROOT/calls"
   [ "$2" = "$(cat "$TEST_ROOT/config/pin")" ] || exit 9
   case "$(cat "$TEST_ROOT/result")" in
    success) echo MIPC_SIM_STATUS_COMPLETE_READY > "$TEST_ROOT/state";;
    fail) exit 1;;
    puk) echo MIPC_SIM_STATUS_SIM_PUK > "$TEST_ROOT/state"; exit 1;;
   esac;;
 *) exit 8;;
esac''')
        self.timeout = self.executable("timeout", 'shift 3\nexec "$@"')
        self.executable("bin/logger", 'printf "%s\\n" "$*" >> "$TEST_ROOT/log"')
        self.executable("bin/sync", ":")
        self.executable("bin/id", "echo 0")

    def write(self, name, content):
        (self.root / name).write_text(content)

    def executable(self, name, body):
        path = self.root / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o700)
        return path

    def script(self, name):
        source = (ROOT / "router" / name).read_text()
        changes = {
            "PATH=/usr/sbin:/usr/bin:/sbin:/bin": f"PATH={self.bin}:/usr/bin:/bin:/usr/sbin:/sbin",
            "CONFIG=/etc/sim-pin-unlock": f"CONFIG={self.config}",
            "RUNTIME=/tmp/sim-pin-unlock": f"RUNTIME={self.root / 'runtime'}",
            "CLI=/usr/bin/mipc_wan_cli": f"CLI={self.cli}",
            "TIMEOUT=/usr/bin/timeout": f"TIMEOUT={self.timeout}",
            "/tmp/.SimInfo": str(self.root / "sim-info"),
            "cut -d. -f1 /proc/uptime": "date +%s",
            "WAIT_SECONDS=300": "WAIT_SECONDS=1",
            "POLL_SECONDS=5": "POLL_SECONDS=1",
            "$(now) + 40": "$(now) + 1",
        }
        for before, after in changes.items():
            source = source.replace(before, after)
        path = self.root / (name + ".test")
        path.write_text(source)
        return path

    def run(self, name="sim-pin-unlock", arguments=()):
        return subprocess.run(["/bin/sh", str(self.script(name)), *arguments],
                              env=dict(os.environ, TEST_ROOT=str(self.root)),
                              capture_output=True, timeout=8)

    def calls(self):
        path = self.root / "calls"
        return len(path.read_text().splitlines()) if path.exists() else 0

    def terminal(self, name="enroll-sim-pin", entries=(PIN, PIN), arguments=(), apn_answers=("4",)):
        master, slave = pty.openpty()

        def session():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        process = subprocess.Popen(
            [sys.executable, "-c", "\n".join([
                "import subprocess, sys, termios",
                "result = subprocess.run(['/bin/sh', *sys.argv[1:]])",
                "echo = bool(termios.tcgetattr(0)[3] & termios.ECHO)",
                "print('TEST_ECHO_ENABLED=' + str(int(echo)), flush=True)",
                "sys.exit(result.returncode)",
            ]), str(self.script(name)), *arguments], stdin=slave, stdout=slave, stderr=slave,
            env=dict(os.environ, TEST_ROOT=str(self.root)), preexec_fn=session,
        )
        output = b""
        sent = 0
        prompts = [b"Known working SIM PIN (hidden): ", b"Repeat PIN (hidden): "]
        replies = list(entries)
        if arguments:
            apn_prompts = [b"Carrier [1-4]: "]
            if apn_answers and apn_answers[0] == "3":
                apn_prompts += [b"Custom APN: ", b"Data roaming [y/n]: "]
            prompts = apn_prompts + prompts
            replies = list(apn_answers) + replies
        deadline = time.monotonic() + 8
        try:
            while time.monotonic() < deadline:
                readable, _, _ = select.select([master], [], [], 0.1)
                if readable:
                    try:
                        data = os.read(master, 65536)
                    except OSError:
                        break
                    if not data:
                        break
                    output += data
                if sent < len(replies) and prompts[sent] in output:
                    os.write(master, (replies[sent] + "\n").encode())
                    sent += 1
                if process.poll() is not None and not readable:
                    break
            else:
                process.kill()
                raise AssertionError("Enrollment test exceeded its deadline")
            result = process.wait(timeout=2)
            echo = b"TEST_ECHO_ENABLED=1" in output
            return result, output.decode(errors="replace"), echo
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
            os.close(slave)
