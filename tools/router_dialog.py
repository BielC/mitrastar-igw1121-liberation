"""Keep the terminal and hidden PIN input local; SSH must not allocate a PTY."""
import getpass
import os
import subprocess
import sys
import warnings


PROMPTS = {
    b"Carrier [1-4]: ": False,
    b"Custom APN: ": False,
    b"Data roaming [y/n]: ": False,
    b"Known working SIM PIN (hidden): ": True,
    b"Repeat PIN (hidden): ": True,
}


def run(command):
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    pending = b""
    hold = max(map(len, PROMPTS))

    def display(data):
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()

    try:
        while chunk := os.read(process.stdout.fileno(), 4096):
            pending += chunk
            for prompt, secret in PROMPTS.items():
                index = pending.find(prompt)
                if index < 0:
                    continue
                display(pending[:index])
                pending = pending[index + len(prompt):]
                if secret:
                    # Refuse getpass's plaintext fallback when no local terminal exists.
                    with warnings.catch_warnings():
                        warnings.simplefilter("error", getpass.GetPassWarning)
                        # getpass disables echo BEFORE showing the prompt. Showing
                        # it earlier lets fast input race with its terminal flush.
                        reply = getpass.getpass(prompt.decode())
                else:
                    display(prompt)
                    reply = input()
                process.stdin.write((reply + "\n").encode())
                process.stdin.flush()
                reply = ""
                break
            else:
                # Retain enough bytes to recognize a prompt split across reads.
                if len(pending) > hold:
                    display(pending[:-hold])
                    pending = pending[-hold:]
        display(pending)
        return process.wait()
    except (EOFError, KeyboardInterrupt, BrokenPipeError, getpass.GetPassWarning):
        print("\nSetup cancelled; no further answers were sent.", file=sys.stderr)
        return 1
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        process.stdin.close()
        process.stdout.close()


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
