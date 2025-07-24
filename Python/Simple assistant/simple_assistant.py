import sys
import os
import time
import datetime
import webbrowser
import speech_recognition as sr
import pyttsx3
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt

# Initialization
engine = pyttsx3.init()

#Voice properties defalut at launch
voices = engine.getProperty('voices')  
engine.setProperty('voice', voices[1].id)  # Change to voice to male or female (0 for male/1 for female)
engine.setProperty('rate', 190)  #  speaking rate
engine.setProperty('volume', 0.7)  #  0.0 (mute)  1.0 (max)

# --- Voice Assistant Logic ---#
# -- Settings Dialog -- #
class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(400, 300)

        layout = QtWidgets.QVBoxLayout()

        # Voice selection
        self.voice_label = QtWidgets.QLabel("Select Voice:")
        self.voice_combo = QtWidgets.QComboBox()
        self.voice_combo.addItems(["Male", "Female"])
        layout.addWidget(self.voice_label)
        layout.addWidget(self.voice_combo)

        # Rate slider
        self.rate_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.rate_slider.setMinimum(100)
        self.rate_slider.setMaximum(300)
        self.rate_slider.setValue(engine.getProperty("rate"))
        layout.addWidget(QtWidgets.QLabel("Speech Rate:"))
        layout.addWidget(self.rate_slider)

        # Volume slider
        self.volume_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(1)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(int(engine.getProperty("volume") * 100))
        layout.addWidget(QtWidgets.QLabel("Volume:"))
        layout.addWidget(self.volume_slider)

        # Close
        self.close_btn = QtWidgets.QPushButton("Close")
        layout.addWidget(self.close_btn)

        self.setLayout(layout)

        self.close_btn.clicked.connect(self.accept)

#-- main Logic class --#
class VoiceAssistantApp:
    #--settings and values --#
    def update_voice_label(self):
        current = self.voice_combo.currentText()
        self.voice_label.setText(f"Voice: {current}")
        voices = engine.getProperty('voices')
        engine.setProperty('voice', voices[0].id if current == "Male" else voices[1].id)

    def update_rate_label(self):
        rate = self.rate_slider.value()
        self.rate_label.setText(f"Speech Rate: {rate}")
        engine.setProperty('rate', rate)

    def update_volume_label(self):
        volume = self.volume_slider.value()
        self.volume_label.setText(f"Volume: {volume}%")
        engine.setProperty('volume', volume / 100)

# --- Function for listening and respond --- #
    def listen_and_respond(self):

        self.hide_settings_panel()  # Auto-collapse settings panel
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            self.response_label.setText("Listening...")
            QApplication.processEvents()  # Update the UI

            try:
                audio = recognizer.listen(source, timeout=5)
                command = recognizer.recognize_google(audio).lower()
                self.text_area.append(f"You said: {command}")
                self.response_label.setText(f"You said: {command}")
    
# dictionary of commands / Key words and corresponding actions
                commands = {
                    "open discord": self.open_discord,
                    "open settings panel": self.open_settings_panel,
                    "open windows settings": self.open_win_settings,
                    "open github": self.open_GitHub,
                    "what time is it": self.tell_time,
                    "what's the time": self.tell_time,
                    "search google for": self.search_google,
                    "close assistant": self.close_assistant,
                    "exit": self.close_assistant,
                    "hello": self.greetings,
                    "what's today's date": self.tell_time,
                    "battery percentage": self.battery_status,
                    "system status": self.system_status,
                    "resize window": self.resize_window,
                    "ask ai": self.ask_GPT4ALL,
                }

                # Check if the command exists in the dictionary and call the associated function
                for key, action in commands.items():
                    if key in command:
                        action(command)
                        return  # Exit after processing the command

                # If no command is recognized, use GPT4All
                response = self.ask_local_ai(command)
                self.response_label.setText(response)
                self.text_area.append(f"AI: {response}")
                engine.say(response)
                engine.runAndWait()

            except sr.UnknownValueError:
                self.response_label.setText("Sorry, I didn't Get That.")
            except sr.RequestError:
                self.response_label.setText("Error with speech services.")
            except sr.WaitTimeoutError:
                self.response_label.setText("Timed out :( Please try again.")
                QApplication.processEvents()  # Update the UI
                time.sleep(1)  # Wait 1 seconds before resetting
                self.start_button.clicked.connect(self.listen_and_respond)  # Reset the button function
            return
    

