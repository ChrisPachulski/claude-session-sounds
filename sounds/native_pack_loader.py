"""
Platform-native sound pack loader.

Detects the current OS, loads the matching platform-native pack.json,
validates that sound files actually exist on disk, and returns a
filtered pool + event map ready for sound_manager consumption.

Usage:
    from native_pack_loader import load_native_pack

    pack = load_native_pack()
    if pack:
        pool = pack["pool"]       # list[dict] with {file, name}
        events = pack["events"]   # dict with completion/error/approval/startup
"""
from __future__ import annotations

import json
import logging
import shutil
import sys
from pathlib import Path
from typing import TypedDict

log = logging.getLogger("native_pack_loader")

PACKS_DIR = Path(__file__).parent / "packs"


# ---------------------------------------------------------------------------
# Type definitions
# ---------------------------------------------------------------------------

class SoundEntry(TypedDict):
    file: str
    name: str


class EventMap(TypedDict, total=False):
    completion: SoundEntry
    error: SoundEntry
    approval: SoundEntry
    startup: SoundEntry


class NativePack(TypedDict):
    name: str
    platform: str
    pool: list[SoundEntry]
    events: EventMap
    pool_missing: list[SoundEntry]
    events_missing: list[str]


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

def detect_platform() -> str:
    """Return normalized platform key: windows, darwin, or linux."""
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def _pack_dir_for_platform(platform: str) -> Path | None:
    """Find the platform-native pack directory."""
    candidates = {
        "windows": PACKS_DIR / "windows-native",
        "darwin": PACKS_DIR / "macos-native",
        "linux": PACKS_DIR / "linux-native",
    }
    pack_dir = candidates.get(platform)
    if pack_dir and (pack_dir / "pack.json").is_file():
        return pack_dir
    return None


# ---------------------------------------------------------------------------
# File existence validation
# ---------------------------------------------------------------------------

def _file_exists(path_str: str) -> bool:
    """Check whether a sound file exists on disk."""
    return Path(path_str).is_file()


def _validate_pool(raw_pool: list[dict]) -> tuple[list[SoundEntry], list[SoundEntry]]:
    """Split pool into (present, missing) based on file existence."""
    present: list[SoundEntry] = []
    missing: list[SoundEntry] = []
    for entry in raw_pool:
        if _file_exists(entry["file"]):
            present.append(SoundEntry(file=entry["file"], name=entry["name"]))
        else:
            missing.append(SoundEntry(file=entry["file"], name=entry["name"]))
    return present, missing


def _validate_events(raw_events: dict) -> tuple[EventMap, list[str]]:
    """Validate event sound files, returning (valid_events, missing_keys)."""
    valid: EventMap = {}
    missing_keys: list[str] = []
    for key in ("completion", "error", "approval", "startup"):
        entry = raw_events.get(key)
        if entry and _file_exists(entry["file"]):
            valid[key] = SoundEntry(file=entry["file"], name=entry["name"])
        elif entry:
            missing_keys.append(key)
    return valid, missing_keys


# ---------------------------------------------------------------------------
# Playback command detection (Linux needs special handling for .oga)
# ---------------------------------------------------------------------------

def detect_playback_command() -> list[str] | None:
    """Find a working audio playback command for the current platform.

    Returns the base command as a list (e.g. ["afplay"] or ["paplay"]),
    or None if no suitable player is found.
    """
    platform = detect_platform()

    if platform == "windows":
        # winsound module handles .wav natively -- no external command needed
        return ["winsound"]

    if platform == "darwin":
        # afplay ships with every macOS install, handles .aiff natively
        if shutil.which("afplay"):
            return ["afplay"]
        return None

    # Linux: .oga files need an Ogg-capable player
    for cmd in ("paplay", "pw-play", "ogg123", "ffplay", "aplay"):
        if shutil.which(cmd):
            if cmd == "ffplay":
                return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]
            if cmd == "ogg123":
                return ["ogg123", "-q"]
            return [cmd]
    return None


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------

