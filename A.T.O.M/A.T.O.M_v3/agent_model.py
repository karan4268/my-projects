# A.T.O.M/agent_model.py
"""
Mistral-7B-Instruct-v0.3 GGUF wrapper for A.T.O.M's agentic reasoning.

Why Mistral instead of Phi-3/4 for tool-calling?
─────────────────────────────────────────────────
Phi-3/4 quantised models are excellent for conversational tasks and
summarisation, but they struggle to reliably produce the JSON-structured
output required in a ReAct tool-calling loop. Mistral-7B-Instruct-v0.3
Q4_K_M (~4.1 GB) is the sweet-spot for local agentic workloads:

  • Follows the [INST] / [/INST] prompt format consistently
  • Produces stable JSON action strings inside multi-turn loops
  • Fits comfortably in 4 GB VRAM when Phi is kept on CPU
  • Download: bartowski/Mistral-7B-Instruct-v0.3-GGUF on Hugging Face

Phi is still used (via local_engine.get_response_from_atom) for:
  • Purely conversational / no-tool queries
  • The final synthesis / summarisation step

Configuration
─────────────
Set agent_model_path in QSettings("A.T.O.M", "Config") or drop the GGUF
into ~/A.T.O.M/models/Mistral-7B-Instruct/.

GPU layer counts
────────────────
Mistral-7B has 32 transformer layers + 1 output (lm_head) layer.
Setting gpu_layers=35 safely offloads every layer (ctransformers clips to
the actual layer count, so over-specifying is harmless and ensures nothing
is left on CPU).  Phi is always run on CPU so all 4 GB VRAM go to Mistral.
"""

from __future__ import annotations

import gc
import threading
from pathlib import Path
from typing import Callable

import torch
from ctransformers import AutoModelForCausalLM
from PyQt5.QtCore import QSettings

# ── config keys ───────────────────────────────────────────────────── #
_SETTINGS_ORG    = "A.T.O.M"
_SETTINGS_APP    = "Config"
_AGENT_MODEL_KEY = "agent_model_path"

# ── Mistral download details ───────────────────────────────────────── #
MISTRAL_REPO  = "bartowski/Mistral-7B-Instruct-v0.3-GGUF"
MISTRAL_FILE  = "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
MISTRAL_TYPE  = "mistral"

# 32 transformer layers + lm_head; over-specifying is safe with ctransformers
_MISTRAL_GPU_LAYERS_FULL = 20

# ── Phi fallback via IPC (never load Phi inside the Mistral subprocess) ── #
def _phi_fallback(prompt: str, max_tokens: int = 512,
                  temperature: float = 0.3, top_p: float = 0.9) -> str:
    """
    Route a prompt to the Phi worker via model_process IPC.
    Keeps Phi in its own subprocess rather than loading it here.
    """
    try:
        from model_process import run_phi_query
        return run_phi_query(prompt, max_tokens=max_tokens,
                             temperature=temperature)
    except Exception as e:
        return f"⚠️ Phi fallback unavailable: {e}"


# ── global singleton ──────────────────────────────────────────────── #
_agent_llm        = None
_agent_ready      = False
_load_attempted   = False   # prevents repeated futile load attempts
_infer_lock       = threading.Lock()   # guards inference only


# ================================================================== #
#  Helpers                                                             #
# ================================================================== #

def _get_agent_model_path() -> Path | None:
    """Return configured / auto-discovered path to Mistral GGUF, or None."""
    settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    raw = settings.value(_AGENT_MODEL_KEY, None)
    if raw:
        p = Path(raw)
        if p.is_file():
            return p
        if p.is_dir():
            hits = list(p.glob("*.gguf"))
            if hits:
                return hits[0]

    # Auto-discover: look in the standard models folder
    base = Path.home() / "A.T.O.M" / "models" / "Mistral-7B-Instruct"
    if base.exists():
        hits = list(base.glob("*.gguf"))
        if hits:
            return hits[0]

    return None


