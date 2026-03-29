"""Background process that continuously re-emits an ANSI title escape sequence.

Runs alongside Claude to prevent the CLI from overwriting the custom
terminal tab title. Killed by the shell wrapper when Claude exits.

Works on any terminal emulator that supports OSC title sequences
(VS Code, iTerm2, Terminal.app, GNOME Terminal, etc.).
"""
import os
import sys
import time

title = os.environ.get("CLAUDE_SOUND_TITLE", "") or (
    sys.argv[1] if len(sys.argv) > 1 else ""
)
if not title:
    sys.exit(0)

while True:
    sys.stderr.write(f"\033]2;{title}\007")
    sys.stderr.flush()
    time.sleep(3)
