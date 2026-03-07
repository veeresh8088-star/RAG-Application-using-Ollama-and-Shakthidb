import requests

OLLAMA_URL = "http://localhost:11434/api/generate"

def ask_ollama(prompt):
    res = requests.post(
        OLLAMA_URL,
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        }
    )
    return res.json()["response"]

