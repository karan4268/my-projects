# A.T.O.M – ADVANCED TASK ORIENTED MODEL

A.T.O.M (Advanced Task Oriented Model) is a local AI assistant designed to run fully offline on Windows PCs.
Inspired by futuristic aesthetics, A.T.O.M combines voice recognition, speech synthesis, and intelligent agentic task execution with a visually stunning interface.
It leverages **two local LLM models** for planning, reasoning, and conversation — with no cloud services required.

> ⚠️ This project is under active development. Some features are still a work in progress.

---

# What's New in v3 ✨

- **Dual-Model Architecture** — Mistral-7B handles agentic planning; Phi-3 handles conversation and synthesis
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

# Architecture Overview 

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
Synthesise final answer
```

**Why two models?**
Phi-3 quants are fast and great at conversation but unreliable at structured JSON tool calls inside a loop.
Mistral-7B-Instruct-v0.3 Q4_K_M (~4 GB) fits in 6–8 GB VRAM and produces stable tool-call JSON.
you can use any agentic model instead of Mistral
Phi handles everything that doesn't need the loop, keeping GPU memory free.

---

# Screenshots 📸

## 🔶 Splash Screen

![Splash Screen](https://github.com/user-attachments/assets/9e0b61d6-be82-4d8e-ac17-5ca4f588f970)

## 🔶 Main UI

![A.T.O.M Main UI](https://github.com/user-attachments/assets/0af75a10-223e-4135-a613-b1ee5e6955e3)
![New Settings panel](https://github.com/user-attachments/assets/6f4a453f-5efc-4de7-a758-a59105bd8a2c)

## 🔶 System Monitoring

🔸 CPU Panel

![CPU Panel](https://github.com/user-attachments/assets/eb165125-125a-4ec4-913f-8e1669e4ad0d)

🔸 RAM Panel

![RAM Panel](https://github.com/user-attachments/assets/d76412fa-b607-44ee-9ef4-0f7bd28dc975)

## 🔶 Terminal / Chat Window and Responses
![New Agentic Loop](https://github.com/user-attachments/assets/e891160f-a261-48c2-ba82-71be92af9cd8)
![](https://github.com/user-attachments/assets/008558a7-f2bf-4978-8b27-2e914c18c6ec)
![light coding](https://github.com/user-attachments/assets/398b328f-9b5c-433d-9da1-899b81536998)
![Chat Mode](https://github.com/user-attachments/assets/f548b9f4-d3a7-4bf3-915c-69634d6a5b66)
![Chat Mode](https://github.com/user-attachments/assets/67ca33d0-cbc9-46a8-9217-13e07d8861a9)

---

# ▶️ A.T.O.M Features Demo

> Video demo coming soon.

---

# ♦️ Installation

## 1. Prerequisites

- Python 3.10+
- CUDA-capable GPU recommended (4GB minimum and 6–8 GB VRAM Recommend for Mistral on GPU)
- note:-
- change model Token and context values in local_engine.py and Agent.py if your GPU has more VRAM.
- You can also run Phi on GPU but its not stable due to ctransformers threading issues with two GGUF models on windows.
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
