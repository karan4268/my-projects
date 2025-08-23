import ollama

def get_response_from_atom(user_text):
    try:
        response = ollama.chat(
            model="phi3",
            messages=[{"role": "user", "content": user_text}]
        )
        return response['message']['content']
    except Exception as e:
        return f"A.T.O.M encountered an error: {e}"