def load_native_pack(platform: str | None = None) -> NativePack | None:
    """Load and validate the platform-native sound pack.

    Args:
        platform: Override auto-detection. One of windows, darwin, linux.

    Returns:
        NativePack dict with validated pool/events, or None if no pack found
        or pool is empty after validation.
    """
    if platform is None:
        platform = detect_platform()

    pack_dir = _pack_dir_for_platform(platform)
    if pack_dir is None:
        log.warning("No native pack found for platform: %s", platform)
        return None

    try:
        raw = json.loads((pack_dir / "pack.json").read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.error("Failed to load native pack: %s", exc)
        return None

    # Validate mode
    if raw.get("mode") != "platform-native":
        log.warning("Pack %s is mode=%s, not platform-native", pack_dir.name, raw.get("mode"))
        return None

    # Validate pool and events
    raw_pool = raw.get("pool", raw.get("sounds", []))
    pool_present, pool_missing = _validate_pool(raw_pool)
    events_valid, events_missing = _validate_events(raw.get("events", {}))

    if pool_missing:
        log.info(
            "Native pack %s: %d/%d pool sounds missing on this machine",
            raw.get("name", "unknown"), len(pool_missing), len(raw_pool),
        )
    if events_missing:
        log.info("Native pack %s: missing event sounds: %s", raw.get("name"), events_missing)

    if not pool_present:
        log.warning("Native pack %s: no pool sounds found on disk", raw.get("name"))
        return None

    return NativePack(
        name=raw.get("name", pack_dir.name),
        platform=platform,
        pool=pool_present,
        events=events_valid,
        pool_missing=pool_missing,
        events_missing=events_missing,
    )


def load_native_pack_as_legacy(platform: str | None = None) -> list[dict[str, str]] | None:
    """Load native pack and return just the pool in sound_manager legacy format.

    Each entry has {"file": <absolute_path>, "name": <display_name>} -- the same
    shape that _load_pool() returns, so it can drop in as a replacement pool.
    """
    pack = load_native_pack(platform)
    if pack is None:
        return None
    return pack["pool"]


# ---------------------------------------------------------------------------
# CLI for diagnostics
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate platform-native sound pack")
    parser.add_argument(
        "--platform", choices=["windows", "darwin", "linux"],
        help="Override platform detection",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    pack = load_native_pack(args.platform)
    if pack is None:
        print("No native pack available for this platform.")
        sys.exit(1)

    if args.json:
        print(json.dumps(pack, indent=2))
        sys.exit(0)

    pname = pack["name"]
    pplat = pack["platform"]
    ppool = len(pack["pool"])
    pmiss = len(pack["pool_missing"])
    pevt = len(pack["events"])
    pemiss = len(pack["events_missing"])
    print(f"Pack: {pname} ({pplat})")
    print(f"Pool: {ppool} sounds available, {pmiss} missing")
    print(f"Events: {pevt} configured, {pemiss} missing")
    print()

    print("Pool sounds:")
    for entry in pack["pool"]:
        nm = entry["name"]
        fl = entry["file"]
        print(f"  {nm:25s}  {fl}")

    if pack["pool_missing"]:
        print()
        print("Missing (not on this machine):")
        for entry in pack["pool_missing"]:
            nm = entry["name"]
            fl = entry["file"]
            print(f"  {nm:25s}  {fl}")

    print()
    print("Event sounds:")
    for key in ("completion", "error", "approval", "startup"):
        entry = pack["events"].get(key)
        if entry:
            nm = entry["name"]
            fl = entry["file"]
            print(f"  {key:15s}  {nm:25s}  {fl}")
        elif key in pack["events_missing"]:
            print(f"  {key:15s}  (missing on disk)")
        else:
            print(f"  {key:15s}  (not configured)")

    playback = detect_playback_command()
    print()
    if playback:
        pcmd = " ".join(playback)
        print(f"Playback command: {pcmd}")
    else:
        print("Playback command: NONE FOUND -- audio may not work")
