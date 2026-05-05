# A.T.O.M/local_engine.py
"""
Phi model engine for A.T.O.M.

NOTE: This module runs inside model_worker.py (a dedicated subprocess).
Phi is always loaded on CPU so that all available VRAM is free for
Mistral.  The _infer_lock guards concurrent inference calls within the
subprocess; _cache_lock guards the cache dict.
"""
from __future__ import annotations

import gc
import threading
import time
from pathlib import Path
from typing import Callable

from PyQt5.QtCore import QSettings
from huggingface_hub import hf_hub_url
import requests
import torch
from ctransformers import AutoModelForCausalLM

# ================================================================== #
#  Model registry                                                      #
# ================================================================== #

AVAILABLE_MODELS: dict[str, dict] = {
    "Phi-3-mini-instruct": {
        "repo":           "QuantFactory/Phi-3-mini-4k-instruct-GGUF",
        "quant":          "Phi-3-mini-4k-instruct.Q4_K_M.gguf",
        "model_path":     None,
        "model_type":     "phi",
        "context_length": 4096,
    },
}

# ── thread-safe cache ─────────────────────────────────────────────── #
_llm_cache:         dict[str, "AutoModelForCausalLM"] = {}
_cache_lock:        threading.Lock = threading.Lock()
_active_model_name: str = "Phi-3-mini-instruct"
_infer_lock:        threading.Lock = threading.Lock()   # guards inference calls


# ================================================================== #
#  Settings helpers                                                    #
# ================================================================== #

def _get_models_dir() -> Path:
    return Path(r"F:\Experiments\A.T.O.M\models") #hardcoded


def get_active_model_name() -> str:
    return _active_model_name


def list_available_models() -> list[str]:
    return list(AVAILABLE_MODELS.keys())


def register_model(
    name:           str,
    repo:           str,
    quant:          str,
    model_type:     str = "phi",
    context_length: int = 4096,
    model_path:     str | None = None,
) -> None:
    """Dynamically register a new model at runtime."""
    AVAILABLE_MODELS[name] = {
        "repo":           repo,
        "quant":          quant,
        "model_type":     model_type,
        "context_length": context_length,
        "model_path":     model_path,
    }


# ================================================================== #
#  Model download                                                      #
# ================================================================== #

