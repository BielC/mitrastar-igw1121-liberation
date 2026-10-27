#!/bin/sh
# Return only the password saved for this SSH target. Never log it.
set -eu
case "${1-}" in
    *password:*|*Password:*)
        exec /usr/bin/security find-generic-password \
            -a "$ROUTER_CLI_SSH_TARGET" -s router-cli.ssh -w 2>/dev/null
        ;;
    *)
        # Host-key questions still require the user's own answer.
        printf '%s ' "${1-}" > /dev/tty
        IFS= read -r answer < /dev/tty
        printf '%s\n' "$answer"
        ;;
esac
