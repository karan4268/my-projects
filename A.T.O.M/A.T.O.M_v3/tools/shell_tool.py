# A.T.O.M/tools/shell_tool.py
"""
Safe, read-only shell command executor for the A.T.O.M agent.

ONLY informational / diagnostic commands are permitted.
Any command that could modify the file system, registry, or network
configuration is blocked.

Allowed commands (whitelist approach):
  ipconfig, ping, tracert, nslookup, netstat,
  dir, tree, type,
  tasklist, systeminfo, ver, hostname,
  wmic (read-only), powershell Get-* cmdlets
"""

import subprocess
import re
import shlex
from pathlib import Path


# ── Safety whitelist ──────────────────────────────────────────────── #
_ALLOWED_PREFIXES = (
    "ipconfig", "ping", "tracert", "traceroute", "nslookup",
    "netstat", "nbtstat", "arp",
    "dir", "tree", "type", "echo",
    "tasklist", "systeminfo", "ver", "hostname", "whoami",
    "wmic", "get-",                          # PowerShell Get-* only
    "python --version", "python -V",
    "pip list", "pip show",
    "git log", "git status", "git branch", "git diff",
    "where ", "which ",
)

_BLOCKED_PATTERNS = re.compile(
    r'\b(rm|del|format|shutdown|reboot|net\s+user|reg\s+add|reg\s+delete|'
    r'taskkill|mklink|attrib|cipher|icacls|takeown|bcdedit|diskpart|'
    r'powercfg|schtasks\s+/create|schtasks\s+/delete|sc\s+start|sc\s+stop)\b',
    re.IGNORECASE
)

_MAX_OUTPUT = 2000  # chars


def shell_exec(command: str) -> str:
    """
    Execute a read-only shell command and return its stdout (truncated).
    Blocked commands return an error string.
    """
    cmd = command.strip()
    if not cmd:
        return "❌ No command provided."

    # Reject clearly dangerous patterns
    if _BLOCKED_PATTERNS.search(cmd):
        return (
            f"❌ Command blocked for safety: '{cmd}'. "
            "Only read-only / informational commands are permitted."
        )

    # Check whitelist
    cmd_lower = cmd.lower().lstrip()
    allowed = any(cmd_lower.startswith(p.lower()) for p in _ALLOWED_PREFIXES)
    if not allowed:
        return (
            f"❌ Command '{cmd}' is not in the allowed list. "
            "Permitted: ipconfig, ping, dir, tasklist, systeminfo, git log/status, etc."
        )

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = result.stdout or result.stderr or "(no output)"
        if len(output) > _MAX_OUTPUT:
            output = output[:_MAX_OUTPUT] + f"\n… [truncated — {len(output)} total chars]"
        return output.strip()

    except subprocess.TimeoutExpired:
        return f"❌ Command timed out: '{cmd}'"
    except Exception as e:
        return f"❌ Shell execution error: {e}"
