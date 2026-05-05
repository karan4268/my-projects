import time

# modules
from voice_atom import listen_to_user
from tts_atom import speak_response
from local_engine import get_response_from_atom, load_model
from command import handle_command

mic_enabled = False  # Controlled by UI toggle


# --------------------------------------------------------
# Load the local model (downloads on first run)
# --------------------------------------------------------
print("🔽 Checking / downloading Phi-3 Mini model...")
load_model()   # ensures model & tokenizer are ready
print("✅ Model ready!\n")


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

    # Otherwise get full LLM response
    print("\n🤖 A.T.O.M is thinking...\n")
    response = get_response_from_atom(query)
    print(response)
    if response.strip():
        speak_response(response)
    print("\n[Response complete]\n")
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
# Entry point
# --------------------------------------------------------
def main():
    try:
        run_voice_loop()
    except KeyboardInterrupt:
        print("🛑 Exited by user.")
