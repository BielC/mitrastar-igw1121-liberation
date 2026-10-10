from pathlib import Path
import stat
import tempfile
import unittest
from support import ICCID, OTHER_ICCID, PIN, Router


class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fake-enrollment-")
        self.addCleanup(self.temp.cleanup)
        self.router = Router(Path(self.temp.name))

    def test_hidden_input_private_files_and_no_modem_write(self):
        result, output, echo = self.router.terminal()
        self.assertEqual(result, 0, output)
        self.assertTrue(echo)
        self.assertNotIn(PIN, output)
        self.assertNotIn(ICCID, output)
        self.assertEqual(self.router.calls(), 0)
        for name in ["pin", "iccid", "pin.previous", "iccid.previous"]:
            self.assertEqual(stat.S_IMODE((self.router.config / name).stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.router.config.stat().st_mode), 0o700)
        self.assertFalse((self.router.config / "verification.pending").exists())

    def test_mismatch_restores_echo_without_changing_enrollment(self):
        result, output, echo = self.router.terminal(entries=(PIN, "1" * 4))
        self.assertEqual(result, 1)
        self.assertTrue(echo)
        self.assertNotIn(PIN, output)
        self.assertEqual((self.router.config / "pin").read_text().strip(), PIN)
        self.assertEqual(self.router.calls(), 0)

    def test_ready_card_with_protection_disabled_is_refused(self):
        self.router.write("state", "MIPC_SIM_STATUS_COMPLETE_READY")
        self.router.write("protection", "0")
        result, output, _ = self.router.terminal()
        self.assertEqual(result, 1)
        self.assertIn("Enable SIM PIN protection", output)
        self.assertEqual(self.router.calls(), 0)

    def test_puk_and_failure_guard_are_refused_before_input(self):
        self.router.write("state", "MIPC_SIM_STATUS_SIM_PUK")
        result, _, _ = self.router.terminal()
        self.assertEqual(result, 1)
        self.router.write("state", "MIPC_SIM_STATUS_SIM_PIN")
        (self.router.config / "verification.pending").touch()
        result, output, _ = self.router.terminal()
        self.assertEqual(result, 1)
        self.assertNotIn("Known working SIM PIN", output)

    def test_sim_change_during_input_preserves_previous_enrollment(self):
        self.router.write("change-identity", OTHER_ICCID)
        result, output, echo = self.router.terminal()
        self.assertEqual(result, 1)
        self.assertTrue(echo)
        self.assertIn("SIM changed", output)
        self.assertEqual((self.router.config / "iccid").read_text().strip(), ICCID)

    def test_interrupted_pair_update_leaves_persistent_stop_guard(self):
        self.router.executable("bin/mv", '''case "$2" in
 */iccid) exit 1;;
 *) exec /bin/mv "$@";;
esac''')
        result, _, echo = self.router.terminal()
        self.assertEqual(result, 1)
        self.assertTrue(echo)
        self.assertTrue((self.router.config / "verification.pending").exists())
        self.assertEqual(self.router.run().returncode, 1)
        self.assertEqual(self.router.calls(), 0)
