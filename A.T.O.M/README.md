# A.T.O.M – ADVANCED TASK ORIENTED MODEL

A.T.O.M (Advanced Task Oriented Model) is a local AI assistant designed to run fully offline on Windows PCs.
Inspired by futuristic aesthetics, A.T.O.M combines voice recognition, speech synthesis, and intelligent agentic task execution with a visually stunning interface.
It leverages **two local LLM models** for planning, reasoning, and conversation — with no cloud services required.

> ⚠️ This project is under active development. Some features are still a work in progress.

---

# What's New in v3 ✨

- **Dual-Model Architecture** — Mistral-7B handles agentic planning; Phi-3/4 handles conversation and synthesis
- **ReAct Agent Loop** — A full Thought → Action → Observation loop with up to 4 steps per query
- **7 Built-in Tools** — web search, file I/O, code review, shell, calculator, system commands, and memory
- **Keyword Router** — fast pre-filter that maps your query to the right tool before hitting the LLM
- **Code Review Tool** — reviews Python, JavaScript, and C++ files against language-specific standards
- **Memory Tool** — store and recall facts across sessions
- **Safe Shell Executor** — whitelist-only read-only shell commands with blocked destructive patterns
- **Forced Tool Injection** — if the model skips a tool call it should have made, the agent retries automatically
- **Scratchpad Synthesis** — if the loop exhausts steps without a final answer, Phi synthesises one from observations

---

# Features ✨

- **Voice Interaction** — speak naturally to A.T.O.M and receive intelligent spoken responses
- **Dual Local LLM Integration** — Mistral-7B-Instruct-v0.3 (GPU, planner) + Phi-3/4-mini (CPU, synthesiser)
- **Agentic Task Execution** — multi-step ReAct loop with tool chaining for complex queries
- **7 Tools Available**:
  - `web_search` — real-time web queries
  - `file` — read, write, append, and list files on disk
  - `code_review` — LLM-powered code review for Python, JS, C++
  - `shell` — safe, read-only shell command execution
  - `calculate` — maths and unit conversion expressions
  - `system_command` — open apps, take screenshots, check battery, control volume
  - `memory` — store and recall facts between sessions
- **Command Execution** — open applications and automate system tasks via natural language
- **Futuristic UI** — neon and glass-style interface with animated circular progress bars (PyQt5)
- **Resource Monitoring** — real-time CPU and RAM monitoring with waveform visualisation
- **Chat Mode** — terminal-style chat panel for keyboard interaction
- **Fully Offline** — no data leaves your system; privacy-first by design
- **Customisable** — easily change themes, layouts, and LLM parameters

---

# Architecture 🧠

```
User Query
    │
    ▼
Keyword Router  ──── conversational? ──►  Phi-3/4 (CPU)  ──►  Response
    │
    ▼ agentic?
Mistral-7B (GPU)
    │
    ▼
ReAct Loop  (up to 4 steps)
  Thought → ACTION → OBSERVATION → repeat
    │
    ▼
Phi-3/4 (CPU)  ──  Synthesise final answer
```

**Why two models?**
Phi-3/4 quants are fast and great at conversation but unreliable at structured JSON tool calls inside a loop.
Mistral-7B-Instruct-v0.3 Q4_K_M (~4 GB) fits in 6–8 GB VRAM and produces stable tool-call JSON.
Phi handles everything that doesn't need the loop, keeping GPU memory free.

---

# Screenshots 📸

## 🔶 Splash Screen

