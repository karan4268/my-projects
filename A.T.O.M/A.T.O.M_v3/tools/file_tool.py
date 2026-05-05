# A.T.O.M/tools/file_tool.py
"""
File system tool for the A.T.O.M agent.
Supports read, write, append, list directory.
Input strings use a simple "operation|path|content" protocol so the
agent can pass a single string argument.
"""
import os
from pathlib import Path


def _safe_path(raw: str) -> Path:
    """Expand ~ and env vars, return absolute Path."""
    # Resolve 'desktop' shortcut to actual desktop path
    raw = raw.strip()
    if raw.lower() in ("desktop", "~/desktop"):
        return Path.home() / "Desktop"
    if raw.lower().startswith("desktop/") or raw.lower().startswith("desktop\\"):
        return Path.home() / "Desktop" / raw[8:]
    return Path(os.path.expandvars(os.path.expanduser(raw))).resolve()


def save_file(path: str, content: str) -> str:
    """Write content to file, creating parent directories as needed."""
    try:
        p = _safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"✅ Saved {len(content)} characters to {p}"
    except Exception as e:
        return f"❌ save_file failed: {e}"


def append_file(path: str, content: str) -> str:
    """Append content to file (creates it if missing)."""
    try:
        p = _safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(content)
        return f"✅ Saved to {p}"
    except Exception as e:
        return f"❌ append_file failed: {e}"


def read_file(path: str) -> str:
    """Read and return file content (truncated at 4000 chars for context safety)."""
    try:
        p = _safe_path(path)
        if not p.exists():
            return f"❌ File not found: {p}"
# Read only what we need — avoid loading a 1 GB file into RAM
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(4001)
        truncated = len(text) > 4000
        if truncated:
            return text[:4000] + f"\n... [truncated]"
        return text
    except Exception as e:
        return f"❌ read_file failed: {e}"


def list_directory(path: str = ".") -> str:
    """List files in a directory."""
    try:
        p = _safe_path(path)
        if not p.is_dir():
            return f"❌ Not a directory: {p}"
        entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
        lines = []
        for entry in entries[:50]:   # cap to 50 to stay within context
            kind = "FILE" if entry.is_file() else " DIR"
            lines.append(f"[{kind}] {entry.name}")
        return "\n".join(lines) or "(empty directory)"
    except Exception as e:
        return f"❌ list_directory failed: {e}"


# --- Unified dispatcher so agent can call one function with "op|path|content" ---
def file_tool(instruction: str) -> str:
    """
    Dispatch file operations from a single instruction string.
    Format:
      read|/path/to/file
      write|/path/to/file|content here
      append|/path/to/file|content here
      list|/path/to/dir
    """
    parts = instruction.split("|", 2)
    op = parts[0].strip().lower() if parts else ""

    if op == "read":
        return read_file(parts[1].strip() if len(parts) > 1 else "")
    elif op == "write":
        path = parts[1].strip() if len(parts) > 1 else ""
        content = parts[2] if len(parts) > 2 else ""
        return save_file(path, content)
    elif op == "append":
        path = parts[1].strip() if len(parts) > 1 else ""
        content = parts[2] if len(parts) > 2 else ""
        return append_file(path, content)
    elif op == "list":
        return list_directory(parts[1].strip() if len(parts) > 1 else ".")
    else:
        return (
            "❌ Unknown file operation. Use: read|path  /  write|path|content  "
            "/  append|path|content  /  list|dir"
        )
