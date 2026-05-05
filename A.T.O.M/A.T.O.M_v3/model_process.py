# A.T.O.M/model_process.py
"""
Manages a single long-lived subprocess that holds BOTH models resident.
Phi stays on CPU (avoids CUDA access violation on 1650 Ti / keeps VRAM free).
Mistral stays on GPU (fits in 4 GB VRAM when Phi is on CPU).

No switching, no restarts, no CUDA poison.

Lock discipline
───────────────
_proc_lock  – protects _proc / _ready references ONLY.
              Never held during blocking I/O (readline, model load wait).
              _start() grabs it briefly to store the new proc, then
              releases it before the ready-wait loop.

_req_lock   – serialises concurrent inference callers so only ONE request
              is in-flight at a time.  Held for the full blocking readline
              loop, but NOT _proc_lock, so health checks can proceed
              without deadlocking on a long inference.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from typing import Callable

_proc:      subprocess.Popen | None = None
_proc_lock  = threading.Lock()   # guards _proc / _ready references only
_req_lock   = threading.Lock()   # one request in-flight at a time
_ready:     bool = False         # True once worker sent {"ready": true}

WORKER = os.path.join(os.path.dirname(__file__), "model_worker.py")


# ─────────────────────────────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────────────────────────────

def _kill_current() -> None:
    """Kill the running worker.  Caller MUST hold _proc_lock."""
    global _proc, _ready

    if _proc is not None:
        try:
            proc = _proc
            proc.stdin.write(json.dumps({"quit": True}) + "\n")
            proc.stdin.flush()
        except Exception:
            pass

        try:
            _proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _proc.kill()
            _proc.wait()

        _proc  = None
        _ready = False


def _stderr_drain(proc: subprocess.Popen) -> None:
    """Daemon thread: forward worker stderr to our stderr."""
    try:
        for line in proc.stderr:
            print(f"[WORKER STDERR] {line}", end="", file=sys.stderr, flush=True)
    except Exception:
        pass


def _proc_readline(proc: subprocess.Popen) -> str | None:
    """Read one line from the worker stdout. Returns None on EOF."""
    line = proc.stdout.readline()
    if not line:
        return None
    return line.strip()


def _proc_writeline(proc: subprocess.Popen, obj: dict) -> None:
    """Send one JSON line to the worker stdin."""
    proc.stdin.write(json.dumps(obj) + "\n")
    proc.stdin.flush()


def _start(status_fn: Callable[[str], None] | None = None) -> bool:
    """
    Spawn the dual-model worker and wait for {"ready": true}.

    IMPORTANT: This function must NOT be called while holding _proc_lock
    for the blocking wait phase.  It grabs the lock briefly to store the
    new proc handle, then releases it before the slow ready-wait loop so
    health-check callers are never blocked.
    """
    global _proc, _ready

    if status_fn:
        status_fn("[INFO] 🔄 Loading both models (Phi on CPU, Mistral on GPU)…")

    proc = subprocess.Popen(
        [sys.executable, WORKER, "both"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    threading.Thread(target=_stderr_drain, args=(proc,), daemon=True).start()

    # Store the proc handle so callers can poll alive status while we wait
    with _proc_lock:
        _proc  = proc
        _ready = False

    # Both models can take a while
    # _proc_lock is NOT held here so health checks are never blocked.
    deadline = time.time() + 240
    while time.time() < deadline:
        line = _proc_readline(proc)
        if line is None:
            # Process exited before sending ready
            break

        try:
            msg = json.loads(line.strip())
        except json.JSONDecodeError:
            continue

        if "status" in msg:
            if status_fn:
                status_fn(msg["status"])
            continue

        if msg.get("ready"):
            with _proc_lock:
                _ready = True
            if status_fn:
                status_fn("[INFO] ✅ Both models ready.")
            return True

        if "error" in msg:
            if status_fn:
                status_fn(f"[ERROR] Worker error: {msg['error']}")
            break

    # Failure path — kill and reset
    proc.kill()
    proc.wait()
    with _proc_lock:
        _proc  = None
        _ready = False

    if status_fn:
        status_fn("[ERROR] ❌ Failed to start model worker.")

    return False


def _ensure(status_fn: Callable[[str], None] | None = None) -> bool:
    """Ensure the dual worker is running; start it if not."""
    # Quick check inside lock — avoid spawning under the lock
    with _proc_lock:
        alive = (_proc is not None and _proc.poll() is None)
        if _ready and alive:
            return True
        # Kill stale handle if needed, then fall through to start
        _kill_current()

    # Spawn outside the lock so _start()'s blocking wait never holds _proc_lock
    return _start(status_fn=status_fn)


def _ask(
    model:       str,
    prompt:      str,
    max_tokens:  int,
    temperature: float,
    use_agent:   bool = False,
    status_fn:   Callable[[str], None] | None = None,
) -> str:
    """Send one request to the worker and block until a response arrives."""
    with _proc_lock:
        proc = _proc

    if proc is None:
        return "⚠️ No model loaded."

    if proc.poll() is not None:
        return "⚠️ Worker process is not running."

    try:
        _proc_writeline(proc, {
            "model":       model,
            "prompt":      prompt,
            "max_tokens":  max_tokens,
            "temperature": temperature,
            "use_agent":   use_agent,
        })

        while True:
            line = _proc_readline(proc)

            if line is None:
                code = proc.poll()
                print(f"[DEBUG] worker exit code: {code}", file=sys.stderr, flush=True)
                return f"⚠️ Worker process closed unexpectedly (exit code: {code})."

            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            if "status" in msg:
                if status_fn:
                    status_fn(msg["status"])
                continue

            if "error" in msg:
                return f"⚠️ {msg['error']}"

            if "response" in msg:
                return msg["response"]

    except Exception as e:
        return f"⚠️ IPC error: {e}"


# ─────────────────────────────────────────────────────────────────────
#  Classification — single source of truth
# ─────────────────────────────────────────────────────────────────────

def _classify(text: str) -> str:
    """Return 'mistral' for agentic/tool-use queries, 'phi' for everything else."""
    try:
        from agent import is_agentic_request
        return "mistral" if is_agentic_request(text) else "phi"
    except Exception:
        return "phi" if len(text.split()) <= 10 else "mistral"


# ─────────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────────

def route_and_respond(
    prompt:      str,
    max_tokens:  int   = 600,
    temperature: float = 0.7,
    status_fn:   Callable[[str], None] | None = None,
) -> str:
    """
    Classify → route to correct resident model → run inference.
    Agentic queries go to Mistral (ReAct loop).
    Conversational / code queries go to Phi (plain inference).
    """
    target    = _classify(prompt)
    use_agent = (target == "mistral")

    with _req_lock:
        if not _ensure(status_fn=status_fn):
            return "⚠️ Could not load models."

        return _ask(target, prompt, max_tokens, temperature,
                    use_agent=use_agent, status_fn=status_fn)


def run_agentic_task(
    goal:      str,
    status_fn: Callable[[str], None] | None = None,
) -> str:
    """Force the Mistral agent loop regardless of classification."""
    with _req_lock:
        if not _ensure(status_fn=status_fn):
            return "⚠️ Could not load models."
        return _ask("mistral", goal, max_tokens=2048, temperature=0.7,
                    use_agent=True, status_fn=status_fn)


def run_phi_query(
    prompt:      str,
    max_tokens:  int   = 1024,
    temperature: float = 0.7,
    status_fn:   Callable[[str], None] | None = None,
) -> str:
    """Force Phi for light conversation or code tasks."""
    with _req_lock:
        if not _ensure(status_fn=status_fn):
            return "⚠️ Could not load models."
        return _ask("phi", prompt, max_tokens, temperature,
                    use_agent=False, status_fn=status_fn)


def get_active_engine() -> str:
    """Both models are always resident; returns 'both' when ready."""
    return "both" if _ready else "none"


def shutdown() -> None:
    """Call on app exit to cleanly terminate the subprocess."""
    with _proc_lock:
        _kill_current()