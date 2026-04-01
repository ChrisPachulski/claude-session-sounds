"""
Claude Code status line script -- shows the current session's sound name.

Configured in ~/.claude/settings.json as:
    "statusLine": "python /path/to/status_line.py"

Receives session context on stdin (JSON with session_id), outputs the
sound name for display in Claude's status bar.
"""
import json
import sys
from pathlib import Path

ASSIGNMENTS_DIR = Path.home() / ".claude" / "sounds" / "assignments"

try:
    raw = sys.stdin.read()
    data = json.loads(raw) if raw.strip() else {}
except (json.JSONDecodeError, EOFError, ValueError):
    data = {}

session_id = data.get("session_id", "")
if session_id:
    assignment_file = ASSIGNMENTS_DIR / f"{session_id}.json"
    if assignment_file.is_file():
        try:
            choice = json.loads(assignment_file.read_text())
            name = choice.get("name", "")
            if name:
                print(f"[{name}]")
        except (json.JSONDecodeError, OSError):
            pass
