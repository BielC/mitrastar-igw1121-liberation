from pathlib import Path
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from support import ROOT, Router


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fake-install-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.router = Router(self.root)
        self.target = self.root / "installed"
        self.target.mkdir()
        (self.root / "rc.common").touch()
        (self.root / "procd.sh").touch()
        (self.root / "vendor-startup").write_text("existing vendor file\n")
        (self.root / "sim-pin-unlock").write_text((ROOT / "router/sim-pin-unlock").read_text())
        self.router.executable("enroll-sim-pin", '''
[ "$(cat "$TEST_ROOT/result")" != fail ] || exit 1
mkdir -p "$TEST_ROOT/config"
chmod 700 "$TEST_ROOT/config"
''')
        self.router.executable("zzz_sim_pin_unlock", '''
echo "$1" >> "$TEST_ROOT/service-actions"
case "$1" in
 enable) ln -s "$TEST_TARGET/service" "$TEST_TARGET/boot-link";;
 enabled) test -L "$TEST_TARGET/boot-link";;
 disable) rm -f "$TEST_TARGET/boot-link";;
 *) exit 9;;
esac
''')
        source = (ROOT / "router/install.sh").read_text()
        replacements = {
            "PATH=/usr/sbin:/usr/bin:/sbin:/bin": f"PATH={self.router.bin}:/usr/bin:/bin:/usr/sbin:/sbin",
            "/usr/bin/mipc_wan_cli": str(self.router.cli),
            "/usr/bin/timeout": str(self.router.timeout),
            "/etc/rc.common": str(self.root / "rc.common"),
            "/lib/functions/procd.sh": str(self.root / "procd.sh"),
            "/etc/sim-pin-unlock": str(self.router.config),
            "/usr/sbin/sim-pin-unlock": str(self.target / "runtime"),
            "/usr/sbin/enroll-sim-pin": str(self.target / "enroll"),
            "/etc/init.d/zzz_sim_pin_unlock": str(self.target / "service"),
            "/etc/rc.d/S99zzz_sim_pin_unlock": str(self.target / "boot-link"),
        }
        for before, after in replacements.items():
            source = source.replace(before, after)
        self.script = self.root / "install.test"
        self.script.write_text(source)

    def run_installer(self):
        return subprocess.run(["/bin/sh", str(self.script)], capture_output=True, timeout=8,
                              env=dict(os.environ, TEST_ROOT=str(self.root), TEST_TARGET=str(self.target)))

    def test_refuses_existing_setup_without_touching_it(self):
        original = (self.router.config / "pin").read_bytes()
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertEqual((self.router.config / "pin").read_bytes(), original)
        self.assertFalse((self.target / "runtime").exists())
        self.assertEqual(self.router.calls(), 0)

    def test_success_enables_only_and_does_not_restart(self):
        shutil.rmtree(self.router.config)
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual((self.root / "service-actions").read_text().splitlines(), ["enable", "enabled"])
        for name in ["runtime", "enroll", "service"]:
            self.assertEqual(stat.S_IMODE((self.target / name).stat().st_mode), 0o700)
        self.assertEqual((self.root / "vendor-startup").read_text(), "existing vendor file\n")
        self.assertEqual(self.router.calls(), 0)

    def test_failed_enrollment_rolls_back_only_new_installation(self):
        shutil.rmtree(self.router.config)
        self.router.write("result", "fail")
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        for name in ["runtime", "enroll", "service", "boot-link"]:
            self.assertFalse((self.target / name).exists())
        self.assertFalse(self.router.config.exists())
        self.assertEqual((self.root / "vendor-startup").read_text(), "existing vendor file\n")
        self.assertEqual(self.router.calls(), 0)