![Splash Screen](https://github.com/user-attachments/assets/b19c057d-22ac-4999-84d4-c28056a10c9e)

## 🔶 Main UI

![A.T.O.M Main UI](https://github.com/user-attachments/assets/39a61f7c-e2dc-44bd-968c-9f8927b529ab)
![New UI](https://github.com/user-attachments/assets/97e356d5-02dd-4be4-8787-6e3977059890)

## 🔶 System Monitoring

🔸 CPU Panel

![CPU Panel](https://github.com/user-attachments/assets/eb165125-125a-4ec4-913f-8e1669e4ad0d)

🔸 RAM Panel

![RAM Panel](https://github.com/user-attachments/assets/d76412fa-b607-44ee-9ef4-0f7bd28dc975)

## 🔶 Terminal / Chat Window and Responses

![Chat Mode](https://github.com/user-attachments/assets/4a370a32-b28d-4b91-825c-7651a07c389b)
![Chat Mode](https://github.com/user-attachments/assets/d7f8f30f-a95a-437a-86c5-b5dfeb8479aa)

---

# ▶️ A.T.O.M Features Demo

> Video demo coming soon.

---

# ♦️ Installation

## 1. Prerequisites

- Python 3.10+
- CUDA-capable GPU recommended (6–8 GB VRAM for Mistral on GPU)
- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) built with CUDA support

## 2. Clone the repository

```bash
git clone https://github.com/karan4268/ATOM.git
cd ATOM
```

## 3. Create a virtual environment

```bash
python -m venv atom-env
atom-env\Scripts\activate   # Windows
```

## 4. Install dependencies

```bash
pip install -r requirements.txt
```

## 5. Download models

Place your GGUF model files in the `models/` directory:

```
models/
  Phi-3-mini-instruct/
    Phi-3-mini-4k-instruct.Q4_K_M.gguf      ← CPU model (conversation & synthesis)
  Mistral-7B-Instruct/
    Mistral-7B-Instruct-v0.3-Q4_K_M.gguf    ← GPU model (agent planner)
```

Both models are available on [HuggingFace](https://huggingface.co) in GGUF format.

## 6. Run

```bash
python UI_atom.py
```

---

# ♦️ Usage

| Mode | How to use |
|------|-----------|
| **Voice** | Click the microphone button and speak your query |
| **Chat** | Type commands in the terminal-style chat widget |
| **File tasks** | `summarise file \| C:/path/to/file.txt` |
| **Code review** | `review code in file \| C:/path/to/script.py` |
| **Web search** | `search for latest news on X` |
| **Calculate** | `calculate (42 * 3.14) / 2` |
| **System** | `open notepad`, `take a screenshot`, `check battery` |
| **Memory** | `remember my project is called ATOM` / `recall project name` |
| **Shell** | `run command ipconfig` |
| **System Monitoring** | Click circular progress bars to view CPU or RAM waveforms |

---

# ♦️ Dependencies

- Python 3.10+
- PyQt5
- llama-cpp-python (with CUDA support recommended)
- pyttsx3 (or alternative TTS engine)
- psutil
- Other packages listed in `requirements.txt`

---

# ♦️ Project Structure

```
A.T.O.M/
├── UI_atom.py              # Main PyQt5 UI entry point
├── agent.py                # ReAct agent loop + keyword router
├── agent_model.py          # Mistral wrapper (GPU planner)
├── local_engine.py         # Phi wrapper (CPU synthesiser)
├── command.py              # System command handler
├── tools/
│   ├── web_search.py
│   ├── file_tool.py
│   ├── code_review.py
│   ├── shell_tool.py
│   ├── calculator.py
│   └── memory_tool.py
└── models/                 # Place GGUF models here
```

---

# ♦️ Contributing

Contributions are welcome! You can:

- Improve the UI/UX
- Add new voice commands or tools
- Optimise system monitoring
- Add support for additional local LLMs
- Improve the ReAct loop reliability

Please fork the repository and submit a pull request.

---

# ♦️ Roadmap

- [ ] Long-term memory with vector search
- [ ] Multi-step file editing (read → modify → write)
- [ ] Plugin system for custom tools
- [ ] Linux/macOS support
- [ ] Smaller footprint single-model mode

---

# Contact

**Created by Karandeep Chadda**

- GitHub: [github.com/karan4268](https://www.github.com/karan4268)
- Email: karandeepchadda@gmail.com
