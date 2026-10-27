from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest
from support import ROOT


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fake-cli-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fake = self.bin / "ssh"
        fake.write_text('''#!/usr/bin/env python3
import json, os, pathlib, socket, sys
root = pathlib.Path(os.environ['TEST_ROOT'])
args = sys.argv[1:]
with (root / 'calls').open('a') as out:
    out.write(json.dumps(args) + '\\n')
control = next(value.split('=', 1)[1] for value in args if value.startswith('ControlPath='))
if '-O' in args:
    sys.exit(0)
if '-t' in args or '-tt' in args or '-T' not in args:
    print('> restricted vendor console', flush=True)
    sys.exit(55)
command = args[-1]
if 'mktemp -d' in command:
    sock = socket.socket(socket.AF_UNIX)
    sock.bind(control)
    print(os.environ.get('STAGING', '/tmp/router-cli.testABC'))
elif command.startswith('cat >'):
    name = 'profile-upload' if 'select-sim-profile' in command else 'upload'
    (root / name).write_bytes(sys.stdin.buffer.read())
    sys.exit(int(os.environ.get('UPLOAD_EXIT', '0')))
elif command.startswith('rm -rf'):
    pass
else:
    (root / 'activation').write_text(command)
    sys.exit(int(os.environ.get('ACTIVATE_EXIT', '0')))
''')
        fake.chmod(0o700)

    def run_cli(self, *arguments, **extra):
        return subprocess.run(
            ['/bin/sh', str(ROOT / 'router-cli'), *arguments],
            capture_output=True, timeout=8,
            env=dict(os.environ, PATH=str(self.bin) + ':' + os.environ['PATH'],
                     TMPDIR=str(self.root), TEST_ROOT=str(self.root), **extra))

    def calls(self):
        path = self.root / 'calls'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_uses_shell_commands_without_opening_restricted_vendor_console(self):
        result = self.run_cli('digi1', '1234@router.local')
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual((self.root / 'upload').read_bytes(), (ROOT / 'router/enroll-sim-pin').read_bytes())
        self.assertEqual((self.root / 'profile-upload').read_bytes(), (ROOT / 'router/select-sim-profile').read_bytes())
        activation = (self.root / 'activation').read_text()
        self.assertIn("'digi1'", activation)
        self.assertIn('select-sim-profile', activation)
        self.assertNotRegex(activation, r'(?m)^\s*(?:/sbin/)?reboot\b')
        self.assertNotIn('cmctl send', activation)
        self.assertTrue(activation.startswith('/bin/sh '))
        self.assertNotIn('\n', activation)
        self.assertTrue(all('-T' in call for call in self.calls() if '-O' not in call))
        self.assertTrue(any('1234@router.local' in call for call in self.calls()))
        self.assertTrue(any('-O' in call and 'exit' in call for call in self.calls()))

    def test_upload_failure_never_activates_profile(self):
        result = self.run_cli('digi1', UPLOAD_EXIT='7')
        self.assertEqual(result.returncode, 7)
        self.assertFalse((self.root / 'activation').exists())
        self.assertTrue(any(call[-1].startswith('rm -rf') for call in self.calls()))

    def test_activation_failure_reaches_the_caller(self):
        self.assertEqual(self.run_cli('digi1', ACTIVATE_EXIT='9').returncode, 9)

    def test_untrusted_staging_path_is_never_used_for_upload_or_cleanup(self):
        result = self.run_cli('digi1', STAGING="/tmp/router-cli.bad'; exit 0; '")
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.root / 'upload').exists())
        self.assertFalse(any(call[-1].startswith('rm -rf') for call in self.calls()))

    def test_invalid_names_and_ssh_targets_are_rejected_before_connecting(self):
        for arguments in ((), ('../x',), ('x;echo',), ('-x',), ('x' * 49,), ('digi1', '-oProxyCommand=x')):
            with self.subTest(arguments=arguments):
                self.assertEqual(self.run_cli(*arguments).returncode, 1)
                self.assertEqual(self.calls(), [])
