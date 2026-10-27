from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
from support import ROOT, ICCID, PIN, Router


class DialogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fake-dialog-")
        self.addCleanup(self.temp.cleanup)
        self.router = Router(Path(self.temp.name))

    def test_local_hidden_pin_prompts_work_without_a_remote_terminal(self):
        result, output, echo = self.router.terminal(
            arguments=("--stdin", "digi1"), apn_answers=("1",), dialog=True)
        self.assertEqual(result, 0, output)
        self.assertTrue(echo)
        self.assertNotIn(PIN, output)
        self.assertNotIn(ICCID, output)
        self.assertEqual((self.router.config / "profiles/digi1/pin").read_text().strip(), PIN)
        self.assertEqual((self.router.config / "profiles/digi1/apn").read_text().strip(), "internet.digimobil.es")
        self.assertEqual(self.router.calls(), 0)

    def test_private_input_mismatch_cancels_without_changing_enrollment(self):
        result, output, echo = self.router.terminal(
            arguments=("--stdin", "digi1"), entries=(PIN, "1" * 4), dialog=True)
        self.assertEqual(result, 1, output)
        self.assertTrue(echo)
        self.assertNotIn(PIN, output)
        self.assertEqual((self.router.config / "pin").read_text().strip(), PIN)
        self.assertFalse((self.router.config / "profiles/digi1").exists())

    def test_stdin_mode_accepts_a_pipe_and_never_echoes_the_pin(self):
        result = subprocess.run(
            ["/bin/sh", str(self.router.script("enroll-sim-pin")), "--stdin", "digi1"],
            input="1\n" + PIN + "\n" + PIN + "\n", text=True, capture_output=True, timeout=8,
            env=dict(os.environ, TEST_ROOT=str(self.router.root)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(PIN, result.stdout + result.stderr)
        self.assertEqual(self.router.calls(), 0)

    def test_closed_input_does_not_overwrite_any_saved_config(self):
        result = subprocess.run(
            ["/bin/sh", str(self.router.script("enroll-sim-pin")), "--stdin", "digi1"],
            input="1\n", text=True, capture_output=True, timeout=8,
            env=dict(os.environ, TEST_ROOT=str(self.router.root)))
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.router.config / "profiles/digi1").exists())
        self.assertEqual((self.router.config / "pin").read_text().strip(), PIN)

    def test_nonterminal_secret_prompt_refuses_plaintext_fallback(self):
        command = [sys.executable, "-c", "import sys; print('Known working SIM PIN (hidden): ', end='', flush=True); sys.stdin.readline()"]
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/router_dialog.py"), *command],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=8, start_new_session=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"Setup cancelled", result.stderr)

    def test_ssh_password_is_loaded_only_for_password_prompts(self):
        fake = self.router.executable("security", 'printf "%s\\n" "synthetic-password"')
        helper = self.router.root / "askpass.test"
        helper.write_text((ROOT / "tools/router_ssh_askpass.sh").read_text().replace("/usr/bin/security", str(fake)))
        result = subprocess.run(
            ["/bin/sh", str(helper), "1234@router.test's password: "],
            capture_output=True, text=True, timeout=8,
            env=dict(os.environ, ROUTER_CLI_SSH_TARGET="1234@router.test"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "synthetic-password")
