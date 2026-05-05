# A.T.O.M/agent.py
"""
A.T.O.M Agentic Core — ReAct Loop (Reason → Act → Observe → Repeat)
=====================================================================

Architecture
------------
  PLANNER  (Mistral-7B-Instruct-v0.3 GGUF)
    ↓
  ReAct LOOP  (up to MAX_STEPS iterations)
    • Thought  — model reasons about what to do next
    • Action   — model picks a tool + writes its input
    • Observe  — tool runs, result fed back into context
    ↓
  SYNTHESIZER  (Phi model, lighter — summarises scratchpad → final answer)

Why Mistral for the agent?
  Phi-3/4 quants are great for chat/summarisation but frequently fail
  to produce reliable JSON tool-call strings inside a loop. Mistral-7B-
  Instruct-v0.3 Q4_K_M (~4 GB) is the sweet-spot: fits in 6–8 GB VRAM,
  follows the [INST]/[/INST] chat format reliably, and produces stable
  structured output for tool calls.

Phi-3 / Phi-4 is still used for:
  • Pure conversational replies (no tools needed)
  • Synthesis / summarisation step (lighter load)

Fixes applied
-------------
  1. Added "summarise"/"summarize" keywords to file tool registry so
     "summarise file | /path" correctly triggers the file tool.
  2. Force-inject now uses _extract_legacy_input() so the injected
     tool input is "read|/path" rather than the raw goal string.
  3. Moved `import getpass` and duplicate `import re` to module top.
  4. Per-tool MAX_OBS_LEN overrides: file → 2000, web_search → 1200.
  5. Synthesis always uses Phi (get_response_from_atom), never Mistral.
"""

from __future__ import annotations

import getpass          # FIX 3: moved from inside the hot loop
import json
import re
import threading
import time
from typing import Callable

# ── local imports ──────────────────────────────────────────────────── #
from local_engine import get_response_from_atom
from agent_model import get_agent_response          # Mistral wrapper
from command import handle_command
from tools.web_search import web_search
from tools.file_tool import file_tool
from tools.code_review import review_code
from tools.calculator import calculate
from tools.shell_tool import shell_exec
from tools.memory_tool import memory_tool


# ================================================================== #
#  1. Tool Registry                                                    #
# ================================================================== #

TOOL_REGISTRY: dict[str, dict] = {
    "web_search": {
        "fn":   web_search,
        "desc": "Search the internet for real-time or factual information. "
                "Input: plain search query string.",
        "keywords": [
            "search", "look up", "lookup", "find online", "google",
            "latest", "news", "current", "today", "who is", "what is",
            "when did", "where is", "how many", "price of", "weather",
            "update", "recent", "trending", "find out",
        ],
    },
    "file": {
        "fn":   file_tool,
        "desc": "Read / write / append / list files on disk. "
                "Input format: 'read|/path'  'write|/path|content'  "
                "'append|/path|content'  'list|/dir'",
        "keywords": [
            "read file", "write file", "save file", "open file",
            "list files", "append to", "create file", "delete file",
            "show contents", "cat ", "ls ", "dir ", "load file",
            # FIX 1: summarise/summarize now correctly routes to the file tool
            "summarise file", "summarize file", "summarise", "summarize",
        ],
    },
    "code_review": {
        "fn":   review_code,
        "desc": "Review source code for bugs, style issues and improvements. "
                "Input: 'file|/path/to/file.py'  OR  'code|python|<raw code>'",
        "keywords": [
            "review code", "check code", "analyze code", "audit code",
            "review my code", "code quality", "lint", "find bugs",
            "check my code", "what's wrong with this code",
        ],
    },
    "system_command": {
        "fn":   handle_command,
        "desc": "Execute local system commands: open/launch apps, battery, "
                "system stats, screenshots, volume, etc. Input: natural language.",
        "keywords": [
            "open", "launch", "start app", "battery", "system info",
            "cpu usage", "ram usage", "screenshot", "volume", "brightness",
            "open app", "launch app",
        ],
    },
    "calculate": {
        "fn":   calculate,
        "desc": "Evaluate a mathematical or unit-conversion expression. "
                "Input: expression string, e.g. '(42 * 3.14) / 2'",
        "keywords": [
            "calculate", "compute", "what is", "how much is", "evaluate",
            "math", "plus", "minus", "divided by", "multiply", "convert",
            "percentage of", "square root", "% of",
        ],
    },
    "shell": {
        "fn":   shell_exec,
        "desc": "Run a safe, read-only shell command (Windows CMD / PowerShell). "
                "ONLY for informational commands (dir, ipconfig, tasklist, etc). "
                "Input: the command string.",
        "keywords": [
            "run command", "execute command", "shell", "cmd", "powershell",
            "terminal command", "ipconfig", "ping", "tasklist", "dir",
        ],
    },
    "memory": {
        "fn":   memory_tool,
        "desc": "Store or recall facts between sessions. "
                "Input: 'store|key|value'  OR  'recall|key'  OR  'list'",
        "keywords": [
            "remember", "recall", "forget", "store this", "save this",
            "what did i tell you", "note this", "memorise", "memorize",
        ],
    },
}

