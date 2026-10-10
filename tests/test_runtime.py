from pathlib import Path
import tempfile
import unittest
from support import ICCID, OTHER_ICCID, PIN, Router


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fake-router-")
        self.addCleanup(self.temp.cleanup)
        self.router = Router(Path(self.temp.name))

    def test_ready_states_never_submit(self):
        for state in ["MIPC_SIM_STATUS_READY", "MIPC_SIM_STATUS_COMPLETE_READY"]:
            with self.subTest(state=state):
                self.router.write("state", state)
                self.assertEqual(self.router.run().returncode, 0)
                self.assertEqual(self.router.calls(), 0)

    def test_success_is_once_per_boot_and_clears_pending(self):
        self.assertEqual(self.router.run().returncode, 0)
        self.assertEqual(self.router.calls(), 1)
        self.assertFalse((self.router.config / "verification.pending").exists())
        self.router.write("state", "MIPC_SIM_STATUS_SIM_PIN")
        self.assertEqual(self.router.run().returncode, 0)
        self.assertEqual(self.router.calls(), 1)
        self.assertNotIn(PIN, (self.router.root / "log").read_text())
        self.assertNotIn(ICCID, (self.router.root / "runtime/status").read_text())

    def test_failure_survives_simulated_reboot(self):
        self.router.write("result", "fail")
        self.assertEqual(self.router.run().returncode, 1)
        self.assertEqual(self.router.calls(), 1)
        self.assertEqual(self.router.run().returncode, 0)
        (self.router.root / "runtime/attempted").unlink()
        self.assertEqual(self.router.run().returncode, 1)
        self.assertEqual(self.router.calls(), 1)

    def test_puk_result_stops_all_future_attempts(self):
        self.router.write("result", "puk")
        self.assertEqual(self.router.run().returncode, 1)
        self.assertTrue((self.router.config / "verification.pending").exists())
        self.assertEqual(self.router.calls(), 1)

    def test_identity_mismatch_unavailable_and_malformed(self):
        for identity in [OTHER_ICCID, "", "invalid"]:
            with self.subTest(identity=identity):
                self.router.write("identity", identity)
                self.assertEqual(self.router.run().returncode, 1)
                self.assertEqual(self.router.calls(), 0)

    def test_non_pin_states_never_submit(self):
        for state in ["MIPC_SIM_STATUS_SIM_PUK", "MIPC_SIM_STATUS_BLOCKED",
                      "MIPC_SIM_STATUS_NOT_INSERT", "unknown"]:
            with self.subTest(state=state):
                self.router.write("state", state)
                self.assertEqual(self.router.run().returncode, 1)
                self.assertEqual(self.router.calls(), 0)

    def test_preserves_last_attempt(self):
        self.router.write("sim-info", "DEVST_SIM_PIN 1 10 1\n")
        self.assertEqual(self.router.run().returncode, 1)
        self.assertEqual(self.router.calls(), 0)

    def test_unconfirmed_previous_attempt_stops(self):
        (self.router.config / "verification.pending").touch()
        self.assertEqual(self.router.run().returncode, 1)
        self.assertEqual(self.router.calls(), 0)

    def test_concurrent_invocation_stops(self):
        (self.router.root / "runtime/lock").mkdir(parents=True)
        self.assertEqual(self.router.run().returncode, 0)
        self.assertEqual(self.router.calls(), 0)

    def test_rechecks_state_after_identity_read(self):
        self.router.write("change-state", "MIPC_SIM_STATUS_SIM_PUK")
        self.assertEqual(self.router.run().returncode, 1)
        self.assertEqual(self.router.calls(), 0)
