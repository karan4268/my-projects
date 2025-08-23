
import os
import psutil
import time
import subprocess
from voice_atom import listen_to_user
from tts_atom import speak_response
from local_engine import get_response_from_atom
from command import handle_command

# Check if Ollama is already running
def is_ollama_running():
    for proc in psutil.process_iter(['name', 'cmdline']):
        if proc.info['name'] and "ollama" in proc.info['name'].lower():
            return True
    return False

# Start Ollama (either GUI or CLI)
def start_ollama(print_fn=print):
    if not is_ollama_running():
        ollama_path = r"C:\Users\karan\AppData\Local\Programs\Ollama\Ollama app.exe"
        ollama_cli_path = r"C:\Users\karan\AppData\Local\Programs\Ollama\ollama.exe"

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

# Single entry to handle input
def process_query(query, speak=True):
    command_response = handle_command(query)
    if command_response:
        if speak:
            speak_response(command_response)
        return command_response

    ai_response = get_response_from_atom(query)
    if speak:
        speak_response(ai_response)
    return ai_response

# full voice loop for standalone mode
def start_voice_loop():
    print("🔵 A.T.O.M is online. Say something...")
    while True:
        query = listen_to_user()
        if query.lower() in ["exit", "quit", "shutdown", "stop", "goodbye"]:
            speak_response("Shutting down ATOM. Goodbye!")
            break
        print(f">>> You said: {query}")
        print(process_query(query))

if __name__ == "__main__":
    start_ollama()
    start_voice_loop()
