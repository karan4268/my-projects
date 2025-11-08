# A.T.O.M/summarizer.py
from local_engine import get_response_from_atom
import re

MAX_TOKENS = 500  # slightly below model context length

def split_into_chunks(text, max_tokens=MAX_TOKENS):
    """Split text into chunks of <= max_tokens words."""
    text = re.sub(r'\s+', ' ', text).strip()
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_tokens):
        chunk = " ".join(words[i:i+max_tokens])
        chunks.append(chunk)
    return chunks

def summarize_text(text):
    """Summarize large text safely in token-sized chunks."""
    chunks = split_into_chunks(text)
    summaries = []

    for i, chunk in enumerate(chunks):
        prompt = f"Summarize this text concisely:\n\n{chunk}"
        print(f"🔹 Summarizing chunk {i+1}/{len(chunks)}...")
        summary = get_response_from_atom(prompt)
        summaries.append(summary)

    # Combine all summaries and summarize again
    combined = " ".join(summaries)
    final_prompt = f"Combine these summaries into a concise overview:\n\n{combined}"
    final_summary = get_response_from_atom(final_prompt)
    return final_summary

