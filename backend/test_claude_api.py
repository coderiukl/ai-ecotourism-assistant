from anthropic import Anthropic
from dotenv import load_dotenv
import os


load_dotenv()
client = Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY", ""),
    base_url=os.getenv("ANTHROPIC_BASE_URL", ""),
    default_headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0",
        "anthropic-version": "2023-06-01"
    }
)

def ask_claude(prompt: str, model: str = "claude-haiku-4-5") -> str:
    text = ""

    with client.messages.stream(
        model=model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
    ) as stream:
        for chunk in stream.text_stream:
            text += chunk

    return text

print(ask_claude("Hello Claude"))