def download_model_hf(
    model_name:  str,
    save_dir:    str | None = None,
    status_fn:   Callable[[str], None] | None = None,
    progress_fn: Callable[[int], None] | None = None,
) -> bool:
    info = AVAILABLE_MODELS.get(model_name)
    if not info:
        if status_fn:
            status_fn(f"❌ Unknown model '{model_name}'.")
        return False

    repo_id    = info["repo"]
    quant_file = info["quant"]

    if not repo_id or not quant_file:
        if status_fn:
            status_fn(f"❌ Model '{model_name}' has no download URL configured.")
        return False

    base_dir = Path(save_dir or _get_models_dir()) / model_name
    base_dir.mkdir(parents=True, exist_ok=True)

    local_file = base_dir / quant_file
    if local_file.exists():
        if status_fn:
            status_fn(f"[INFO] ✅ '{quant_file}' already downloaded.")
        return True

    try:
        url = hf_hub_url(repo_id, quant_file)
    except Exception as e:
        if status_fn:
            status_fn(f"[ERROR] ❌ Could not get file URL: {e}")
        return False

    if status_fn:
        status_fn(f"[INFO] 📥 Downloading {quant_file} …")

    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total      = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(local_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_fn and total > 0:
                            progress_fn(int(downloaded / total * 100))
        if status_fn:
            status_fn(f"[INFO] ✅ Download complete: {quant_file}")
        if progress_fn:
            progress_fn(100)
        return True
    except Exception as e:
        if status_fn:
            status_fn(f"❌ Failed to download model: {e}")
        if local_file.exists():
            local_file.unlink(missing_ok=True)
        return False


# ================================================================== #
#  Locate local GGUF                                                   #
# ================================================================== #

def find_local_gguf(model_name: str, save_dir: str | None = None) -> Path | None:
    info = AVAILABLE_MODELS.get(model_name)
    if not info:
        return None

    model_path = info.get("model_path")
    if model_path:
        p = Path(model_path)
        if p.is_file():
            return p
        if p.is_dir():
            ggufs = list(p.glob("*.gguf"))
            if ggufs:
                return ggufs[0]

    base_dir = Path(save_dir or _get_models_dir()) / model_name
    if base_dir.exists():
        ggufs = list(base_dir.glob("*.gguf"))
        if ggufs:
            return ggufs[0]

    return None


# ================================================================== #
#  Load model (thread-safe, cached)                                    #
# ================================================================== #

def load_model(
    model_name: str | None = None,
    save_dir:   str | None = None,
    status_fn:  Callable[[str], None] | None = None,
    device:     str | None = None,
) -> "AutoModelForCausalLM":
    global _active_model_name

    settings     = QSettings("A.T.O.M", "Config")
    model_choice = settings.value("model_choice", "Phi-3-mini-instruct")
    name = model_name or model_choice

    # ── Fast path: already cached ─────────────────────────────────── #
    with _cache_lock:
        if name in _llm_cache:
            _active_model_name = name
            if status_fn:
                status_fn(f"[INFO] ✅ Model '{name}' already loaded (cached).")
            return _llm_cache[name]

    # ── Validate ──────────────────────────────────────────────────── #
    info = AVAILABLE_MODELS.get(name)
    if not info:
        raise ValueError(f"[ERROR] ❌ Model '{name}' is not registered in AVAILABLE_MODELS.")

    # ── Locate / download ─────────────────────────────────────────── #
    local_file = find_local_gguf(name, save_dir=save_dir)
    if not local_file:
        if status_fn:
            status_fn(f"[WARN] ⚠️ Model '{name}' not found locally — attempting download…")
        success = download_model_hf(name, save_dir=save_dir, status_fn=status_fn)
        if not success:
            raise RuntimeError(f"[ERROR] ❌ Could not download model '{name}'.")
        local_file = find_local_gguf(name, save_dir=save_dir)
        if not local_file:
            raise RuntimeError(f"[ERROR] ❌ Model '{name}' still not found after download.")

    # ── Phi always runs on CPU — VRAM is reserved for Mistral ─────── #
    # Ignore whatever 'device' was passed in.
    if device not in (None, "cpu"):
        if status_fn:
            status_fn(
                f"[INFO] Phi is always loaded on CPU (device='{device}' ignored). "
                "This preserves VRAM for the Mistral agent model."
            )

    model_type     = info.get("model_type", "phi")
    context_length = info.get("context_length", 4096)

    if status_fn:
        status_fn(f"[INFO] Loading '{name}' from '{local_file}' on CPU…")

    # ── GC before load ────────────────────────────────────────────── #
    gc.collect()

    # ── Load ──────────────────────────────────────────────────────── #
    try:
        instance = AutoModelForCausalLM.from_pretrained(
            str(local_file),
            model_type=model_type,
            gpu_layers=0,          # CPU only — all VRAM goes to Mistral
            context_length=context_length,
        )
        if status_fn:
            status_fn(f"[INFO] ✅ Loaded '{name}' on CPU.")
    except Exception as e:
        raise RuntimeError(
            f"[ERROR] ❌ Failed loading '{name}' on CPU: {e}"
        ) from e

    # ── Store in cache ────────────────────────────────────────────── #
    with _cache_lock:
        _llm_cache[name] = instance
        _active_model_name = name

    return instance


# ================================================================== #
#  Switch / set-path helpers                                           #
# ================================================================== #

def switch_model(
    model_name: str,
    save_dir:   str | None = None,
    status_fn:  Callable[[str], None] | None = None,
    device:     str | None = None,
) -> bool:
    """Switch the active model, loading it if not already cached."""
    if model_name not in AVAILABLE_MODELS:
        if status_fn:
            status_fn(f"❌ Unknown model '{model_name}'.")
        return False
    try:
        load_model(model_name, save_dir=save_dir, status_fn=status_fn, device=device)
        if status_fn:
            status_fn(f"🔄 Active model switched to '{model_name}'.")
        return True
    except Exception as e:
        if status_fn:
            status_fn(f"❌ Could not switch to '{model_name}': {e}")
        return False


def set_manual_model_path(
    model_name:  str,
    folder_path: str,
    status_fn:   Callable[[str], None] | None = None,
) -> bool:
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        if status_fn:
            status_fn(f"❌ Folder '{folder_path}' does not exist.")
        return False

    gguf_files = list(folder.glob("*.gguf"))
    if not gguf_files:
        if status_fn:
            status_fn(f"❌ No .gguf files found in '{folder_path}'.")
        return False

    if model_name in AVAILABLE_MODELS:
        AVAILABLE_MODELS[model_name]["model_path"] = str(folder)
    else:
        AVAILABLE_MODELS[model_name] = {
            "repo":           None,
            "quant":          None,
            "model_path":     str(folder),
            "model_type":     "phi",
            "context_length": 4096,
        }

    settings = QSettings("A.T.O.M", "Config")
    settings.setValue("model_path",   str(folder))
    settings.setValue("model_choice", model_name)

    if status_fn:
        status_fn(f"[INFO] ✅ Model path set for '{model_name}': {folder_path}")
    return True


# ================================================================== #
#  Unload model                                                        #
# ================================================================== #

def unload_model(
    model_name: str | None = None,
    status_fn:  Callable[[str], None] | None = None,
) -> bool:
    """Free a cached model from memory."""
    global _active_model_name
    with _cache_lock:
        name = model_name or _active_model_name
        if name not in _llm_cache:
            if status_fn:
                status_fn(f"[WARN] ⚠️ Model '{name}' was not loaded.")
            return False
        del _llm_cache[name]
        if _active_model_name == name:
            _active_model_name = next(iter(_llm_cache), "Phi-3-mini-instruct")

    if status_fn:
        status_fn(f"[INFO] 🗑️ Model '{name}' unloaded.")
    return True


# ================================================================== #
#  Generate response                                                   #
# ================================================================== #

def get_response_from_atom(
    prompt:      str,
    model_name:  str | None = None,
    max_tokens:  int   = 1024,
    temperature: float = 0.1,
    top_p:       float = 0.9,
    device:      str | None = None,
) -> str:
    """
    Generate text using the active (or specified) model.

    Parameters
    ----------
    prompt      : full prompt string
    model_name  : explicit model to use (defaults to active model)
    max_tokens  : maximum new tokens
    temperature : sampling temperature
    top_p       : nucleus sampling threshold
    device      : ignored for Phi (always CPU); kept for API compatibility

    Returns
    -------
    str — generated text
    """
    name  = model_name or _active_model_name
    model = load_model(name, device=device)
    try:
        with _infer_lock:
            return model(
                prompt,
                max_new_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
            )
    except Exception as e:
        raise RuntimeError(f"Error during model generation for '{name}': {e}") from e


# ================================================================== #
#  Quick test helper (for development use only)                        #
# ================================================================== #

def test_model(prompt: str = "Hello, test!", device: str = "cpu") -> bool:
    try:
        print("Loading model (test)…")
        load_model(device=device)
        out = get_response_from_atom(prompt, device=device)
        print("Model output:", out)
        return True
    except Exception as e:
        print("Test failed:", e)
        return False