import os
import shutil
import fitz  # PyMuPDF for PDFs
import docx  # for dox
import nltk  # tokenizer

nltk.download('punkt_tab')
from nltk.tokenize import word_tokenize

# Define the folder to be sorted
SOURCE_FOLDER = "F:\sd\Backup"  # Change this for the folder to be sorted
DEST_FOLDER = "F:\sd\Backup"    # Change destination folder (can be the same folder too)

# Create category folders /Sub-folders
CATEGORIES = {
    "Images": [".jpg", ".jpeg", ".png", ".gif"],
    "Documents": [".pdf", ".docx", ".txt",".xlsx"],
    "Invoices": ["invoice", "receipt", "slip"],                # file extentions or keywords can be added as necessary
    "Media": [".mp4", ".avi", ".mkv", ".flac", ".wav"],
    "Audio":[".mp3"],
    "Archives":[".zip",".7z"],
    "Reports & Forms":["Report","Synopsis","Form",]
}
# Creating Sub folders
for folder in CATEGORIES.keys():
    os.makedirs(os.path.join(DEST_FOLDER, folder), exist_ok=True)

def extract_text(file_path):
    """Extract text from PDF or DOCX files."""
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".pdf":
        # Extract text from PDF using PyMuPDF (fitz)
        doc = fitz.open(file_path)
        text = " ".join([page.get_text("text") for page in doc])
        return text

    elif ext == ".docx":
        # Extracting text from DOCX using python-docx
        doc = docx.Document(file_path)
        text = " ".join([p.text for p in doc.paragraphs])
        return text

    elif ext == ".txt":
        # For text files,read the content
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    
    return ""

def categorize_file(file_name, file_path):
    """Prioritize content analysis, and fallback to extension-based categorization."""
    # extract text content from the file
    text = extract_text(file_path)

    if text:
        # Tokenizing  the text
        words = word_tokenize(text.lower())

        # Check for keywords related to certain catagory
        for category, keywords in CATEGORIES.items():
            if any(keyword in words for keyword in keywords):
                return category

    # If no keywords found, sort using file extension check
    ext = os.path.splitext(file_name)[1].lower()
    for category, extensions in CATEGORIES.items():
        if ext in extensions:
            return category

    # no match found, return Uncategorized
    return "Uncategorized"

def sort_files():
    """Scan the folder and move files into the correct category."""
    for file_name in os.listdir(SOURCE_FOLDER):
        file_path = os.path.join(SOURCE_FOLDER, file_name)

        if os.path.isfile(file_path):
            category = categorize_file(file_name, file_path)
            dest_path = os.path.join(DEST_FOLDER, category, file_name)
            shutil.move(file_path, dest_path)
            print(f"Moved: {file_name} → {category}")

if __name__ == "__main__":
    sort_files()
    print("File sorting complete!✔️")