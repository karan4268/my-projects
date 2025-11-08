# A.T.O.M/local_engine.py
import os
from pathlib import Path
from PyQt5.QtCore import QSettings
from huggingface_hub import hf_hub_download, hf_hub_url
import requests
from ctransformers import AutoModelForCausalLM
import torch

# ---------------- Model Download Settings  ---------------- #
AVAILABLE_MODELS = {
    "Phi-3-mini-instruct": {
        "repo": "QuantFactory/Phi-3-mini-4k-instruct-GGUF",
        "quant": "Phi-3-mini-4k-instruct.Q4_K_M.gguf",
        # This can be either a folder OR a full file path. If it's a file path, the loader will use it directly.
        "model_path": r"F:\Experiments\A.T.O.M\models\Phi-3-mini-instruct\Phi-3-mini-4k-instruct.Q4_K_M.gguf",
    },
    "Phi-4-mini-instruct": {
        "repo": "QuantFactory/phi-4-GGUF",
        "quant": "Phi-4-mini-instruct-Q4_K_S.gguf",
        "model_path": None,
    },
}

llm_instance = None  # Global cached LLM instance


# ---------------- Helpers ---------------- #
def get_user_settings():
    settings = QSettings("A.T.O.M", "Config")
    model_choice = settings.value("model_choice", "Phi-3-mini-instruct")
    model_path = settings.value("model_path", None)
    return model_choice, model_path


