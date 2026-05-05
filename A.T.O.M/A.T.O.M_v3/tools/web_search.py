# A.T.O.M/tools/web_search.py

"""
Google Search tool for A.T.O.M agent using Serper API.
Get API key: https://serper.dev
Free tier available.
"""

import requests
import os

def web_search(query: str, max_results: int = 5) -> str:
    query = query.strip()
    if not query:
        return "❌ Empty search query."

    # Re-read at call time so QSettings or late env vars are picked up
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        try:
            from PyQt5.QtCore import QSettings
            api_key = QSettings("A.T.O.M", "Config").value("serper_api_key", None)
        except Exception:
            pass

    if not api_key:
        return (
            "❌ SERPER_API_KEY not set. "
            "Get a free key at https://serper.dev and add it in Settings."
        )

    try:
        url = "https://google.serper.dev/search"

        payload = {
            "q": query,
            "num": max_results
        }

        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        results = []

        # Answer box (best result)
        if "answerBox" in data:
            ans = data["answerBox"].get("answer") or data["answerBox"].get("snippet")
            if ans:
                results.append(f"📌 {ans}")

        # Organic results
        for item in data.get("organic", [])[:max_results]:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "")

            results.append(f"[{title}]\n{snippet}\nURL: {link}")

        return "\n\n".join(results) if results else "No results found."

    except Exception as e:
        return f"❌ Search failed: {e}"