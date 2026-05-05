import os
import subprocess
import sys
import webbrowser
import datetime
import psutil
import difflib
import win32com.client # For COM interaction with Windows Shell to open apps from windows virtual AppsFolder
import pythoncom # For COM initialization
import time
from PyPDF2 import PdfReader  # for PDF text extraction
from docx import Document # for DOCX text extraction

# --- Global reference to terminal widget for interactive commands --- #
terminal_widget_ref = None  # Will be set from UI_ATOM
# --- Custom app paths for specific apps --- #
custom_apps = {
    "discord": r"C:\Users\karan\AppData\Local\Discord\Update.exe --processStart Discord.exe --process-start-args --system-tray",# for example only , discord can also be launched using windows virtual appsfolder
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
def launch_app_from_appsfolder(app_name: str):
    app_name = app_name.lower().strip()

    # Initialize COM for this thread
    pythoncom.CoInitialize()
    try:
        shell = win32com.client.Dispatch("Shell.Application")
        folder = shell.Namespace("shell:AppsFolder")

        for item in folder.Items():
            name = item.Name.lower()
            if app_name in name:
                item.InvokeVerb("open")
                return f"Launching {item.Name}"

        return f"App '{app_name}' not found."
    finally:
        # Always uninitialize to avoid leaks
        pythoncom.CoUninitialize()

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
    return "I am ATOM, an AI assistant which can help you with various tasks from simple queries to complex problem-solving. type /help to see what I can do!"
def quit():
    time.sleep(0.5)  # Delay for 0.5 seconds before exit
    sys.exit(0)

# --- Command dictionary --- #
command_map = {
    "time": {
        "triggers": ["what's the time", "what time is it", "what's today's date"],
        "handler": tell_time
    },
    "greeting": {
        "triggers": ["hello", "hi", "hey"],
        "handler": greetings
    },
    "battery": {
        "triggers": ["battery info", "battery status", "battery percentage"],
        "handler": battery_status
    },
    "system": {
        "triggers": ["sys info", "system information", "system info", "sys status", "system status"],
        "handler": system_status
    },
    "identity": {
        "triggers": ["who are you?"],
        "handler": info_about_atom
    },
    "exit": {
        "triggers": ["quit", "exit", "bye", "shutdown"],
        "handler": quit
    },
}
def handle_command(text):
    text = text.lower().strip()

    # --------------------------------------------------
    # 1. Exact trigger match
    # --------------------------------------------------
    for cmd in command_map.values():
        if text in cmd["triggers"]:
            return cmd["handler"]()

    # --------------------------------------------------
    # 2. Fuzzy match (typo tolerance)
    # --------------------------------------------------
    all_triggers = []
    trigger_to_cmd = {}

    for cmd in command_map.values():
        for trig in cmd["triggers"]:
            all_triggers.append(trig)
            trigger_to_cmd[trig] = cmd

    import difflib
    close = difflib.get_close_matches(text, all_triggers, n=1, cutoff=0.65)
    if close:
        return trigger_to_cmd[close[0]]["handler"]()

    # --------------------------------------------------
    # 3. Partial intent match
    # --------------------------------------------------
    for cmd in command_map.values():
        for trig in cmd["triggers"]:
            if trig in text:
                return cmd["handler"]()

    # --------------------------------------------------
    # 4. App launching
    # --------------------------------------------------
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

    # --------------------------------------------------
    # 5. Web search
    # --------------------------------------------------
    if text.startswith("search google for"):
        return search_google(text)

    # --------------------------------------------------
    # 6. No match → fallback
    # --------------------------------------------------
    return None