# MitraStar IGW-1121 SIM PIN fix

Restore SIM connectivity on a **Movistar MitraStar IGW-1121GX2X2-Mv3** when
the SIM works in a phone but the router cannot unlock it through its web panel.
Includes the native PIN workaround, guarded startup automation, and a guide
for replacing the SIM.

[Guía en español](docs/es.md) · [Technical findings](docs/findings.md) ·
[Troubleshooting and removal](docs/troubleshooting.md)

## What worked

On the tested Spanish firmware, the web PIN flow invokes PUK recovery rather
than ordinary PIN verification. The modem's native utility can verify the
known correct PIN directly. We restored data with an O2 Spain SIM on Movistar
5G SA, then with a replacement SIM on Movistar 5G NSA.

Two details matter:

- **SIM PIN protection must be enabled.** Having a PIN assigned is different
  from requiring it at startup. The firmware explicitly puts a SIM with
  protection disabled into its connection-manager LOCK state.
- **A replacement SIM needs new enrollment.** The startup script checks the
  ICCID before trying the saved PIN, even if both cards use the same PIN.

This project uses tools already installed on the router. It does not provide
firmware, a carrier-unlock patch, or a way to bypass a genuine network or
contractual restriction. A location warning alone did not establish a permanent
lock in our tests: it cleared after successful SIM initialization.

## Tested device

| Item | Tested value |
| --- | --- |
| Model | IGW-1121GX2X2-Mv3, black Movistar unit |
| Hardware | 1.0 |
| Firmware | `GL_g1.0_100AVK0_b2` |
| OS | OpenWrt 21.02.7, aarch64 |
| Modem utility | `/usr/bin/mipc_wan_cli` |
| Startup | OpenWrt `rc.common` / procd |

**Other firmware versions and the GX4X4 have not been tested.** Do not flash a
different model's firmware to follow this guide.

## Setup

1. Test the SIM in a phone. Enable SIM PIN protection there and confirm its
   current PIN. Do not guess PINs or use a PUK unless the SIM actually requires
   one. Set the correct carrier APN in the router; for O2 Spain, the tested
   values are `telefonica.es`, PAP, username/password `telefonica`.
2. Connect your computer to the router by Ethernet. If you need continuous
   internet while testing, keep a separate Wi-Fi or hotspot connection as the
   computer's default route. The installer never switches your computer's network.
3. Confirm SSH access to your own router. The tested management address was
   `192.168.8.1`, username `1234`, and password the router's web password from
   its label. This account had UID 0. Verify the SSH host fingerprint; other
   firmware may use different access settings. No passwords or config backups
   are included in this repository.
4. On your **computer**, clone the repository and copy only the router scripts:

   ```sh
   git clone https://github.com/BielC/mitrastar-igw1121-sim-pin-fix.git
   cd mitrastar-igw1121-sim-pin-fix
   tar -C router -cf - install.sh sim-pin-unlock enroll-sim-pin zzz_sim_pin_unlock |
     ssh 1234@192.168.8.1 'umask 077; mkdir /tmp/igw1121-pin-fix && tar -xf - -C /tmp/igw1121-pin-fix'
   ssh -t 1234@192.168.8.1 '/bin/sh /tmp/igw1121-pin-fix/install.sh'
   ```

   The installer asks for the SIM PIN twice with terminal echo disabled. It
   reads the inserted card's ICCID locally and saves both in root-only files.
   **Enrollment does not verify that the entered PIN is correct.** Use the known
   working PIN from step 1. Enrollment submits no PIN and makes no modem changes.
   Upload refuses an existing staging directory; remove an earlier upload
   before retrying, as described in the removal guide.
5. The installer enables startup without restarting anything. If the router is
   currently waiting for its PIN, you can run the guarded script once in SSH:

   ```sh
   /usr/sbin/sim-pin-unlock
   cat /tmp/sim-pin-unlock/status
   ```

6. When a brief outage is acceptable, reboot the router once with a backup
   internet connection available. Reconnect by SSH and check:

   ```sh
   cat /tmp/sim-pin-unlock/status
   mipc_wan_cli --show_sim_status
   mipc_wan_cli --show_register_status
   cmctl get networkSearchInfo
   cmctl get apnInfo 1
   ```

   Successful startup reports `PIN accepted; SIM is ready.` A SIM that is
   already unlocked reports `SIM is already ready; no PIN was submitted.`
   Registration and the data session can take additional time. `apnConnStatus: 1`
   confirms an active session; PIN acceptance alone does not prove internet access.

The runtime script and init service were tested on the device, including a real
reboot and internet ping/DNS/HTTP checks. The public installer and enrollment
helper are new packaging, checked with isolated simulated-router tests; they
have not been installed on a second physical router.

## How startup protects the SIM

The script waits up to five minutes for initialization and acts only on the
exact `MIPC_SIM_STATUS_SIM_PIN` state with the enrolled ICCID. It skips ready
cards, mismatched identities, and PUK/recovery states. It preserves the final
PIN attempt when the vendor counter is available.

An atomic runtime lock and attempt marker allow **at most one submission per
boot**. A persistent stop guard is written before submission and cleared only
after confirmed readiness. Failure or interruption blocks automatic attempts
on future boots until reviewed. The service never respawns and never sends a
PUK, changes PIN protection, changes the APN, restarts networking, or flashes
firmware. These protections apply to this script; the vendor's own automatic
PIN behavior is outside its control.

## Replacing the SIM

Enable PIN protection and confirm the replacement card's PIN on a phone first.
With that card inserted, re-enroll from your computer:

```sh
ssh -t 1234@192.168.8.1 /usr/sbin/enroll-sim-pin
```

The helper checks the current card, privately asks for its PIN, and preserves
the previous enrollment in root-only `.previous` files. It refuses an active
verification or an unresolved failure guard. It does not clear this boot's
attempt marker. Reboot once when convenient so the modem initializes with the
new card. The installed startup service continues to enroll one card at a time.

## Disable

Inside the router's SSH session:

```sh
/etc/init.d/zzz_sim_pin_unlock disable
/etc/init.d/zzz_sim_pin_unlock stop
```

This disables/stops only this project's service. See
[removal and recovery](docs/troubleshooting.md) for the exact files and guard
handling. Firmware updates or factory resets may remove the setup.

## Privacy and contributions

No real PIN, PUK, ICCID, IMSI, IMEI, router password, config backup, device
fingerprint, or raw log is included. The PIN is stored **in plaintext on the
router**, protected by directory mode 700 and file mode 600. The native utility
briefly receives it as a process argument; privileged processes can inspect
it, and vendor logging may expose private data. Do not publish raw diagnostics.

For an issue, share the model, firmware version, symbolic SIM/registration
states, and the custom service's sanitized status message. Remove identifiers,
passwords, and PINs from anything else. See [contributing](CONTRIBUTING.md).

```sh
python3 tools/check_shell_syntax.py
python3 tools/check_public_files.py
python3 -m unittest discover -s tests -v
```

MIT licensed for the original scripts and documentation in this project.
Vendor firmware and binaries are not redistributed.
