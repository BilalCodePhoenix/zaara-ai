import requests
import time

URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:latest"

PROMPT = (
    "You are a female dental receptionist in India. "
    "Reply in natural Hindi using feminine grammar. "
    "Use one short sentence only. "
    "Say: I can help you book a dental appointment."
)

payload = {
    "model": MODEL,
    "messages": [
        {"role": "user", "content": PROMPT}
    ],
    "stream": True,
    "keep_alive": "5m",
    "options": {
        "temperature": 0.2,
        "num_predict": 100
    }
}

print(f"\nModel: {MODEL}")
print("Sending request...\n")

start = time.perf_counter()
first_token_time = None
response_text = ""

with requests.post(
    URL,
    json=payload,
    stream=True,
    timeout=120
) as response:

    response.raise_for_status()

    import json

    for line in response.iter_lines():
        if not line:
            continue

        data = json.loads(line)

        token = data.get("message", {}).get("content", "")

        if token:
            if first_token_time is None:
                first_token_time = time.perf_counter()
            response_text += token

        if data.get("done"):
            end = time.perf_counter()
            break

print("Response:", response_text)

if first_token_time:
    print(
        "Time to first token:",
        round(first_token_time - start, 2),
        "seconds"
    )

print("Total generation time:", round(end - start, 2), "seconds")