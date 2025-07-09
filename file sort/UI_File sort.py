import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import nltk
import os
import File_sort as sorter  # Replace with your logic filename if different
import ttkbootstrap as tb
from ttkbootstrap.constants import *


nltk.download('punkt')


class FileSorterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart File Sorter")
        self.root.geometry("700x500")

        self.source_folder = tk.StringVar()
        self.dest_folder = tk.StringVar()
        self.new_item = tk.StringVar()
        self.selected_category = tk.StringVar()

        # Folder selection
        ttk.Label(root, text="Source Folder:").pack(pady=5)
        ttk.Entry(root, textvariable=self.source_folder, width=60).pack()
        ttk.Button(root, text="Browse", command=self.browse_source).pack()

        ttk.Label(root, text="Destination Folder:").pack(pady=10)
        ttk.Entry(root, textvariable=self.dest_folder, width=60).pack()
        ttk.Button(root, text="Browse", command=self.browse_dest).pack()

        ttk.Button(root, text="Start Sorting", command=self.start_sorting).pack(pady=20)

        # Divider
        ttk.Separator(root, orient='horizontal').pack(fill='x', pady=10)

        # UI for adding file extensions or keywords
        ttk.Label(root, text="Add Custom File Extensions/Keyword to a Category:").pack()
        cat_names = list(sorter.CATEGORIES.keys())
        self.selected_category.set(cat_names[0])
        ttk.OptionMenu(root, self.selected_category, cat_names[0], *cat_names).pack(pady=5)
        ttk.Entry(root, textvariable=self.new_item, width=30).pack()
        ttk.Button(root, text="Add to Category", command=self.add_to_category).pack(pady=5)

        # Output Status Box
        self.status_box = tk.Text(root, height=10, width=80)
        self.status_box.pack()

    def browse_source(self):
        folder = filedialog.askdirectory()
        if folder:
            self.source_folder.set(folder)

    def browse_dest(self):
        folder = filedialog.askdirectory()
        if folder:
            self.dest_folder.set(folder)

    def add_to_category(self):
        category = self.selected_category.get()
        item = self.new_item.get().strip().lower()

        if not item:
            messagebox.showwarning("Empty Input", "Please enter a valid extension or keyword.")
            return

        if item in sorter.CATEGORIES[category]:
            self.update_status(f"'{item}' already exists in '{category}'.")
        else:
            sorter.CATEGORIES[category].append(item)
            self.update_status(f"Added '{item}' to category '{category}'.")
            self.new_item.set("")

    def update_status(self, message):
        self.status_box.insert(tk.END, message + "\n")
        self.status_box.see(tk.END)
        self.root.update()

    def start_sorting(self):
        src = self.source_folder.get()
        dst = self.dest_folder.get()

        if not src or not dst:
            messagebox.showwarning("Missing Input", "Please select both source and destination folders.")
            return

        self.status_box.delete(1.0, tk.END)
        self.update_status("Sorting started...\n")

        sorter.SOURCE_FOLDER = src
        sorter.DEST_FOLDER = dst

        # Ensure category folders exist
        for folder in sorter.CATEGORIES.keys():
            os.makedirs(os.path.join(dst, folder), exist_ok=True)
        os.makedirs(os.path.join(dst, "Uncategorized"), exist_ok=True)

        sorter.sort_files()
        self.update_status("Sorting complete ✔️")


if __name__ == "__main__":
    root = tb.Window(themename="darkly")  # or "darkly", "cyborg", "solar", etc.
    app = FileSorterApp(root)
    root.mainloop()
