from pathlib import Path
import stat
import tempfile
import unittest
from support import ICCID, OTHER_ICCID, PIN, Router


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fake-profile-")
        self.addCleanup(self.temp.cleanup)
        self.router = Router(Path(self.temp.name))
        self.profile = self.router.config / "profiles" / "digi1"

    def enroll(self):
        return self.router.terminal(arguments=("digi1",))

    def test_new_profile_reads_identity_and_hides_pin(self):
        result, output, echo = self.enroll()
        self.assertEqual(result, 0, output)
        self.assertTrue(echo)
        self.assertNotIn(PIN, output)
        self.assertNotIn(ICCID, output)
        self.assertEqual((self.profile / "pin").read_text().strip(), PIN)
        self.assertEqual((self.profile / "iccid").read_text().strip(), ICCID)
        for directory in (self.profile, self.profile.parent):
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
        for name in ("pin", "iccid"):
            self.assertEqual(stat.S_IMODE((self.profile / name).stat().st_mode), 0o600)
        self.assertEqual(self.router.calls(), 0)

    def test_saved_profile_activates_without_a_terminal_or_modem_write(self):
        self.assertEqual(self.enroll()[0], 0)
        (self.router.config / "pin").write_text("1" * 4 + "\n")
        result = self.router.run("enroll-sim-pin", arguments=("digi1",))
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual((self.router.config / "pin").read_text().strip(), PIN)
        self.assertNotIn(PIN.encode(), result.stdout + result.stderr)
        self.assertNotIn(b"Known working", result.stdout)
        self.assertEqual(self.router.calls(), 0)

    def test_another_card_is_refused_even_when_pin_matches(self):
        self.assertEqual(self.enroll()[0], 0)
        self.router.write("identity", OTHER_ICCID)
        result = self.router.run("enroll-sim-pin", arguments=("digi1",))
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"another SIM", result.stderr)
        self.assertEqual((self.router.config / "iccid").read_text().strip(), ICCID)
        self.assertEqual(self.router.calls(), 0)

    def test_saved_profile_respects_failure_and_attempt_guards(self):
        self.assertEqual(self.enroll()[0], 0)
        attempted = self.router.root / "runtime" / "attempted"
        attempted.touch()
        self.assertEqual(self.router.run("enroll-sim-pin", arguments=("digi1",)).returncode, 0)
        self.assertTrue(attempted.exists())
        (self.router.config / "verification.pending").touch()
        result = self.router.run("enroll-sim-pin", arguments=("digi1",))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.router.calls(), 0)

    def test_profile_publish_failure_keeps_persistent_guard(self):
        self.router.executable("bin/mv", '''case "$2" in
 */profiles/*) exit 1;;
 *) exec /bin/mv "$@";;
esac''')
        self.assertEqual(self.enroll()[0], 1)
        self.assertTrue((self.router.config / "verification.pending").exists())
        self.assertEqual(self.router.run().returncode, 1)
        self.assertFalse(self.profile.exists())
        self.assertEqual(self.router.calls(), 0)

    def test_path_traversal_and_linked_profiles_are_refused(self):
        for name in ("../outside", "a/b", "x';exit", "-x", "_x", "x" * 49):
            with self.subTest(name=name):
                result = self.router.run("enroll-sim-pin", arguments=(name,))
                self.assertEqual(result.returncode, 1)
                self.assertEqual(self.router.calls(), 0)
        (self.router.config / "profiles").symlink_to(self.router.root)
        result = self.router.run("enroll-sim-pin", arguments=("digi1",))
        self.assertEqual(result.returncode, 1)