# FIX 4: per-tool observation length overrides (default 600 is too tight for file reads)
_MAX_OBS_LEN_DEFAULT = 600
_MAX_OBS_LEN_OVERRIDES: dict[str, int] = {
    "file":       2000,
    "web_search": 1200,
}


# ================================================================== #
#  2. ReAct Prompts                                                    #
# ================================================================== #

_SYSTEM_PROMPT = """You are A.T.O.M, an agentic AI operating in a ReAct loop: Thought → ACTION → OBSERVATION → ... → FINAL ANSWER.

Desktop: "C:/Users/{username}/OneDrive/Desktop"

Tools:
{tool_list}

Rules:
- ALWAYS start with a Thought.
- To call a tool, output EXACTLY this JSON on its own line (no extra text):
  ACTION: {{"tool": "<tool_name>", "input": "<tool_input>"}}
- After seeing an OBSERVATION, think again and either call another tool or give the Final Answer.
- When done, output EXACTLY:
  FINAL ANSWER: <your complete answer here>
- NEVER make up tool results. ALWAYS use a tool if you need real data.
- Keep Thoughts concise (1-2 sentences).
- If a tool returns an error, try a different approach or tool.
- Do NOT call the same tool with the exact same input twice.
"""

_TOOL_ENTRY = "  • {name}: {desc}"

_USER_TEMPLATE = """User goal: {goal}

Begin your reasoning now."""

_REACT_CONTINUE = """OBSERVATION: {observation}

Continue your reasoning. Either call another tool or give the Final Answer."""


# ================================================================== #
#  3. Keyword Router (pre-filter so trivial queries skip the loop)     #
# ================================================================== #

def _normalise(text: str) -> str:
    t = text.lower().strip()
    typos = {
        "seacrh": "search", "searh": "search", "serach": "search",
        "calcualte": "calculate", "calcualtion": "calculate",
    }
    for wrong, right in typos.items():
        t = t.replace(wrong, right)
    return re.sub(r"\s+", " ", t)


def route(goal: str) -> list[str]:
    """Return list of tool names that keyword-match this goal."""
    t = _normalise(goal)
    matched = []
    for name, info in TOOL_REGISTRY.items():
        for kw in info["keywords"]:
            if kw in t:
                if name not in matched:
                    matched.append(name)
                break
    # compound: "review code in file X" → file first, then code_review
    if "code_review" in matched and "file" not in matched:
        if re.search(r"\bfile\b|\bpath\b|\.py\b|\.js\b|\.cpp\b|\.ts\b", t):
            matched.insert(0, "file")
    return matched


# Matches requests like "convert this to Python", "rewrite in Java", "write this in C++"
# These are pure LLM tasks — no tools needed, so we bypass the ReAct loop entirely.
_CODE_CONVERT_RE = re.compile(
    r'\b(convert|translate|rewrite|write|port)\b.{0,60}'
    r'\b(python|java|javascript|typescript|c\+\+|cpp|rust|go|ruby|swift|kotlin|scala)\b',
    re.IGNORECASE | re.DOTALL,
)

# Matches requests that contain raw code keywords strongly suggesting translation
_CODE_BLOCK_CONVERT_RE = re.compile(
    r'(#include\s*<|public\s+static\s+void|def\s+\w+\s*\(|function\s+\w+\s*\()'
    r'.{0,200}'
    r'\b(convert|translate|rewrite|write|in python|to python|to java|in java)\b',
    re.IGNORECASE | re.DOTALL,
)