# Define functions for each command
    def ask_GPT4ALL(self, command):
        prompt = command.replace("ask ai", "").strip()
        reply = self.ask_local_ai(prompt)
        self.response_label.setText(reply)
        #--- AI repones in the text area
        self.text_area.append(f"<b>You:</b> {prompt}")
        self.text_area.append(f"<b>AI:</b> {reply}")

        engine.say(reply)
        engine.runAndWait()
        return

    def open_discord(self, command):
        self.response_label.setText("Opening Discord...")
        os.system(r"C:\Users\karan\AppData\Local\Discord\Update.exe --processStart Discord.exe --process-start-args --system-tray")  
        # Opens Discord
        # Opens Discord, the path may vary
        # If discord is not in the PATH, you can specify the full path like this:
        # os.system(r"C:\Path\To\Discord.exe")
        engine.say("Opening Discord")
        engine.runAndWait()
        return

#windows settings
    def open_win_settings(self, command):
        self.response_label.setText("Opening Windows Settings...")
        os.system("start ms-settings:")  # Opens Windows Settings
        engine.say("Opening Windows Settings")
        engine.runAndWait()
        return

    def open_settings_panel(self, command=None):
        self.toggle_settings_panel()
        engine.say("Opening settings panel")
        engine.runAndWait()
        return
#window resize
    def resize_window(self, command):
        self.response_label.setText("Resizing window to default size")
        engine.say("Resized window to default")
        self.setGeometry(100, 100, 500, 400)  # Resize the window to 500x400

#greetings
    def greetings(self, command):
        self.response_label.setText("Hello! How can I help you?😊")
        engine.say("Hello! How can I help you?")
        engine.runAndWait()
        return
    
# Opens GitHub in the default web browser
    def open_GitHub(self, command):
        self.response_label.setText("Opening GitHub...")
        webbrowser.open(f"https://www.gitHub.com/")  # Opens GitHub
        engine.say("Opening GitHub.com")
        engine.runAndWait()
        return

    def tell_time(self, command): #tell the current system time
        time_now = datetime.datetime.now().strftime("%H:%M")
        self.response_label.setText(f"The time is {time_now} & the date is {datetime.datetime.now().strftime('%d-%m-%Y')}")
        date = datetime.datetime.now().strftime("%d-%m-%Y")
        engine.say(f"The time is {time_now} & the date is {date}")
        engine.runAndWait()
        return

    def search_google(self, command): #search google for the query given by user
        query = command.replace("search google for", "").strip()
        webbrowser.open(f"https://www.google.com/search?q={query}")
        self.response_label.setText(f"Searching Google for {query}")
        engine.say(f"Searching Google for {query}")
        engine.runAndWait()
        return
    

    #system status
    def battery_status(self, command): #tell the battery status of the system
        import psutil
        battery = psutil.sensors_battery()
        self.response_label.setText(f"Your system is running on {battery.percent}% battery")
        engine.say(f"Your system is running on {battery.percent}% battery")
        if battery.percent <= 20:
            self.response_label.setText(f"Your battery is running low {battery.percent}%")
            engine.say(f"Your Battery is Low, at{battery.percent}% Consider Pluging a Charger")
        engine.runAndWait()
        return
    
    #system status
    def system_status(self, command): #tell the system status
        import psutil
        battery = psutil.sensors_battery()
        cpu_usage = psutil.cpu_percent()
        ram = psutil.virtual_memory()
        self.response_label.setText(f"Your system is running on {battery.percent}% battery, CPU usage is {cpu_usage}% and RAM is {ram.percent}% ")
        engine.say(f"Your system is running on {battery.percent}% battery, CPU usage is {cpu_usage}% and RAM is {ram.percent}%")
        engine.runAndWait()
        return

    def close_assistant(self, command):
        self.response_label.setText("Goodbye! ✌️")
        engine.say("Goodbye! Have a nice day!")
        engine.runAndWait()
        time.sleep(1)  # Delay before exiting
        QApplication.quit()  # Close the application
        return  # Exit the function
