import sys 
import speech_recognition as sr
import pyttsx3
import os
import webbrowser
import datetime
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QTextEdit
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt
import time

# Initialization
engine = pyttsx3.init()

#Voice properties
voices = engine.getProperty('voices')  
engine.setProperty('voice', voices[1].id)  # Change to voice to male or female (0 for male/1 for female)
engine.setProperty('rate', 160)  #  speaking rate
engine.setProperty('volume', 0.7)  #  0.0 (mute)  1.0 (max)

# GUI customizations
class VoiceAssistantApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('Simple Voice Assistant')  # title of the window
        self.setGeometry(100, 100, 500, 400)  # window size
        self.setWindowFlags(Qt.WindowStaysOnTopHint)  # Always on top
        # Make the window transparent and remove black borders
        self.setAttribute(Qt.WA_TranslucentBackground)  # Enables transparency
        self.setAttribute(Qt.WA_TranslucentBackground)  # Enable translucent background
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(122, 225, 195, 0.8);  /* Semi-transparent background */
                border-radius: 20px;  /* Rounded corners */
                color: white;
                font-size: 16px;
                font-weight: bold;
                border: 2px solid rgba(0, 0, 0, 0.1);  /* Semi-transparent border */
            }
        """)

        # UI Elements
        self.init_ui()

    def init_ui(self):
        # Layout
        layout = QVBoxLayout()
        self.adjustSize()

        # Display Area
        self.response_label = QLabel("Click '🎙️' and  Say Something", self)
        self.response_label.setAlignment(Qt.AlignCenter)
        self.response_label.setStyleSheet("""
        QLabel {
        color:#333;
        font-size: 20px;
        padding: 10px;
        border-radius: 15px;  /* Rounded corners */
    }
""")
        layout.addWidget(self.response_label)

        # Text Area for Display
        self.text_area = QTextEdit(self)
        self.text_area.setPlaceholderText(" Response History will be shown here...")
        self.text_area.setReadOnly(True)
        self.text_area.setStyleSheet("font-size: 17px;color: #333; padding: 10px;")  # Text area style
        layout.addWidget(self.text_area)

        # Buttons
        self.start_button = QPushButton("🎙️", self)
        #button style
        self.start_button.setStyleSheet("""
        QPushButton {
                background-color: rgba(112, 238, 202, 0.5);
                font-size: 20px; 
                font-weight: bold; 
                border-radius: 20px; 
                padding: 10px 20px;
                border: none; 
    }
        QPushButton:hover {
            background-color: rgba(122, 225, 195, 0.3);
        }
        QPushButton:pressed {
            background-color: rgba(142, 227, 203, 0.6);
    }
""")
        # listening button function
        self.start_button.clicked.connect(self.listen_and_respond)
        layout.addWidget(self.start_button)


        #Layout
        self.setLayout(layout)

# Function for listening and respond
    def listen_and_respond(self):
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
                    "open settings": self.open_settings,
                    "open github": self.open_GitHub,
                    "what time is it": self.tell_time,
                    "what's the time": self.tell_time,
                    "search google for": self.search_google,
                    "close assistant": self.close_assistant,
                    "exit": self.close_assistant,
                    "repeat what i say": self.repeat_command,
                    "hello": self.greetings,
                    "hi": self.greetings,
                    "What's up": self.greetings,
                    "what's today's date": self.tell_time,
                }

                # Check if the command exists in the dictionary and call the associated function
                for key, action in commands.items():
                    if key in command:
                        action(command)
                        return  # Exit after processing the command

                # If no command is recognized , repeat the user's input
                engine.say(f"You said: {command}")
                engine.runAndWait()
                return # Exit after processing the command

            except sr.UnknownValueError:
                self.response_label.setText("Sorry, I didn't Get That.")
            except sr.RequestError:
                self.response_label.setText("Error with speech services.")
            except sr.WaitTimeoutError:
                self.response_label.setText("Listening timed out. Please try again.")
                QApplication.processEvents()  # Update the UI
                time.sleep(1)  # Wait for 2 seconds before resetting
                self.start_button.clicked.connect(self.listen_and_respond)  # Reset the button function

    # Define functions for each command
    def open_discord(self, command):
        self.response_label.setText("Opening Discord...")
        os.system(r"C:\Users\karan\AppData\Local\Discord\Update.exe --processStart ""Discord.exe""") 
#can be changed according to the path of discord on your system
        engine.say("Opening Discord")
        engine.runAndWait()

    def open_settings(self, command):
        self.response_label.setText("Opening Windows Settings...")
        os.system("start ms-settings:")  # Opens Windows Settings
        engine.say("Opening Windows Settings")
        engine.runAndWait()

#greetings
    def greetings(self, command):
        self.response_label.setText("Hello! How can I help you?😊")
        engine.say("Hello! How can I help you?")
        engine.runAndWait()

    def open_GitHub(self, command):
        self.response_label.setText("Opening GitHub...")
        webbrowser.open(f"https://www.gitHub.com/")  # Opens GitHub
        engine.say("Opening GitHub.com")
        engine.runAndWait()

    def tell_time(self, command): #tell the current system time
        time_now = datetime.datetime.now().strftime("%H:%M")
        self.response_label.setText(f"The time is {time_now}")
        date = datetime.datetime.now().strftime("%d-%m-%Y")
        engine.say(f"The date is {date}")
        engine.say(f"The time is {time_now}")
        engine.runAndWait()

    def search_google(self, command): #search google for the query given by user
        query = command.replace("search google for", "").strip()
        webbrowser.open(f"https://www.google.com/search?q={query}")
        self.response_label.setText(f"Searching Google for {query}")
        engine.say(f"Searching Google for {query}")
        engine.runAndWait()
    
    def repeat_command(self, command): #repeat user's command
        self.response_label.setText(f"Reapeating what you said:")
        engine.say(f"{command}")
        engine.runAndWait()

    def close_assistant(self, command):
        self.response_label.setText("Goodbye! ✌️")
        engine.say("Goodbye! Have a nice day!")
        engine.runAndWait()
        time.sleep(1)  # Delay before exiting
        QApplication.quit()  # Close the application
        return  # Exit the function

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VoiceAssistantApp()
    window.show()
    sys.exit(app.exec_())