def is_agentic_request(text: str) -> bool:
    """
    Returns True if the request needs agentic tool use.
    Combines keyword routing with heuristic signals that imply tool need
    even without an exact keyword match (e.g. file paths, URLs, code blocks).
    """
    # ── Pure LLM bypass: code translation / conversion tasks ─────────────
    # These never need tools — routing them into the ReAct loop causes the
    # agent to hallucinate unnecessary web_search / code_review tool calls.
    if _CODE_CONVERT_RE.search(text):
        return False
    if _CODE_BLOCK_CONVERT_RE.search(text):
        return False

    if route(text):
        return True
    t = _normalise(text)
    # Implicit signals
    if re.search(r'https?://', text):                          # URL present
        return True
    if re.search(r'[A-Za-z]:\\[\w\\/.]+|/[\w/]{3,}', text):  # file path
        return True
    if re.search(r'```[\w]*\n.*?```', text, re.DOTALL):       # code block
        return True
    return False


# ================================================================== #
#  4. Tool Execution                                                   #
# ================================================================== #

def _run_tool(tool_name: str, tool_input: str, status_fn=None) -> str:
    info = TOOL_REGISTRY.get(tool_name)
    if not info:
        return f"❌ Unknown tool: '{tool_name}'. Available: {', '.join(TOOL_REGISTRY)}"
    if status_fn:
        preview = tool_input[:80] + ("…" if len(tool_input) > 80 else "")
        status_fn(f"🔧 [{tool_name}] {preview}")
    try:
        result = info["fn"](tool_input)
        return str(result)
    except Exception as e:
        return f"❌ Tool '{tool_name}' error: {e}"


# ================================================================== #
#  5. ReAct Parser (robust — handles malformed JSON gracefully)        #
# ================================================================== #

_ACTION_RE = re.compile(
    r'ACTION:\s*(\{.*?\})',
    re.DOTALL | re.IGNORECASE,
)
_FINAL_RE = re.compile(
    r'FINAL\s+ANSWER:\s*(.*)',
    re.DOTALL | re.IGNORECASE,
)
# Fallback: model sometimes writes tool/input on separate lines
_LOOSE_TOOL_RE = re.compile(
    r'"tool"\s*:\s*"([^"]+)".*?"input"\s*:\s*"([^"]*)"',
    re.DOTALL | re.IGNORECASE,
)


def _repair_json(raw: str) -> dict | None:
    """
    Best-effort JSON repair for common model output issues:
      • Trailing commas
      • Single-quoted strings
      • Unescaped newlines inside string values
    Returns a dict on success, None on failure.
    """
    # Strip markdown fences
    raw = re.sub(r"```json|```", "", raw).strip()
    # Replace smart quotes
    raw = raw.replace("\u201c", '"').replace("\u201d", '"')
    # Single → double quotes (crude but catches simple cases)
    if "'" in raw and '"' not in raw:
        raw = raw.replace("'", '"')
    # Remove trailing commas before } or ]
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _parse_step(text: str) -> tuple[str, str | None, str | None]:
    """
    Returns (thought, tool_name_or_None, tool_input_or_None).
    If this is the final-answer step, returns (answer, None, None).
    Falls back through multiple strategies before giving up.
    """
    # ── Pre-clean: strip Mistral prompt artifacts and hallucinated leakage ──
    _LEAK_RE = re.compile(
        r'(Instruction\s+\d|system\s*:|You are an? (?:advanced|powerful)|'
        r'Available tools:|Written by an AI|Please rephrase|'
        r'\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>|</s>|<s>)',
        re.IGNORECASE,
    )
    leak = _LEAK_RE.search(text)
    if leak:
        # For [/INST] keep everything AFTER the last occurrence
        if "[/INST]" in text:
            text = text.split("[/INST]")[-1].strip()
        else:
            text = text[:leak.start()].strip()

    # ── Strategy 1: FINAL ANSWER ──────────────────────────────────────
    fm = _FINAL_RE.search(text)
    if fm:
        return fm.group(1).strip(), None, None

    # ── Strategy 2: Well-formed ACTION JSON ───────────────────────────
    am = _ACTION_RE.search(text)
    if am:
        action = _repair_json(am.group(1))
        if action and "tool" in action:
            tool  = str(action["tool"]).strip()
            inp   = str(action.get("input", "")).strip()
            thought = text[: am.start()].strip()
            return thought, tool, inp

    # ── Strategy 3: JSON block anywhere in output ─────────────────────
    json_block = re.search(r'\{[^{}]*"tool"[^{}]*\}', text, re.DOTALL)
    if json_block:
        action = _repair_json(json_block.group(0))
        if action and "tool" in action:
            tool  = str(action["tool"]).strip()
            inp   = str(action.get("input", "")).strip()
            thought = text[: json_block.start()].strip()
            return thought, tool, inp

    # ── Strategy 4: Loose key-value extraction ────────────────────────
    lm = _LOOSE_TOOL_RE.search(text)
    if lm:
        tool = lm.group(1).strip()
        inp  = lm.group(2).strip()
        thought = text[: lm.start()].strip()
        return thought, tool, inp

    # ── Strategy 5: No valid action — sanity-check before returning ───
    cleaned = text.strip()

    # Only reject if it looks like a broken ACTION attempt, not a real answer
    _GARBAGE_RE = re.compile(
        r'^\s*\{\s*"tool"|"action"\s*:\s*\{|\[response\]|ACTION\s*:\s*\{',
        re.IGNORECASE,
    )
    if _GARBAGE_RE.search(cleaned):
        return (
            "⚠️ The agent produced an unreadable response. "
            "Please try rephrasing your request.",
            None,
            None,
        )

    # If the answer is non-empty and doesn't look like garbage, return it
    if cleaned:
        return cleaned, None, None

    return "⚠️ Agent produced no answer.", None, None


