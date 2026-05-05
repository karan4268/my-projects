# A.T.O.M/tools/memory_tool.py
"""
Persistent key-value memory store for the A.T.O.M agent.
Facts are stored in ~/A.T.O.M/memory.json so they survive restarts.

Dispatch format (same pipe-separated protocol as other tools):
  store|<key>|<value>   — save a fact
  recall|<key>          — retrieve a fact
  forget|<key>          — delete a fact
  list                  — show all stored keys
"""

import json
import os
from pathlib import Path
from datetime import datetime

_MEMORY_FILE = Path.home() / "A.T.O.M" / "memory.json"


def _load() -> dict:
    _MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _MEMORY_FILE.exists():
        try:
            return json.loads(_MEMORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(data: dict) -> None:
    _MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _MEMORY_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def store_fact(key: str, value: str) -> str:
    if not key.strip():
        return "❌ Key cannot be empty."
    data = _load()
    data[key.strip()] = {
        "value": value.strip(),
        "stored_at": datetime.now().isoformat(timespec="seconds"),
    }
    _save(data)
    return f"✅ Stored: '{key}' = '{value}'"


def recall_fact(key: str) -> str:
    data = _load()
    entry = data.get(key.strip())
    if not entry:
        return f"❌ No memory found for key: '{key}'. Use 'list' to see all keys."
    return f"'{key}' = {entry['value']}  (stored {entry['stored_at']})"


def forget_fact(key: str) -> str:
    data = _load()
    if key.strip() not in data:
        return f"❌ No memory found for key: '{key}'"
    del data[key.strip()]
    _save(data)
    return f"✅ Forgotten: '{key}'"


def list_facts() -> str:
    data = _load()
    if not data:
        return "📭 Memory is empty. Use 'store|key|value' to save facts."
    lines = [f"• {k}: {v['value']}  ({v['stored_at']})" for k, v in data.items()]
    return "📚 Stored memories:\n" + "\n".join(lines)


def memory_tool(instruction: str) -> str:
    """
    Dispatcher.  Input: 'store|key|value', 'recall|key', 'forget|key', 'list'
    """
    parts = instruction.split("|", 2)
    op = parts[0].strip().lower() if parts else ""

    if op in ("store", "remember", "save", "memorise", "memorize"):
        key   = parts[1].strip() if len(parts) > 1 else ""
        value = parts[2].strip() if len(parts) > 2 else ""
        if not value:
            return "❌ Use: store|<key>|<value>"
        return store_fact(key, value)

    elif op in ("recall", "get", "retrieve", "what is"):
        key = parts[1].strip() if len(parts) > 1 else ""
        return recall_fact(key)

    elif op in ("forget", "delete", "remove"):
        key = parts[1].strip() if len(parts) > 1 else ""
        return forget_fact(key)

    elif op == "list":
        return list_facts()

    else:
        return (
            "❌ Unknown memory operation. Use:\n"
            "  store|key|value  /  recall|key  /  forget|key  /  list"
        )
