# Findings on the tested firmware

These observations come from one Movistar IGW-1121GX2X2-Mv3 with firmware
`GL_g1.0_100AVK0_b2`. Addresses below identify locations in that build and may
change in other releases. Conclusions about other models remain unverified.

## Web PIN entry takes the wrong path

The cellular web CGI stores the entered PIN and sets the USIM state to
`PINNING`. In the actual `libbemodules.so`, `beCellIntfUsim` compares the country
code at 0x4e2d4. Spain, 0xD5, branches to 0x4e350, where the backend generates a
PIN from ICCID and calls `EnterPUKCode` instead of ordinary `EnterPINCode`.

One web submission produced `MIPC_SIM_UNBLOCK_PIN_REQ FAIL,result:2`, without
changing the observed retry counters. One subsequent native `sim_verify_pin`
request with the known correct PIN succeeded. Do not interpret unchanged
counters in that test as assurance that web retries are safe on every build.

The installed utility exposes these useful operations:

```sh
mipc_wan_cli --show_sim_status
mipc_wan_cli --sim_pin_info_get
mipc_wan_cli --show_register_status
mipc_wan_cli --at_cmd 'AT+CCID'
```

Direct verification uses `--sim_verify_pin` with the actual current PIN.
The provided script reads it privately instead of putting a literal PIN in
shell history, and submits it only after status/identity checks.

## Disabled PIN protection triggers a connection-manager lock

The replacement SIM was already unlocked but reported `+CLCK: 0` when queried
with `AT+CLCK="SC",2`. It had no network registration or data session despite
an enabled radio and strong signal.

In the actual `cm` binary, the protection field is checked at 0x4061d4. The
zero case branches at 0x4061d8 to 0x4065e0, logs `No PIN Protection, Go LOCK
State`, and changes connection-manager state. The branch also clears an
internal flag at 0x40664c. This supports the observed need to reinitialize the
manager after turning protection on, rather than expecting a running locked
manager to recover immediately.

Enabling protection with the known correct PIN succeeded and retained three
PIN attempts. Updating enrollment and rebooting once then let the startup
service verify the PIN and restore registration/data. The public guide enables
protection on a phone first; the automation itself never changes protection.

## The location warning was not conclusive

The interface displayed a fixed-radio/location warning while
`/data/ES_CELL_LOCK_HASPERMITCELL` was zero. After successful SIM initialization
and automatic scanning, that field became 1 and the router established a data
session. Editing the flag was unnecessary and would not establish permission
or unlock a network restriction.

The first O2 Spain SIM connected to Movistar NR5G-SA. The replacement connected
to Movistar NR5G-NSA. Both had successful internet tests from the router. No
firmware flash or persistent carrier-lock patch was needed for those tests.

## Boot automation was tested

The standalone init service runs after the vendor's START=99 initialization,
using the `zzz_sim_pin_unlock` name for ordering. It leaves all vendor startup
files alone. During a real reboot, the script read ICCID while the SIM was
PIN-locked, submitted once, confirmed readiness, and cleared its persistent
guard. Mobile registration and the data session followed.

The root filesystem used a persistent writable overlay; `/tmp` was volatile.
This is why configuration and the failure guard survive ordinary boots while
the per-boot lock/attempt marker do not. An update or reset may remove custom
files.

## What is not established

- General compatibility with other firmware, other carriers, or the GX4X4.
- A permanent carrier or location unlock.
- Full firmware-image compatibility, a safe cross-flash, or a recovery image.
- Internet access merely because PIN verification or registration succeeded.

This repository contains original code and sanitized explanations, not the
private captures, configuration exports, vendor binaries, or disassembly files.
