import ollama


# streaming responses (chunks)
def stream_response_from_atom(user_text):
    """
    Stream response chunks from the local Ollama model.
    """
    try:
        stream = ollama.chat(
            model="phi3",
            messages=[{"role": "user", "content": user_text}],
            stream=True
        )
        for chunk in stream:
            if "message" in chunk and "content" in chunk["message"]:
                yield chunk["message"]["content"]
    except Exception as e:
        yield f"A.T.O.M encountered an error: {e}"

# waits for entire response
def get_response_from_atom(user_text):
    """
    Blocking version (waits for full output).
    """
    try:
        response = ollama.chat(
            model="phi3",
            messages=[{"role": "user", "content": user_text}]
        )
        return response['message']['content']
    except Exception as e:
        return f"A.T.O.M encountered an error: {e}"