def download_model_hf(model_name: str, save_dir: str = None, status_fn=None, progress_fn=None):
    """
    Download quantized model files from Hugging Face hub to a local folder.
    """
    info = AVAILABLE_MODELS.get(model_name)
    if not info:
        if status_fn:
            status_fn(f"❌ Unknown model '{model_name}'.")
        return False

    repo_id = info["repo"]
    quant_file = info["quant"]
    base_dir = Path(save_dir or (Path.home() / "A.T.O.M" / "models")) / model_name
    base_dir.mkdir(parents=True, exist_ok=True)

    try:
        url = hf_hub_url(repo_id, quant_file)
    except Exception as e:
        if status_fn:
            status_fn(f"❌ Could not get file URL: {e}")
        return False

    local_file = base_dir / quant_file
    if status_fn: status_fn(f"📥 Downloading {quant_file} ...")

    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            chunk_size = 1024 * 1024
            with open(local_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_fn and total > 0:
                            progress = int(downloaded / total * 100)
                            progress_fn(progress)

        if status_fn: status_fn(f"✅ Download complete: {quant_file}")
        if progress_fn:
            progress_fn(100)
        return True

    except Exception as e:
        if status_fn: status_fn(f"❌ Failed to download model: {e}")
        return False


def find_local_gguf(model_name: str, save_dir: str = None):
    """
    Return Path to a local GGUF file for model_name or None.
    Handles cases where AVAILABLE_MODELS[].model_path may be a file path or a folder.
    """
    info = AVAILABLE_MODELS.get(model_name)
    if not info:
        return None

    # If explicit model_path configured in AVAILABLE_MODELS, use it directly
    model_path = info.get("model_path")
    if model_path:
        p = Path(model_path)
        if p.is_file():
            return p
        # if it's a folder, search inside
        if p.is_dir():
            ggufs = list(p.glob("*.gguf"))
            if ggufs:
                return ggufs[0]

    # fallback: look in default save_dir / model_name folder
    base_dir = Path(save_dir or (Path.home() / "A.T.O.M" / "models")) / model_name
    if not base_dir.exists():
        return None
    ggufs = list(base_dir.glob("*.gguf"))
    if ggufs:
        return ggufs[0]
    return None


# ---------------- Load Model ---------------- #
def load_model(model_name: str = None, save_dir: str = None, status_fn=None, device: str = None):
    """
    Load the GGUF model using ctransformers.AutoModelForCausalLM.
    device: None (auto), 'cpu' or 'cuda' to force.
    """
    global llm_instance
    if llm_instance is not None:
        if status_fn: status_fn("✅ Model already loaded (cached).")
        return llm_instance

    model_choice, custom_path = get_user_settings()
    model_name = model_name or model_choice
    info = AVAILABLE_MODELS.get(model_name)
    if not info:
        raise ValueError(f"Model '{model_name}' not in AVAILABLE_MODELS")

    # locate local GGUF file (handles file or folder)
    local_file = find_local_gguf(model_name, save_dir=save_dir)
    if not local_file:
        if status_fn: status_fn("⚠️ Model not found locally — attempting to download...")
        success = download_model_hf(model_name, save_dir=save_dir, status_fn=status_fn)
        if not success:
            raise RuntimeError(f"❌ Could not download model {model_name}.")
        local_file = find_local_gguf(model_name, save_dir=save_dir)
        if not local_file:
            raise RuntimeError(f"❌ Model still not found after download attempt: {model_name}")

    if status_fn: status_fn(f"📦 Loading model from '{local_file}' ...")

    # Decide device: prefer CPU if user forced 'cpu' or torch reports no GPU or device override
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    safe_gpu_layers = 0
    if device == "cuda":
        # conservative default — you can increase after testing
        safe_gpu_layers = 15  # number of layers on GPU; rest on CPU 
        #------------------------------------------#
        # log-08-11-2025 FIXED MEMORY ACCESS ISSUE #
        #    TO DO: Find Sweet spot for my GPU     #
        # -----------------------------------------#      
    else:
        safe_gpu_layers = 0

    # Try loading with GPU (if requested) and if that fails, fallback to CPU
    try:
        llm_instance = AutoModelForCausalLM.from_pretrained(
        str(local_file),
        model_type="phi",
        gpu_layers=safe_gpu_layers,
        context_length=4096,    # 4096 allow longer responses (prevents truncation max phi3 quant can handle)
        )
        if status_fn: status_fn(f"✅ Model loaded successfully ({model_name}) on device={device} gpu_layers={safe_gpu_layers}")
        return llm_instance

    except Exception as e_gpu:
        # GPU load failed — FALLBACK to CPU
        if status_fn:
            status_fn(f"⚠️ Loading on GPU failed: {e_gpu}. Retrying on CPU (gpu_layers=0)...")
        try:
            llm_instance = AutoModelForCausalLM.from_pretrained(
            str(local_file),
            model_type="phi",
            gpu_layers=0,
            context_length=4096,     # also for CPU fallback
        )
            if status_fn:
                status_fn(f"✅ Model loaded successfully ({model_name}) on CPU (gpu_layers=0).")
            return llm_instance
        except Exception as e_cpu:
            # both attempts failed — raise with both traces
            raise RuntimeError(f"Failed loading model on GPU and CPU.\nGPU error: {e_gpu}\nCPU error: {e_cpu}")

# ---------------- Set Manual Model Path ---------------- #
def set_manual_model_path(model_name: str, folder_path: str, status_fn=None):
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        if status_fn: status_fn(f"❌ Folder '{folder_path}' does not exist.")
        return False

    gguf_files = list(folder.glob("*.gguf"))
    if not gguf_files:
        if status_fn: status_fn(f"❌ No .gguf files found in '{folder_path}'.")
        return False

    if model_name in AVAILABLE_MODELS:
        AVAILABLE_MODELS[model_name]["model_path"] = str(folder)
    else:
        AVAILABLE_MODELS[model_name] = {
            "repo": None,
            "quant": None,
            "model_path": str(folder)
        }

    settings = QSettings("A.T.O.M", "Config")
    settings.setValue("model_path", str(folder))
    settings.setValue("model_choice", model_name)

    if status_fn: status_fn(f"✅ Model path set for '{model_name}': {folder_path}")
    return True


# ---------------- Generate Response ---------------- #
def get_response_from_atom(prompt, max_tokens=1024, temperature=0.7, top_p=0.9, device: str = None):
    """
    Generate text using the loaded model. Provide `device='cpu'` to force CPU inference for testing.
    """
    model = load_model(device=device)
    # ctransformers models are callable; calling returns a string
    try:
        return model(prompt, max_new_tokens=max_tokens, temperature=temperature, top_p=top_p)
    except Exception as e:
        # If model call fails, raise a clearer error
        raise RuntimeError(f"Error during model generate: {e}")


# ------------- quick test helper (FOR TESTING ONLY) -------------- #
def test_model(prompt="Hello, test!", device="cpu"):
    try:
        print("Loading model (test)...")
        m = load_model(device=device)
        print("Running test inference...")
        out = get_response_from_atom(prompt, device=device)
        print("Model output:", out)
        return True
    except Exception as e:
        print("Test failed:", e)
        return False
