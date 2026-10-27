# Troubleshooting and removal

Run router commands inside SSH as root. Keep a separate internet connection
when testing a reboot or changing anything that could interrupt the router.

## Status messages

```sh
cat /tmp/sim-pin-unlock/status
```

| Message / observation | Next action |
| --- | --- |
| Already ready | No PIN is needed; check registration and the data session. |
| PIN accepted | Check registration, then APN session and internet separately. |
| SIM identity differs | Re-enroll the inserted card with its known PIN. |
| Identity not ready before deadline | Do not bypass the identity check. Verify firmware, SIM insertion, and native ICCID query. |
| Previous verification unconfirmed | Review the persistent guard before any attempt. |
| Too few attempts / PUK / recovery | Use the carrier's actual recovery procedure. This project does not send PUKs. |
| SIM ready but no registration | Check PIN protection, signal, radio state, and carrier provisioning. An APN change alone cannot fix absent registration. |

The script's five-minute waiting deadline and short command timeouts bound the
startup process. Success clears only its own persistent guard. It does not
prove the mobile data session is active.

Useful read-only checks:

```sh
mipc_wan_cli --show_sim_status
mipc_wan_cli --show_register_status
mipc_wan_cli --nw_radio_state_get
mipc_wan_cli --at_cmd 'AT+CLCK="SC",2'
cmctl get networkSearchInfo
cmctl get apnInfo 1
```

`+CLCK: 0` means PIN protection is off; `+CLCK: 1` means it is on. Enable it on
a phone with the known correct PIN before booting this firmware with the SIM.
`apnConnStatus: 1` indicates an active data session. Confirm its actual interface
before testing internet; the observed interface was `ccmni2`:

```sh
ping -c 3 -W 3 -I ccmni2 1.1.1.1
wget -T 10 -O /dev/null http://connectivitycheck.gstatic.com/generate_204
```

These are router-side upstream tests. Client Wi-Fi/Ethernet, DHCP, or firewall
problems can still require separate investigation.

## An unresolved stop guard

The service refuses `/etc/sim-pin-unlock/verification.pending` across boots.
Enrollment also uses this guard while replacing the PIN/ICCID pair; an
interrupted enrollment intentionally leaves the service blocked.

Do not delete the guard to keep trying a guessed PIN. Disable the service,
confirm the actual PIN and retry state on a phone, and review the private
enrollment. After manual recovery, verify that the modem is READY or
COMPLETE_READY before clearing an old verification guard:

```sh
/etc/init.d/zzz_sim_pin_unlock disable
/etc/init.d/zzz_sim_pin_unlock stop
mipc_wan_cli --show_sim_status
```

Only after the card and enrollment have been reviewed:

```sh
rm -f /etc/sim-pin-unlock/verification.pending
```

If enrollment was interrupted, re-enroll the known working card before
re-enabling the service. Keep `/tmp/sim-pin-unlock/attempted` until the next
boot. Do not remove it to force additional attempts in the same boot.

## Restore the previous enrolled card

The public enrollment helper preserves both previous files. With the previous
card inserted and its PIN/protection confirmed, disable the service first and
check that no verification is running. Restore both files, not just the ICCID:

```sh
cp /etc/sim-pin-unlock/pin.previous /etc/sim-pin-unlock/pin
cp /etc/sim-pin-unlock/iccid.previous /etc/sim-pin-unlock/iccid
chmod 600 /etc/sim-pin-unlock/pin /etc/sim-pin-unlock/iccid
/etc/init.d/zzz_sim_pin_unlock enable
```

If unsure which backup belongs to which card, use the enrollment helper
instead. Do not restore old credentials to a different SIM.

## Disable or uninstall

```sh
/etc/init.d/zzz_sim_pin_unlock disable
/etc/init.d/zzz_sim_pin_unlock stop
```

This affects only the custom service. To remove it, including its saved secrets:

```sh
rm -f /etc/init.d/zzz_sim_pin_unlock /etc/rc.d/S99zzz_sim_pin_unlock
rm -f /usr/sbin/sim-pin-unlock /usr/sbin/enroll-sim-pin
rm -rf /etc/sim-pin-unlock /tmp/sim-pin-unlock
```

The uploaded copy in `/tmp/igw1121-pin-fix` contains only public scripts and can
also be removed. No vendor file needs restoring because none was overwritten.

## SIM profiles

Named profiles store their PIN/ICCID pairs in `/etc/sim-pin-unlock/profiles/NAME`.
The selected pair is copied into the existing active configuration. A name does
not identify the carrier or change the APN. Use a new name for another SIM or a
changed PIN; an existing profile is never silently overwritten. Profile selection
also refuses any unresolved failure guard and preserves the per-boot attempt marker.

## Sharing diagnostics

Share only symbolic states and the custom status message. Raw AT output,
`AT+CCID`, configuration XML, screenshots, vendor logs, and process arguments
can expose identities or credentials. Remove those details before posting.
