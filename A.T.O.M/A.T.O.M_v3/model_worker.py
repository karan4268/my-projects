# A.T.O.M/model_worker.py
"""
Runs inside a subprocess.  Owns both models for its entire lifetime.
Communicates via stdin/stdout JSON lines.

Protocol
────────
  parent → child : {"model": "phi"|"mistral", "prompt": "...",
                     "max_tokens": 600, "temperature": 0.7,
                     "use_agent": true|false}
  child  → parent: {"ready":    true}
                   {"status":   "..."}   (progress during load or agent loop)
                   {"response": "..."}   (final answer)
                   {"error":    "..."}   (recoverable per-request error)
  parent → child : {"quit": true}

Pipe-protection strategy (Windows + Linux)
──────────────────────────────────────────
ctransformers prints inference progress directly via the C runtime to
file-descriptor 1 (stdout).  Python-level tricks (redirecting sys.stdout,
wrapping with _NullWriter, os.fdopen) do NOT stop this — the C library
calls WriteFile/write(1,...) directly, corrupting the JSON pipe.

The only reliable solution is to work at the OS fd level:

  1. Save the pipe write-end by dup()-ing fd 1 to a new fd (_pipe_fd).
  2. dup2(stderr_fd, 1) — point fd 1 at stderr so all C-level stdout
     writes go there instead of the pipe.
  3. For each _send(), temporarily dup2(_pipe_fd, 1), os.write, then
     dup2(stderr_fd, 1) again — the pipe is only open for the instant
     we need to write a protocol line.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import traceback

# ── OS-level pipe protection ─────────────────────────────────────────── #
# Must happen BEFORE any C-extension (ctransformers / torch) is imported.

_pipe_fd   = os.dup(sys.stdout.fileno())   # private copy of the pipe write-end
_stderr_fd = sys.stderr.fileno()

# Point fd 1 → stderr so any C-level write(1,...) goes to stderr, not the pipe
os.dup2(_stderr_fd, 1)

# Also redirect Python sys.stdout so print() hits stderr
sys.stdout = sys.stderr

# Lock: _send() may be called from status-callback threads during agent loops
_send_lock = threading.Lock()


def _send(obj: dict) -> None:
    """
    Write one JSON line to the real pipe.
    Briefly redirects fd 1 to the pipe, writes, then points it back at stderr.
    Using os.write() (unbuffered) so there is no intermediate buffer to flush.
    """
    data = (json.dumps(obj) + "\n").encode("utf-8")
    with _send_lock:
        os.dup2(_pipe_fd, 1)
        try:
            os.write(1, data)
        finally:
            os.dup2(_stderr_fd, 1)


def _status(msg: str) -> None:
    _send({"status": msg})


def _readline() -> str | None:
    """
    Read one line from stdin (fd 0 — never touched).
    Returns stripped text or None on EOF.
    """
    line = sys.stdin.readline()
    if not line:
        return None
    return line.strip()


def main() -> None:
    if len(sys.argv) < 2:
        _send({"error": "model_worker: no model name supplied"})
        sys.exit(1)

    model_name = sys.argv[1]   # "both" | "phi" | "mistral"

    respond         = None
    respond_agentic = None

    try:
        if model_name == "both":
            from local_engine import load_model
            from agent_model import load_agent_model

            _send({"status": "[INFO] Loading Phi on CPU..."})
            phi_llm = load_model(
                "Phi-3-mini-instruct",
                status_fn=_status,
                device="cpu",
            )

            _send({"status": "[INFO] Loading Mistral on GPU..."})
            ok = load_agent_model(
                status_fn=_status,
                device="cuda",
            )
            if not ok:
                _send({"error": "Mistral failed to load — check model path / VRAM."})
                sys.exit(1)

            def respond(model: str, prompt: str,
                        max_tokens: int, temperature: float) -> str:
                if model == "phi":
                    return phi_llm(
                        prompt,
                        max_new_tokens=max_tokens,
                        temperature=temperature,
                        top_p=0.9,
                    )
                else:
                    from agent_model import get_agent_response
                    return get_agent_response(
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )

            def respond_agentic(model: str, goal: str,
                                max_tokens: int, status_fn=None) -> str:
                if model == "phi":
                    return phi_llm(
                        goal,
                        max_new_tokens=max_tokens,
                        temperature=0.7,
                        top_p=0.9,
                    )
                else:
                    from agent import run_agent
                    return run_agent(goal, status_fn=status_fn)

        elif model_name == "phi":
            from local_engine import load_model

            phi_llm = load_model(
                "Phi-3-mini-instruct",
                status_fn=_status,
                device="cpu",
            )

            def respond(model: str, prompt: str,
                        max_tokens: int, temperature: float) -> str:
                return phi_llm(
                    prompt,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    top_p=0.9,
                )

            def respond_agentic(model: str, goal: str,
                                max_tokens: int, status_fn=None) -> str:
                return phi_llm(
                    goal,
                    max_new_tokens=max_tokens,
                    temperature=0.7,
                    top_p=0.9,
                )

        elif model_name == "mistral":
            from agent_model import load_agent_model

            ok = load_agent_model(status_fn=_status, device="cuda")
            if not ok:
                _send({"error": "Mistral failed to load — check model path / VRAM."})
                sys.exit(1)

            def respond(model: str, prompt: str,
                        max_tokens: int, temperature: float) -> str:
                from agent_model import get_agent_response
                return get_agent_response(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

            def respond_agentic(model: str, goal: str,
                                max_tokens: int, status_fn=None) -> str:
                from agent import run_agent
                return run_agent(goal, status_fn=status_fn)

        else:
            _send({"error": f"Unknown model name: {model_name!r}"})
            sys.exit(1)

    except Exception:
        _send({"error": f"Worker startup failed:\n{traceback.format_exc()}"})
        sys.exit(1)

    _send({"ready": True})

    # ── Request loop ─────────────────────────────────────────────────── #
    while True:
        raw_line = _readline()

        if raw_line is None:
            break   # stdin EOF — parent shut down

        if not raw_line:
            continue

        try:
            req = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        if req.get("quit"):
            break

        model       = req.get("model",       "phi")
        prompt      = req.get("prompt",      "")
        max_tokens  = req.get("max_tokens",  1000)
        temperature = req.get("temperature", 0.7)
        use_agent   = req.get("use_agent",   False)

        try:
            if use_agent:
                result = respond_agentic(model, prompt, max_tokens,
                                         status_fn=_status)
            else:
                result = respond(model, prompt, max_tokens, temperature)
        except Exception:
            _send({"error": traceback.format_exc()})
            continue

        _send({"response": result})


if __name__ == "__main__":
    main()