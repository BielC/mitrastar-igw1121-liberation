from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from support import ROOT, PIN, Router


class ProfileRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fake-profile-runner-")
        self.addCleanup(self.temp.cleanup)
        self.router = Router(Path(self.temp.name))
        helper = self.router.root / "enroll-sim-pin"
        helper.write_text(self.router.script("enroll-sim-pin").read_text())
        runtime = self.router.executable("runtime-script", self.router.script("sim-pin-unlock").read_text())
        service = self.router.executable("service", '''
case "$1" in
 enable|enabled) echo "$1" >> "$TEST_ROOT/service-actions";;
 *) exit 9;;
esac''')
        source = (ROOT / "router/select-sim-profile").read_text()
        for before, after in {
            "/usr/sbin/sim-pin-unlock": str(runtime),
            "/etc/init.d/zzz_sim_pin_unlock": str(service),
            "/usr/bin/mipc_wan_cli": str(self.router.cli),
            "/usr/bin/timeout": str(self.router.timeout),
            "/tmp/sim-pin-unlock/status": str(self.router.root / "runtime/status"),
        }.items():
            source = source.replace(before, after)
        self.runner = self.router.root / "runner"
        self.runner.write_text(source)

    def run_profile(self, entries="1\n" + PIN + "\n" + PIN + "\n"):
        return subprocess.run(
            ["/bin/sh", str(self.runner), "digi1"], input=entries,
            capture_output=True, text=True, timeout=8,
            env=dict(os.environ, TEST_ROOT=str(self.router.root)))

    def test_enrolls_and_unlocks_once_then_reuses_ready_profile(self):
        result = self.run_profile()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PIN accepted", result.stdout)
        self.assertNotIn(PIN, result.stdout + result.stderr)
        self.assertEqual(self.router.calls(), 1)
        result = self.run_profile(entries="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already ready", result.stdout)
        self.assertNotIn("already attempted", result.stdout)
        self.assertEqual(self.router.calls(), 1)

    def test_ready_sim_is_not_verified(self):
        self.router.write("state", "MIPC_SIM_STATUS_COMPLETE_READY")
        result = self.run_profile()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already ready", result.stdout)
        self.assertEqual(self.router.calls(), 0)
        self.assertEqual((self.router.root / "service-actions").read_text().splitlines(), ["enable", "enabled"])

    def test_incorrect_pin_keeps_guard_and_prevents_repeated_verification(self):
        self.router.write("result", "fail")
        result = self.run_profile()
        self.assertEqual(result.returncode, 1)
        self.assertTrue((self.router.config / "verification.pending").exists())
        self.assertEqual(self.router.calls(), 1)
        self.assertEqual(self.run_profile(entries="").returncode, 1)
        self.assertEqual(self.router.calls(), 1)
