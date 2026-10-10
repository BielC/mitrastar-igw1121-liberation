# MitraStar IGW-1121 Liberation

Restore O2 Spain SIM connectivity on the **Movistar MitraStar IGW-1121GX2X2-Mv3**
when web PIN entry fails or the router shows a domicile-lock warning.

On the tested firmware, web PIN entry incorrectly invokes PUK recovery. These
scripts verify the known PIN through the router's native modem utility and
repeat that step at boot. Both tested SIMs connected afterward; a permanent
carrier or location unlock has not been established.

[Guía en español](docs/es.md) · [Technical findings](docs/findings.md) ·
[Troubleshooting and removal](docs/troubleshooting.md)

## Compatibility

Tested on the black GX2X2-Mv3, hardware **1.0**, firmware
**`GL_g1.0_100AVK0_b2`**, running OpenWrt 21.02.7 (aarch64).
**Other firmware and the GX4X4 are untested.** No firmware flash is required.

The runtime and init service passed a real reboot and internet checks. The
installer and enrollment helper have simulated-router tests only.

## Setup

1. Test the SIM in a phone, **enable PIN protection**, and confirm its current
   PIN. Do not guess: this firmware locks its connection manager when protection
   is disabled. Set the carrier APN in the router; tested O2 Spain settings:
   `telefonica.es`, PAP, username/password `telefonica`.
2. Connect by Ethernet. Keep a separate internet connection for the reboot.
   Confirm SSH access and the host fingerprint. On the tested router:
   `1234@192.168.8.1`, with root privileges and the web password from its label.
   Adjust the address or account below if yours differs.
3. Run on your **computer**:

   ```sh
   git clone https://github.com/BielC/mitrastar-igw1121-liberation.git
   cd mitrastar-igw1121-liberation
   tar -C router -cf - install.sh sim-pin-unlock enroll-sim-pin zzz_sim_pin_unlock |
     ssh 1234@192.168.8.1 'umask 077; mkdir /tmp/igw1121-pin-fix && tar -xf - -C /tmp/igw1121-pin-fix'
   ssh -t 1234@192.168.8.1 '/bin/sh /tmp/igw1121-pin-fix/install.sh'
   ```

   Enter the known PIN twice at the hidden prompt. The installer saves it with
   the inserted SIM's ICCID and enables startup; it does not verify the PIN or
   restart the router. If an earlier upload exists, see the removal guide before
   retrying.
4. Reboot once, then run inside **router SSH**:

   ```sh
   cat /tmp/sim-pin-unlock/status
   mipc_wan_cli --show_register_status
   cmctl get apnInfo 1
   ```

   Expect `PIN accepted; SIM is ready.` or an already-ready message.
   `apnConnStatus: 1` confirms a data session; check internet access separately.
   To handle a pending PIN before rebooting, run `/usr/sbin/sim-pin-unlock` in SSH.

## Replacing the SIM

Enable protection and confirm the new card's PIN on a phone. Insert it, then
run from your computer:

```sh
ssh -t 1234@192.168.8.1 /usr/sbin/enroll-sim-pin
```

Reboot afterward. **Re-enroll even if the PIN is unchanged:** the script matches
ICCID and stores one card at a time. Previous enrollment is preserved privately.

## Safeguards and privacy

The script acts only on the enrolled SIM in PIN-required state, with **at most
one attempt per boot**. Failed or unconfirmed attempts block future automatic
attempts. It skips ready/PUK states and preserves the final PIN attempt when the
vendor counter is available. It never sends PUKs or changes PIN protection,
APN, networking, or firmware.

The PIN is stored **in plaintext in root-only router files** and briefly passed
to the native utility as a process argument. Privileged processes and vendor
logs may expose it. Do not publish raw logs, backups, credentials, or SIM/device
identifiers. Firmware updates and factory resets may remove the setup.

See [troubleshooting and removal](docs/troubleshooting.md) for failures,
disabling the service, or uninstalling. [Contributing](CONTRIBUTING.md) covers
safe reports and development checks. Original scripts and documentation are
[MIT licensed](LICENSE); vendor firmware and binaries are not included.