def download_mistral(
    save_dir: str | None = None,
    status_fn: Callable[[str], None] | None = None,
    progress_fn: Callable[[int], None] | None = None,
) -> bool:
    """
    Download Mistral-7B-Instruct-v0.3 Q4_K_M from HuggingFace Hub.
    Returns True on success.
    """
    import requests
    from huggingface_hub import hf_hub_url

    base = Path(save_dir or (Path.home() / "A.T.O.M" / "models")) / "Mistral-7B-Instruct"
    base.mkdir(parents=True, exist_ok=True)
    local_file = base / MISTRAL_FILE

    if local_file.exists():
        if status_fn:
            status_fn(f"[INFO] ✅ Mistral already downloaded: {local_file}")
        return True

    try:
        url = hf_hub_url(MISTRAL_REPO, MISTRAL_FILE)
    except Exception as e:
        if status_fn:
            status_fn(f"[ERROR] ❌ Could not get Mistral URL: {e}")
        return False

    if status_fn:
        status_fn(f"[INFO] 📥 Downloading {MISTRAL_FILE} (~4.1 GB)…")

    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total      = int(r.headers.get("content-length", 0))
            downloaded = 0
            chunk_size = 1024 * 1024
            with open(local_file, "wb") as f:
                for chunk in r.iter_content(chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_fn and total:
                            progress_fn(int(downloaded / total * 100))

        if status_fn:
            status_fn(f"[INFO] ✅ Mistral download complete: {local_file}")
        if progress_fn:
            progress_fn(100)

        # Persist path in settings and reset load state so next call reloads
        settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        settings.setValue(_AGENT_MODEL_KEY, str(local_file))
        global _load_attempted
        _load_attempted = False

        return True

    except Exception as e:
        if status_fn:
            status_fn(f"[ERROR] ❌ Mistral download failed: {e}")
        return False


# ================================================================== #
#  Model loader                                                        #
# ================================================================== #

def load_agent_model(
    status_fn: Callable[[str], None] | None = None,
    device: str | None = None,
    force: bool = False,
) -> bool:
    """
    Load the Mistral GGUF into the global singleton.

    Parameters
    ----------
    status_fn : optional progress callback
    device    : 'cuda' | 'cpu' | None  (None → auto-detect; prefer CUDA)
    force     : re-attempt even if a previous attempt failed

    Returns True if successfully loaded, False if falling back to Phi.
    """
    global _agent_llm, _agent_ready, _load_attempted

    if _agent_ready:
        return True

    # Don't hammer a missing model on every inference call
    if _load_attempted and not force:
        return False

    _load_attempted = True

    model_path = _get_agent_model_path()
    if not model_path:
        if status_fn:
            status_fn(
                "[WARN] ⚠️ Mistral agent model not found. "
                "Agentic reasoning will fall back to Phi. "
                "Use Settings → Download Mistral to enable the full agent."
            )
        return False

    if status_fn:
        status_fn(f"[INFO] 🤖 Loading Mistral agent model from {model_path}…")

    # Device resolution — explicit beats auto-detect
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        if status_fn:
            status_fn("[WARN] ⚠️ CUDA requested but not available — using CPU.")
        device = "cpu"

    gpu_layers = _MISTRAL_GPU_LAYERS_FULL if device == "cuda" else 0

    if status_fn:
        status_fn(
            f"[INFO] Using device={device}, gpu_layers={gpu_layers} "
            f"(offloading {gpu_layers} layers to GPU)"
        )

    # Free any CUDA cache before loading so the allocator has a clean slate
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    def _try_load(gl: int) -> "AutoModelForCausalLM":
        return AutoModelForCausalLM.from_pretrained(
            str(model_path),
            model_type=MISTRAL_TYPE,
            gpu_layers=gl,
            context_length = 4096,
        )

    try:
        _agent_llm   = _try_load(gpu_layers)
        _agent_ready = True
        if status_fn:
            status_fn(
                f"[INFO] ✅ Mistral agent model loaded "
                f"(gpu_layers={gpu_layers}, device={device})"
            )
        return True

    except Exception as e_primary:
        if device == "cuda":
            # GPU OOM or driver error — retry on CPU
            if status_fn:
                status_fn(
                    f"[WARN] ⚠️ GPU load failed ({e_primary}). "
                    "Retrying on CPU — performance will be degraded…"
                )
            try:
                _agent_llm   = _try_load(0)
                _agent_ready = True
                if status_fn:
                    status_fn("[INFO] ✅ Mistral loaded on CPU (gpu_layers=0).")
                return True
            except Exception as e_cpu:
                if status_fn:
                    status_fn(
                        f"[ERROR] ❌ Mistral failed to load.\n"
                        f"  GPU error : {e_primary}\n"
                        f"  CPU error : {e_cpu}\n"
                        "Falling back to Phi for all responses."
                    )
                return False
        else:
            # Already on CPU — nothing to retry
            if status_fn:
                status_fn(
                    f"[ERROR] ❌ Mistral failed to load on CPU: {e_primary}\n"
                    "Falling back to Phi for all responses."
                )
            return False


# ================================================================== #
#  Format messages → Mistral [INST] prompt                            #
# ================================================================== #

def _format_mistral_prompt(
    messages: list[dict],
    system:   str | None = None,
) -> str:
    """
    Convert a message list into Mistral's [INST] format.

    Handles:
      • system role messages embedded in the list
      • stray / consecutive assistant turns
      • multi-turn history correctly
      • re-injecting a condensed rule reminder on every observation turn
        so Mistral doesn't lose its ReAct instructions after the first exchange

    Format:
      <s>[INST] <<SYS>>\\n{system}\\n<</SYS>>\\n\\n{user1} [/INST] {assistant1} </s>
      <s>[INST] {user2} [/INST] {assistant2} </s>
      <s>[INST] {userN} [/INST]
    """
    _REACT_REMINDER = (
        '\n\n[Reminder: output ACTION: {"tool":"...","input":"..."}'
        " OR FINAL ANSWER: ...]"
    )

    parts: list[str] = []
    sys_injected = False

    inline_system_parts: list[str] = []
    filtered: list[dict] = []
    for msg in messages:
        if msg["role"] == "system":
            inline_system_parts.append(msg["content"])
        else:
            filtered.append(msg)

    all_system_parts = []
    if system:
        all_system_parts.append(system)
    all_system_parts.extend(inline_system_parts)
    merged_system = "\n\n".join(all_system_parts) if all_system_parts else None

    i = 0
    while i < len(filtered):
        msg = filtered[i]

        if msg["role"] == "user":
            content = msg["content"]

            if not sys_injected and merged_system:
                content = f"<<SYS>>\n{merged_system}\n<</SYS>>\n\n{content}"
                sys_injected = True
            elif sys_injected and "OBSERVATION:" in content:
                content = content + _REACT_REMINDER

            if i + 1 < len(filtered) and filtered[i + 1]["role"] == "assistant":
                a_content = filtered[i + 1]["content"]
                parts.append(f"<s>[INST] {content} [/INST] {a_content} </s>")
                i += 2
            else:
                # Final user turn — leave [/INST] open for the model to complete
                parts.append(f"<s>[INST] {content} [/INST]")
                i += 1

        elif msg["role"] == "assistant":
            # Stray assistant turn with no preceding user turn in this window:
            # append to the last open [/INST] if present, otherwise skip
            if parts:
                last = parts[-1]
                if last.endswith("[/INST]"):
                    parts[-1] = last + f" {msg['content']} </s>"
            i += 1
        else:
            i += 1

    return "".join(parts)


# ================================================================== #
#  Inference entry point                                               #
# ================================================================== #

def get_agent_response(
    messages:    list[dict],
    system:      str | None = None,
    max_tokens:  int = 1000,
    temperature: float = 0.2,
    top_p:       float = 0.9,
    status_fn:   Callable[[str], None] | None = None,
) -> str:
    """
    Generate the next agent step using Mistral (or Phi fallback via IPC).

    Parameters
    ----------
    messages    : conversation history in OpenAI format
    system      : system prompt (injected into first user turn)
    max_tokens  : max new tokens to generate
    temperature : sampling temperature (low = more deterministic for tool calls)
    top_p       : nucleus sampling

    Returns
    -------
    str — raw model output (Thought + ACTION JSON or FINAL ANSWER)
    """
    # Ensure model is loaded — attempt once if not yet ready
    if not _agent_ready:
        if status_fn:
            status_fn("⚠️ Mistral not loaded — attempting load now…")
        loaded = load_agent_model(status_fn=status_fn)
        if not loaded:
            # Build a combined prompt and fall back to Phi via IPC
            combined = ""
            if system:
                combined += f"System: {system}\n\n"
            for m in messages[-4:]:
                combined += f"{m['role'].capitalize()}: {m['content']}\n"
            combined += "Assistant:"
            return _phi_fallback(combined, max_tokens=max_tokens,
                                 temperature=temperature, top_p=top_p)

    if _agent_ready and _agent_llm is not None:
        prompt = _format_mistral_prompt(messages, system=system)
        try:
            with _infer_lock:
                output = _agent_llm(
                    prompt,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                )
            text = str(output).strip()
            if "[/INST]" in text:
                text = text.split("[/INST]")[-1].strip()
            for marker in ("[INST]", "<<SYS>>", "<</SYS>>", "</s>", "<s>"):
                text = text.replace(marker, "").strip()
            return text
        except Exception as e:
            import sys as _sys
            print(
                f"[agent_model] ⚠️ Mistral inference error — falling back to Phi: {e}",
                file=_sys.stderr,
            )

    # Inference-time fallback: Mistral loaded but call failed
    combined = ""
    if system:
        combined += f"System: {system}\n\n"
    for m in messages[-4:]:
        combined += f"{m['role'].capitalize()}: {m['content']}\n"
    combined += "Assistant:"
    return _phi_fallback(combined, max_tokens=max_tokens,
                         temperature=temperature, top_p=top_p)


# ================================================================== #
#  Public status helpers                                               #
# ================================================================== #

def agent_model_available() -> bool:
    """Return True if Mistral is loaded and ready."""
    return _agent_ready


def reset_load_state() -> None:
    """
    Allow a fresh load attempt after a previous failure.
    Call this after the user fixes their model path or re-downloads Mistral.
    """
    global _load_attempted, _agent_ready, _agent_llm
    _load_attempted = False
    _agent_ready    = False
    _agent_llm      = None