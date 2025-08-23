import os
import subprocess
import webbrowser
import datetime
import psutil
import difflib
import win32com.client
from PyQt5 import QtCore  # ✅ Needed for processEvents()
from chat_atom import OllamaWorker as chat_with_ollama
from tts_atom import speak_response
from voice_atom import listen_to_user  
import threading

# --- Global reference to terminal widget for interactive commands --- #
terminal_widget_ref = None  # Will be set from UI_ATOM

# --- Voice mode --- #
def start_voice_mode(terminal_panel):
    """
    Starts non-blocking voice mode.
    `terminal_panel` must be TerminalChat instance with `append_message(str)` signal-safe.
    """
    def _voice_loop():
        import voice_atom  # local mic listener
        terminal_panel.append_message("🟢 Voice mode activated. Say 'exit' to quit.\n")
        stop_flag = False

        def _callback(text):
            nonlocal stop_flag
            if not text:
                terminal_panel.append_message("⚠️ No speech detected.\n")
                return

            terminal_panel.append_message(f"🎤 You said: {text}\n")

            if text.lower().strip() in ["exit", "quit", "stop listening"]:
                terminal_panel.append_message("🛑 Exiting voice mode.\n")
                stop_flag = True
                return

            # first try hardwired commands
            resp = handle_command(text)
            if resp:
                terminal_panel.append_message(f"A.T.O.M: {resp}\n")
                threading.Thread(target=lambda: speak_response(resp), daemon=True).start()
            else:
                # fallback to LLM
                def do_ai(q):
                    try:
                        reply = chat_with_ollama(q)
                        terminal_panel.append_message(f"🗨️ A.T.O.M says: {reply}\n")
                        threading.Thread(target=lambda: speak_response(reply), daemon=True).start()
                    except Exception as e:
                        terminal_panel.append_message(f"⚠️ LLM error: {e}\n")
                threading.Thread(target=do_ai, args=(text,), daemon=True).start()

        # start mic listener (non-blocking)
        voice_atom.start_listening(_callback)

        # keep thread alive until user says exit
        while not stop_flag:
            QtCore.QThread.msleep(100)

        # stop listening
        voice_atom.stop_listening()

    threading.Thread(target=_voice_loop, daemon=True).start()


# --- Custom app paths for specific apps --- #
custom_apps = {
    "discord": r"C:\Users\karan\AppData\Local\Discord\Update.exe --processStart Discord.exe --process-start-args --system-tray",
}

def launch_custom_app(name):
    exe = custom_apps.get(name.lower())
    if exe:
        if "--" in exe:
            subprocess.Popen(exe.split())
        else:
            if os.path.exists(exe):
                subprocess.Popen(exe)
            else:
                return f"Path not found for {name}."
        return f"Launching {name.capitalize()}"
    return None


# --- AppsFolder launcher (for Windows) --- #
def launch_app_from_appsfolder(app_name):
    app_name = app_name.lower().strip()
    shell = win32com.client.Dispatch("Shell.Application")
    folder = shell.Namespace("shell:AppsFolder")

    for item in folder.Items():
        name = item.Name.lower()
        if app_name in name:
            item.InvokeVerb("open")
            return f"Launching {item.Name}"
    return f"App '{app_name}' not found."


# --- Hardcoded command and responses --- #
def tell_time():
    now = datetime.datetime.now()
    return now.strftime("It is %A, %B %d, %I:%M %p.")

def search_google(command):
    query = command.lower().replace("search google for", "").strip()
    if query:
        webbrowser.open(f"https://www.google.com/search?q={query}")
        return f"Searching Google for {query}"
    return "What should I search for? Please specify your query and try again."

def greetings():
    return "Hello! I am ATOM. How can I help you today?"

def battery_status():
    battery = psutil.sensors_battery()
    if battery:
        return f"Battery is at {battery.percent}%."
    return "Battery info not available."

def system_status():
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    return f"CPU usage is {cpu}%, RAM usage is {ram}%."

def info_about_atom():
    return "I am ATOM, a LLM based on Microsoft's PHI-3 model. How can I assist you today?"
    

# --- Command dictionary --- #
command_map = {
    "what's the time": tell_time,
    "what time is it": tell_time,
    "what's today's date": tell_time,
    "hello": greetings,
    "hi": greetings,
    "hey": greetings,
    "battery percentage": battery_status,
    "battery info": battery_status,
    "battery status": battery_status,
    "system status": system_status,
    "system info": system_status,
    "sys info": system_status,
    "sys status": system_status,
    "who are you?": info_about_atom,

}


# --- Main command handler (✅ only one now) --- #
def handle_command(text):
    text = text.lower().strip()

    # --- Exact command map lookup --- #
    if text in command_map:
        return command_map[text]()

    # --- Fuzzy match for similar hardwired commands --- #
    close = difflib.get_close_matches(text, command_map.keys(), n=1, cutoff=0.6)  
    if close:
        return command_map[close[0]]()

    # --- Voice mode ---

    if text == "voice mode":
        if terminal_widget_ref:
            # Run in background thread to avoid freezing UI
            threading.Thread(target=lambda: start_voice_mode(terminal_widget_ref), daemon=True).start()
            return "Voice mode started."
        else:
            threading.Thread(target=start_voice_mode, daemon=True).start()
            return "Voice mode started in console."


    # --- App launching --- #
    if text.startswith(("open", "launch", "start")):
        app_name = (
            text.replace("open ", "")
            .replace("launch ", "")
            .replace("start ", "")
            .strip()
        )
        result = launch_custom_app(app_name)
        if result:
            return result
        return launch_app_from_appsfolder(app_name)

    # --- Search --- #
    if text.startswith("search google for"):
        return search_google(text)

    return None