# ================================================================== #
#  6. Main ReAct Loop                                                  #
# ================================================================== #

MAX_STEPS = 4    # safety cap — prevents infinite loops


def run_agent(
    goal: str,
    status_fn: Callable[[str], None] | None = None,
    history: list[dict] | None = None,
) -> str:

    # ── Quick-check: pure conversation? ──────────────────────────────
    if not is_agentic_request(goal):
        if status_fn:
            status_fn(f"[INFO]💬 Conversational query — using Phi model directly.")
        return get_response_from_atom(goal, max_tokens=1000,
                                      temperature=0.7, top_p=0.9)

    # ── Build tool list for system prompt ────────────────────────────
    tool_list = "\n".join(
        _TOOL_ENTRY.format(name=n, desc=info["desc"])
        for n, info in TOOL_REGISTRY.items()
    )
    system_prompt = _SYSTEM_PROMPT.format(
        tool_list=tool_list,
        username=getpass.getuser()   # FIX 3: getpass already imported at top
    )

    # ── Build initial message history ────────────────────────────────
    messages: list[dict] = []
    if history:
        messages.extend(history[-6:])

    forced_tools = route(goal)

    messages.append({
        "role":    "user",
        "content": _USER_TEMPLATE.format(goal=goal),
    })

    if status_fn:
        status_fn(f"[INFO]🤖 Agent starting ReAct loop for: {goal[:60]}…")

    scratchpad: list[str] = []
    final_answer: str | None = None
    tool_call_count = 0
    seen_calls: set[tuple[str, str]] = set()
    _force_attempted = False   # ensures we only force-inject a tool call once

    # ── ReAct Loop ───────────────────────────────────────────────────
    for step in range(MAX_STEPS):

        if status_fn:
            status_fn(f"🔄 Step {step + 1}/{MAX_STEPS} — reasoning…")

        try:
            raw_output = get_agent_response(
                messages=messages,
                system=system_prompt,
                max_tokens=600,
                temperature=0.2,
                status_fn=status_fn,
            )
        except Exception as e:
            if status_fn:
                status_fn(f"⚠️ Model inference error at step {step + 1}: {e}")
            break

        if not raw_output or not raw_output.strip():
            if status_fn:
                status_fn(f"⚠️ Empty model output at step {step + 1} — stopping.")
            break

        scratchpad.append(f"[Step {step + 1}]\n{raw_output}")
        thought, tool_name, tool_input = _parse_step(raw_output)

        # ── Final answer reached ──────────────────────────────────────
        if tool_name is None:
            if not _force_attempted and tool_call_count == 0 and forced_tools:
                _force_attempted = True
                if status_fn:
                    status_fn("⚠️ Model skipped tools — forcing first tool call…")
                tool_name_forced = forced_tools[0]
                # FIX 2: use _extract_legacy_input so the injected input is
                # "read|/path" rather than the raw goal string, which file_tool
                # cannot parse and would return an error.
                tool_input_forced = _extract_legacy_input(tool_name_forced, goal)
                messages.append({"role": "assistant", "content": raw_output})
                messages.append({
                    "role": "user",
                    "content": (
                        f"OBSERVATION: ❌ No tools were called. You MUST call a tool.\n"
                        f"Call this tool now:\n"
                        f'ACTION: {{"tool": "{tool_name_forced}", "input": "{tool_input_forced}"}}'
                    ),
                })
                continue
            final_answer = thought
            if status_fn:
                status_fn("✅ Agent reached final answer.")
            break

        # ── Deduplication guard ───────────────────────────────────────
        call_key = (tool_name, tool_input)
        if call_key in seen_calls:
            if status_fn:
                status_fn(f"⚠️ Duplicate tool call ({tool_name}) — stopping loop.")
            messages.append({"role": "assistant", "content": raw_output})
            messages.append({
                "role": "user",
                "content": (
                    "OBSERVATION: ❌ You already called this tool with the same input. "
                    "Do NOT repeat it. Use a different tool or provide the FINAL ANSWER now."
                ),
            })
            continue
        seen_calls.add(call_key)

        # ── Tool call ─────────────────────────────────────────────────
        tool_call_count += 1
        if status_fn:
            status_fn(f"[INFO]🔧 Calling tool '{tool_name}'…")

        observation = _run_tool(tool_name, tool_input, status_fn=status_fn)

        # FIX 4: use per-tool observation length cap
        obs_limit = _MAX_OBS_LEN_OVERRIDES.get(tool_name, _MAX_OBS_LEN_DEFAULT)
        if len(observation) > obs_limit:
            observation = observation[:obs_limit] + "\n… [truncated]"

        scratchpad.append(f"[Observation]\n{observation}")

        # Early exit: file saved successfully — task is done
        if tool_name == "file" and observation.startswith("✅"):
            final_answer = f"Done. {observation}"
            if status_fn:
                status_fn("✅ File saved — task complete.")
            break

        # If web_search just ran and goal requires saving to file,
        # force the next step to be a file write instead of letting
        # Mistral skip it and give a premature FINAL ANSWER
        save_keywords = ["save", "write", "store", "txt", "file", "desktop", "document"]
        needs_save = any(kw in goal.lower() for kw in save_keywords)
        if tool_name == "web_search" and needs_save and observation and not observation.startswith("❌"):
            # FIX 3: getpass already imported at top — no inline import needed
            desktop = f"C:/Users/{getpass.getuser()}/Desktop"
            name_match = re.search(r'save (?:it |details? )?as ([^\s]+\.txt)', goal, re.IGNORECASE)
            filename = name_match.group(1) if name_match else "search_results.txt"
            filepath = f"{desktop}/{filename}"
            forced_input = f"write|{filepath}|{observation[:2000]}"
            if status_fn:
                status_fn(f"📝 Forcing file save to {filepath}…")
            messages.append({"role": "assistant", "content": raw_output})
            messages.append({
                "role": "user",
                "content": (
                    f"OBSERVATION: {observation[:800]}\n\n"
                    f"Now save this information to a file. Call this tool:\n"
                    f'ACTION: {{"tool": "file", "input": "{forced_input}"}}'
                ),
            })
            continue

        messages.append({"role": "assistant", "content": raw_output})
        messages.append({
            "role":    "user",
            "content": _REACT_CONTINUE.format(observation=observation),
        })

    # ── Synthesise if loop exhausted without FINAL ANSWER ────────────
    if final_answer is None:
        if status_fn:
            status_fn("⚠️ Max steps reached — synthesising from scratchpad…")

        relevant_steps = [s for s in scratchpad if "[Observation]" in s]
        if not relevant_steps:
            relevant_steps = scratchpad

        if not relevant_steps:
            final_answer = "⚠️ Agent produced no usable output."
        else:
            combined = "\n\n".join(relevant_steps)[-3000:]
            synth_prompt = (
                f"You are A.T.O.M. Summarise these reasoning steps into a clear, "
                f"concise answer for the user.\n\n"
                f"User goal: {goal}\n\n"
                f"Steps:\n{combined}\n\n"
                f"Final answer:"
            )
            # FIX 5: always use Phi (get_response_from_atom) for synthesis.
            # Mistral is the planner and is done by this point — using it here
            # wastes VRAM and contradicts the two-model architecture.
            try:
                final_answer = get_response_from_atom(
                    synth_prompt, max_tokens=512, temperature=0.3
                ).strip()
            except Exception as e:
                last_obs = next(
                    (s.replace("[Observation]", "").strip()
                     for s in reversed(scratchpad) if "[Observation]" in s),
                    None
                )
                final_answer = last_obs or f"⚠️ Could not synthesise answer: {e}"

    return final_answer or "⚠️ Agent produced no answer."


