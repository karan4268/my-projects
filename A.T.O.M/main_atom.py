import os
import psutil
import time
import subprocess
import sys
# modules
from voice_atom import listen_to_user
from tts_atom import speak_response
from local_engine import get_response_from_atom
from command import handle_command

mic_enabled = False  # Controlled by UI toggle

# Check if Ollama is already running
def is_ollama_running():
    for proc in psutil.process_iter(['name', 'cmdline']):
        if proc.info['name'] and "ollama" in proc.info['name'].lower():
            return True
    return False

# Start Ollama GUI or CLI (in splash/ startup screen)
def start_ollama(print_fn=print):  # default to print if not provided
    if not is_ollama_running():
        ollama_cli_path = r"C:\\Users\\karan\\AppData\\Local\\Programs\\Ollama\\ollama.exe"
        ollama_path = r"C:\\Users\\karan\\AppData\\Local\\Programs\\Ollama\\Ollama app.exe"
        if os.path.exists(ollama_path):
            subprocess.Popen([ollama_path], shell=True)
            print_fn("👉 Starting Ollama GUI...")
            time.sleep(5)
        elif os.path.exists(ollama_cli_path):
            subprocess.Popen([ollama_cli_path], shell=True)
            print_fn("👉 Starting Ollama CLI...")
            time.sleep(5)
        else:
            print_fn("❌ Ollama not found at expected paths.")
    else:
        print_fn("✅ Ollama is running.")



# Process command or query (test input field in terminal widget)
def process_query(query):
    if not query.strip():
        return "⚠️ Empty command."

    # Exit command voice or text input
    if query.lower() in ["exit", "quit", "shutdown", "stop", "goodbye"]:
        speak_response("Shutting down A.T.O.M. Goodbye!")
        print("🗨️ A.T.O.M says: Session ended.")
        sys.exit(0)  # Hard exit to prevent LLM from processing exit as input 

    # Command execution first 
    command_response = handle_command(query)
    if command_response:
        speak_response(command_response)
        return f"🗨️ A.T.O.M says: {command_response}"

    # Fallback to LLM if command not recognized
    ai_response = get_response_from_atom(query)
    speak_response(ai_response)
    return f"🗨️ A.T.O.M says: {ai_response}"

# Toggle microphone from UI
def toggle_microphone(state):
    global mic_enabled
    mic_enabled = state
    if mic_enabled:
        print("🎙️ Mic enabled. Listening...")
        run_voice_loop()
    else:
        print("🎙️ Mic disabled.")

# Continuous listening loop
def run_voice_loop():
    global mic_enabled
    while mic_enabled:
        query = listen_to_user()
        if query:
            process_query(query)

# CLI entry
def main():
    start_ollama()
    run_voice_loop()

# if __name__ == "__main__":
#     main()
