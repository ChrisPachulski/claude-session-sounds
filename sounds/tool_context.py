"""
Parse tool context and detect outcomes from Claude Code hook JSON.

Used by the sound system to determine event type (completion/error/approval)
and optionally which tool/command triggered the event.
"""
from __future__ import annotations

import re
from typing import NamedTuple


###############################################################################
# Known CLI commands and their valid subcommands (adapted from claudio)
###############################################################################

KNOWN_SUBCOMMANDS: dict[str, set[str]] = {
    "git": {"add", "commit", "push", "pull", "clone", "checkout", "branch",
            "merge", "rebase", "status", "log", "diff", "fetch", "stash",
            "reset", "revert", "tag", "remote"},
    "npm": {"install", "uninstall", "update", "start", "stop", "test", "run",
            "build", "publish", "init", "audit"},
    "docker": {"build", "run", "pull", "push", "start", "stop", "exec",
               "compose", "volume", "network", "ps", "images", "logs"},
    "cargo": {"build", "run", "test", "check", "fmt", "clippy", "add",
              "install", "doc", "bench", "clean", "new", "init"},
    "go": {"build", "run", "test", "install", "get", "mod", "fmt", "vet",
           "generate", "clean"},
    "pip": {"install", "uninstall", "list", "show", "freeze", "download"},
    "yarn": {"add", "install", "remove", "upgrade", "start", "build", "test",
             "run", "init"},
    "kubectl": {"get", "describe", "create", "apply", "delete", "logs",
                "exec", "port-forward", "scale", "rollout"},
}

_PATH_OR_URL_RE = re.compile(r"[/.]|://")


###############################################################################
# ToolContext result type
###############################################################################

class ToolContext(NamedTuple):
    tool: str            # e.g. "bash", "read", "write", "edit"
    command: str | None  # e.g. "git", "npm" (Bash tool only)
    subcommand: str | None  # e.g. "commit", "push" (known CLIs only)
    is_error: bool       # True if the tool failed


###############################################################################
# Command parsing
###############################################################################

def _extract_command(command_str: str) -> tuple[str | None, str | None]:
    """Extract the base command and subcommand from a Bash command string."""
    if not command_str:
        return None, None

    # Split on whitespace, skip env vars (FOO=bar) and sudo/nohup wrappers
    words = command_str.split()
    cmd = None
    for word in words:
        if "=" in word and not word.startswith("-"):
            continue  # environment variable
        if word in ("sudo", "nohup", "nice", "time", "env"):
            continue  # wrapper commands
        if word.startswith("-"):
            continue  # flags
        cmd = word.split("/")[-1]  # strip path prefix
        break

    if cmd is None:
        return None, None

    # Find subcommand (next non-flag word after command)
    cmd_lower = cmd.lower()
    valid_subs = KNOWN_SUBCOMMANDS.get(cmd_lower)
    if valid_subs is None:
        return cmd_lower, None

    found_cmd = False
    for word in words:
        if not found_cmd:
            if word.split("/")[-1].lower() == cmd_lower:
                found_cmd = True
            continue
        if word.startswith("-"):
            continue
        if _PATH_OR_URL_RE.search(word):
            continue  # path or URL, not a subcommand
        if word.lower() in valid_subs:
            return cmd_lower, word.lower()
        break  # first non-flag word after cmd that isn't a known subcommand

    return cmd_lower, None


###############################################################################
# Error detection
###############################################################################

def _detect_error(tool_name: str, tool_response: dict | None) -> bool:
    """Determine if a tool invocation failed based on its response."""
    if tool_response is None:
        return False

    # Check universal interrupt flag
    if tool_response.get("interrupted"):
        return True

    # Check stderr -- only flag as error if it contains real error patterns
    # (many successful commands write warnings to stderr: npm, git, pip)
    stderr = tool_response.get("stderr", "")
    if stderr and isinstance(stderr, str):
        stderr_lower = stderr.lower()
        _ERROR_PATTERNS = ("error:", "fatal:", "traceback", "exception:", "panic:",
                           "command not found", "permission denied", "segfault")
        if any(pat in stderr_lower for pat in _ERROR_PATTERNS):
            return True

    tool_lower = tool_name.lower()

    if tool_lower in ("read", "glob", "ls"):
        content = tool_response.get("content")
        return content is None

    if tool_lower in ("edit", "write", "multiedit"):
        success = tool_response.get("success")
        if isinstance(success, bool):
            return not success

    return False


###############################################################################
# Main parser
###############################################################################

def parse_tool_context(hook_data: dict) -> ToolContext:
    """Parse a Claude Code hook JSON payload into a ToolContext.

    Args:
        hook_data: The full hook JSON object with tool_name, tool_input,
                   tool_response fields.

    Returns:
        ToolContext with tool name, optional command/subcommand, and error flag.
    """
    tool_name = hook_data.get("tool_name", "unknown")
    tool_input = hook_data.get("tool_input") or {}
    tool_response = hook_data.get("tool_response")

    command = None
    subcommand = None

    if tool_name.lower() == "bash":
        cmd_str = tool_input.get("command", "")
        command, subcommand = _extract_command(cmd_str)

    is_error = _detect_error(tool_name, tool_response)

    return ToolContext(
        tool=tool_name.lower(),
        command=command,
        subcommand=subcommand,
        is_error=is_error,
    )


def detect_outcome(hook_data: dict) -> str:
    """Determine the event outcome from hook JSON.

    Returns one of: "completion", "approval", "error", "end", "unknown".

    This is the canonical outcome detector for the sound system's
    event-type dispatch.
    """
    event_name = hook_data.get("hook_event_name", "")

    if event_name == "Stop":
        return "completion"

    if event_name == "StopFailure":
        return "error"

    if event_name == "Notification":
        return "approval"

    if event_name == "SessionEnd":
        return "end"

    if event_name == "PostToolUse":
        ctx = parse_tool_context(hook_data)
        return "error" if ctx.is_error else "completion"

    return "unknown"