# ================================================================== #
#  7. Legacy single-shot path (kept for backward compatibility)        #
# ================================================================== #

def _legacy_run(goal: str, status_fn=None) -> str:
    """
    Fast path for queries that only need ONE tool call (no chain needed).
    Used when the agent model is not available / loading.
    """
    tools = route(goal)
    if not tools:
        return get_response_from_atom(goal)

    results = []
    for name in tools:
        inp = _extract_legacy_input(name, goal)
        res = _run_tool(name, inp, status_fn)
        if len(res) > 1500:
            res = res[:1500] + "\n… [truncated]"
        results.append((name, res))
        if name == "system_command" and res and not res.startswith("❌"):
            return res

    combined = "\n\n".join(f"[{n}]\n{r}" for n, r in results)
    prompt = (
        f"You are A.T.O.M. Answer this query using ONLY the tool results provided.\n"
        f"Query: {goal}\n\nTool results:\n{combined}\n\nAnswer:"
    )
    return get_response_from_atom(prompt, max_tokens=512, temperature=0.3).strip()


def _extract_legacy_input(tool_name: str, goal: str) -> str:
    t = _normalise(goal)
    if tool_name == "web_search":
        for prefix in ("search for ", "search ", "look up ", "lookup ",
                       "find online ", "google ", "what is the latest on "):
            if t.startswith(prefix):
                return goal[len(prefix):].strip()
        return goal.strip()
    if tool_name == "file":
        if "|" in goal:
            return goal
        pm = re.search(r'["\']?([A-Za-z]:\\[\w\\/.]+|/[\w/.]+)["\']?', goal)
        if pm:
            p = pm.group(1)
            if any(w in t for w in ("write", "save", "create")):
                return f"write|{p}|{goal[pm.end():].strip().lstrip(chr(34)+chr(39)+':')}"
            if "append" in t:
                return f"append|{p}|{goal[pm.end():].strip().lstrip(chr(34)+chr(39)+':')}"
            if "list" in t:
                return f"list|{p}"
            return f"read|{p}"
        return goal
    if tool_name == "code_review":
        pm = re.search(r'["\']?([A-Za-z]:\\[\w\\/.]+\.\w+|/[\w/.]+\.\w+)["\']?', goal)
        if pm:
            return f"file|{pm.group(1)}"
        cm = re.search(r"```([\w]*)\n(.*?)```", goal, re.DOTALL)
        if cm:
            return f"code|{cm.group(1) or 'python'}|{cm.group(2)}"
        return f"code|python|{goal}"
    return goal


# ================================================================== #
#  8. Thread Worker (PyQt UI integration)                             #
# ================================================================== #

class AgentWorker(threading.Thread):
    """
    Drop-in background worker for use with PyQt UI.
    Emits status via status_fn(str) and delivers the result via done_fn(str).
    """

    def __init__(
        self,
        goal:      str,
        status_fn: Callable[[str], None] | None = None,
        done_fn:   Callable[[str], None] | None = None,
        history:   list[dict] | None = None,
    ):
        super().__init__(daemon=True, name="ATOM-Agent")
        self.goal      = goal
        self.status_fn = status_fn
        self.done_fn   = done_fn
        self.history   = history or []

    def run(self):
        try:
            result = run_agent(
                self.goal,
                status_fn=self.status_fn,
                history=self.history,
            )
        except Exception as e:
            result = f"⚠️ Agent error: {e}"
            if self.status_fn:
                try:
                    self.status_fn(result)
                except Exception:
                    pass

        if self.done_fn:
            try:
                self.done_fn(result)
            except Exception:
                pass