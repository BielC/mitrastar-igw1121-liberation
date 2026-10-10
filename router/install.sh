#!/bin/sh
# Install only this project's files. Do not restart any service or network.
set -eu
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
SOURCE=$(CDPATH= cd "$(dirname "$0")" && pwd)
created=0

cleanup() {
    result=$?
    trap - EXIT
    if [ "$result" -ne 0 ] && [ "$created" = 1 ]; then
        /etc/init.d/zzz_sim_pin_unlock disable 2>/dev/null || :
        rm -f /etc/rc.d/S99zzz_sim_pin_unlock /etc/init.d/zzz_sim_pin_unlock
        rm -f /usr/sbin/sim-pin-unlock /usr/sbin/enroll-sim-pin
        rm -rf /etc/sim-pin-unlock
        printf '%s\n' 'New installation rolled back; existing vendor files were untouched.' >&2
    fi
    exit "$result"
}

[ "$(id -u)" = 0 ] || { printf '%s\n' 'Run this on the router as root.' >&2; exit 1; }
for file in /usr/bin/mipc_wan_cli /usr/bin/timeout /etc/rc.common /lib/functions/procd.sh; do
    [ -f "$file" ] || { printf 'Required router file is missing: %s\n' "$file" >&2; exit 1; }
done
for file in /etc/sim-pin-unlock /usr/sbin/sim-pin-unlock /usr/sbin/enroll-sim-pin /etc/init.d/zzz_sim_pin_unlock /etc/rc.d/S99zzz_sim_pin_unlock; do
    if [ -e "$file" ] || [ -L "$file" ]; then
        printf '%s\n' 'A previous setup exists; refusing to overwrite it. Use enroll-sim-pin for SIM replacement.' >&2
        exit 1
    fi
done
for name in sim-pin-unlock enroll-sim-pin zzz_sim_pin_unlock; do
    [ -f "$SOURCE/$name" ]
    /bin/sh -n "$SOURCE/$name"
done
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
created=1
cp "$SOURCE/sim-pin-unlock" /usr/sbin/sim-pin-unlock
cp "$SOURCE/enroll-sim-pin" /usr/sbin/enroll-sim-pin
cp "$SOURCE/zzz_sim_pin_unlock" /etc/init.d/zzz_sim_pin_unlock
chmod 700 /usr/sbin/sim-pin-unlock /usr/sbin/enroll-sim-pin /etc/init.d/zzz_sim_pin_unlock
/usr/sbin/enroll-sim-pin
/etc/init.d/zzz_sim_pin_unlock enable
/etc/init.d/zzz_sim_pin_unlock enabled
sync
printf '%s\n' 'Installed and enabled. No service, network, or router was restarted.'
printf '%s\n' 'Reboot only when a brief router outage is acceptable and you have a backup connection.'
