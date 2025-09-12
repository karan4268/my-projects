import os
import psutil
import time
import subprocess

# modules
from voice_atom import listen_to_user
from tts_atom import speak_response
from local_engine import get_response_from_atom, stream_response_from_atom
from command import handle_command
from stream_respo import StreamingChat  # new module

mic_enabled = False  # Controlled by UI toggle
ollama_process = None

# --------------------------------------------------------
# Check if Ollama is already running
# --------------------------------------------------------
def is_ollama_running():
    for proc in psutil.process_iter(['name', 'cmdline']):
        if proc.info['name'] and "ollama" in proc.info['name'].lower():
            return True
    return False

# --------------------------------------------------------
# Start Ollama (GUI or CLI)
# --------------------------------------------------------
def start_ollama(print_fn=print):
    global ollama_process
    if not is_ollama_running():
        ollama_cli_path = r"C:\\Users\\karan\\AppData\\Local\\Programs\\Ollama\\ollama.exe"
        ollama_path = r"C:\\Users\\karan\\AppData\\Local\\Programs\\Ollama\\ollama app.exe"

        if os.path.exists(ollama_path):
            ollama_process = subprocess.Popen([ollama_path], shell=True)
            print_fn("👉 Starting Ollama App...")
            time.sleep(5)
        elif os.path.exists(ollama_cli_path):
            ollama_process = subprocess.Popen([ollama_cli_path], shell=True)
            print_fn("👉 Starting Ollama CLI...")
            time.sleep(5)
        else:
            print_fn(":( Ollama not found at expected paths.")
    else:
        print_fn("^_^ Ollama is already running.✔️")

# --------------------------------------------------------
# Stop Ollama gracefully when exiting
# --------------------------------------------------------
def stop_ollama():
    global ollama_process
    try:
        if ollama_process and ollama_process.poll() is None:
            ollama_process.terminate()
            ollama_process.wait(timeout=3)
            print("🛑 Ollama terminated gracefully.")
    except Exception as e:
        print(f"⚠️ Error stopping Ollama: {e}")
    finally:
        # Force kill if still running
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and "ollama" in proc.info['name'].lower():
                proc.kill()
                print("Ollama process stopped.")

# --------------------------------------------------------
# Streaming Chat Setup
# --------------------------------------------------------
chat = StreamingChat(enable_tts=True, ui_callback=print)

# --------------------------------------------------------
# Process query
# --------------------------------------------------------
def process_query(query):
    if not query.strip():
        return "⚠️ Empty command."

    # First try command execution
    command_response = handle_command(query)
    if command_response:
        speak_response(command_response)  # commands stay instant
        return f"A.T.O.M says: {command_response}"

    # Otherwise stream LLM response
    print("🤖 A.T.O.M is thinking...\n")
    chat.stream_chat(query)
    return "✅ Response completed."

# --------------------------------------------------------
# Microphone control
# --------------------------------------------------------
def toggle_microphone(state):
    global mic_enabled
    mic_enabled = state
    if mic_enabled:
        print("🎙️ Mic enabled. Listening...")
        run_voice_loop()
    else:
        print("🎙️ Mic disabled.")

def run_voice_loop():
    global mic_enabled
    while mic_enabled:
        query = listen_to_user()
        if query:
            process_query(query)

# --------------------------------------------------------
# Entry
# --------------------------------------------------------
def main():
    start_ollama()
    try:
        run_voice_loop()
    except KeyboardInterrupt:
        stop_ollama()
        chat.shutdown()
        print("🛑 Exited by user.")

# if __name__ == "__main__":
#     main()
