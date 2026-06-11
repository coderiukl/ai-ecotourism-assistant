from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", ""),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
)


def ask_openai(prompt: str, model: str | None = None) -> str:
    response = client.chat.completions.create(
        model=model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    return response.choices[0].message.content or ""


if __name__ == "__main__":
    print(ask_openai("Hello OpenAI"))
