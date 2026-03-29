"""
Per-session sound assignment manager for Claude Code hooks.

Called by hooks with JSON on stdin containing session_id:
    python sound_manager.py assign   # SessionStart: pick & assign sound
    python sound_manager.py play     # Stop: play the assigned sound
    python sound_manager.py release  # SessionEnd: free the assignment

Called directly by shell wrapper (no stdin):
    python sound_manager.py pick     # Pre-pick a sound for --name flag
"""
import json
import random
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SOUNDS_DIR = Path(__file__).parent
ASSIGNMENTS_DIR = SOUNDS_DIR / "assignments"
STALE_HOURS = 12

SOUND_POOL = [
    {"file": "mario_powerup.wav", "name": "Power-Up"},
    {"file": "scorpion.wav", "name": "Scorpion"},
    {"file": "pokeball.wav", "name": "Gotcha"},
    {"file": "tetris.wav", "name": "Tetris"},
    {"file": "r2d2.wav", "name": "R2-D2"},
    {"file": "minecraft.wav", "name": "Minecraft"},
    {"file": "pentakill.wav", "name": "Pentakill"},
    {"file": "lightsaber.wav", "name": "Lightsaber"},
    {"file": "civ.wav", "name": "New Era"},
    {"file": "mission.wav", "name": "Mission"},
    {"file": "bond.wav", "name": "007"},
    {"file": "shire.wav", "name": "The Shire"},
    {"file": "mohican.wav", "name": "Mohican"},
    {"file": "coolcat.wav", "name": "Cool Cat"},
    {"file": "mangione.wav", "name": "Feels So Good"},
    {"file": "abouttime.wav", "name": "About Time"},
    {"file": "creek.wav", "name": "Creek"},
]


def _cleanup_stale() -> None:
    """Remove assignment files older than STALE_HOURS."""
    if not ASSIGNMENTS_DIR.is_dir():
        return
    cutoff = time.time() - (STALE_HOURS * 3600)
    for f in ASSIGNMENTS_DIR.glob("*.json"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
        except OSError:
            pass


def _get_assigned_files() -> set[str]:
    """Return set of sound filenames currently assigned to active sessions."""
    assigned = set()
    if ASSIGNMENTS_DIR.is_dir():
        for f in ASSIGNMENTS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                assigned.add(data["file"])
            except Exception:
                pass
    return assigned


def _build_title(sound_name: str) -> str:
    """Build the session title string."""
    return sound_name


def _play_sound(wav_path: Path) -> None:
    """Play a WAV file using the platform's native audio player."""
    if sys.platform == "win32":
        cmd = [
            "powershell.exe", "-NoProfile", "-Command",
            f"(New-Object Media.SoundPlayer '{wav_path}').PlaySync()",
        ]
    elif sys.platform == "darwin":
        cmd = ["afplay", str(wav_path)]
    else:
        cmd = ["aplay", "-q", str(wav_path)]

    subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=10,
    )


def _find_sound_by_name(name: str) -> dict[str, str] | None:
    """Find a sound pool entry whose name matches (case-insensitive)."""
    for entry in SOUND_POOL:
        if entry["name"].lower() == name.lower():
            return entry
    return None


def pick() -> None:
    """Pick an available sound and output the title. Used by shell wrapper."""
    ASSIGNMENTS_DIR.mkdir(parents=True, exist_ok=True)
    _cleanup_stale()

    assigned = _get_assigned_files()
    available = [s for s in SOUND_POOL if s["file"] not in assigned]
    if not available:
        available = SOUND_POOL

    choice = random.choice(available)
    print(_build_title(choice["name"]))


def assign(session_id: str) -> None:
    """Assign a sound to this session, matching the --name from the wrapper."""
    ASSIGNMENTS_DIR.mkdir(parents=True, exist_ok=True)
    _cleanup_stale()

    existing = ASSIGNMENTS_DIR / f"{session_id}.json"
    if existing.is_file():
        choice = json.loads(existing.read_text())
    else:
        # Try to match the --name value from the session file
        choice = None
        try:
            import os
            sessions_dir = Path.home() / ".claude" / "sessions"
            session_file = sessions_dir / f"{os.getppid()}.json"
            if session_file.is_file():
                session_data = json.loads(session_file.read_text())
                name = session_data.get("name", "")
                if name:
                    choice = _find_sound_by_name(name)
        except Exception:
            pass

        if choice is None:
            assigned = _get_assigned_files()
            available = [s for s in SOUND_POOL if s["file"] not in assigned]
            if not available:
                return
            choice = random.choice(available)

        existing.write_text(json.dumps(choice))

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                f"This session's sound is '{choice['name']}'. "
                f"Do not mention the session name or sound assignment to the user."
            )
        }
    }))


def play(session_id: str) -> None:
    """Play the assigned sound for this session."""
    assignment_file = ASSIGNMENTS_DIR / f"{session_id}.json"
    if not assignment_file.is_file():
        return

    choice = json.loads(assignment_file.read_text())
    wav_path = SOUNDS_DIR / choice["file"]
    if wav_path.is_file():
        _play_sound(wav_path)
        print(json.dumps({"systemMessage": f"{choice['name']}!"}))


def release(session_id: str) -> None:
    """Free the sound assignment when the session ends."""
    assignment_file = ASSIGNMENTS_DIR / f"{session_id}.json"
    try:
        assignment_file.unlink(missing_ok=True)
    except OSError:
        pass


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""

    if action == "pick":
        pick()
    else:
        try:
            stdin_data = json.loads(sys.stdin.read())
        except (json.JSONDecodeError, EOFError):
            stdin_data = {}
        session_id = stdin_data.get("session_id", "unknown")

        if action == "assign":
            assign(session_id)
        elif action == "play":
            play(session_id)
        elif action == "release":
            release(session_id)
