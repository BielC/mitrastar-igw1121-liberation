# Contributing

Reports from the exact tested model and other firmware are welcome. Include
model, hardware/firmware version, symbolic SIM state, registration state, and
whether PIN protection was enabled. State separately whether PIN verification,
registration, data session, and internet tests succeeded.

Do not attach raw logs, configuration exports, firmware binaries, screenshots
of labels, or SIM identifiers. The public-file check helps catch common
accidents; it cannot replace reviewing every file before publishing.

The runtime script must retain identity matching, one attempt per boot,
persistent failure blocking, bounded waits, and refusal of PUK recovery. Do
not add retry loops that submit additional PINs or bypass an unknown identity.
Keep credentials in root-only router files and out of arguments accepted by
the enrollment helper, examples, fixtures, and commit history.

Run:

```sh
python3 tools/check_shell_syntax.py
python3 tools/check_public_files.py
python3 -m unittest discover -s tests -v
pre-commit run --all-files
```

The runtime script and init service match the device-tested implementation.
Installer/enrollment changes need isolated failure/privacy tests, and hardware
testing must be identified separately from simulation. A successful unit test
does not establish compatibility with a different modem or firmware.

An optional GitHub Actions workflow is in
`.github/workflow-templates/checks.yml`. To activate it, copy it to
`.github/workflows/checks.yml` using the GitHub editor or credentials with
workflow write permission. It runs syntax, public-file checks, and the isolated
tests with read-only repository permission.
