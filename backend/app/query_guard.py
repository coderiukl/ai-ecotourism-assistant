import json

from anthropic import Anthropic

from .config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_BASE_URL,
    ANTHROPIC_MODEL,
    ANTHROPIC_USER_AGENT,
    ANTHROPIC_VERSION,
)


_client = None


def get_guard_client():
    global _client

    if _client is None:
        _client = Anthropic(
            api_key=ANTHROPIC_API_KEY,
            base_url=ANTHROPIC_BASE_URL,
            default_headers={
                "User-Agent": ANTHROPIC_USER_AGENT,
                "anthropic-version": ANTHROPIC_VERSION,
            },
        )

    return _client


def check_query_clarity(question: str):
    question = (question or "").strip()

    if not question:
        return {
            "needs_clarification": True,
            "clarifying_question": "Bạn nhập câu hỏi giúp mình nhé.",
        }

    if not ANTHROPIC_API_KEY:
        return {
            "needs_clarification": False,
            "clarifying_question": "",
        }

    prompt = f"""
Bạn là bộ kiểm tra câu hỏi cho chatbot du lịch Núi Bà Đen.

Nhiệm vụ:
- Xác định câu hỏi của người dùng đã đủ rõ để tra dữ liệu RAG chưa.
- Nếu câu hỏi quá ngắn hoặc mơ hồ, hãy tạo 1 câu hỏi lại thân thiện.
- Nếu câu hỏi đủ rõ, không hỏi lại.

Ví dụ mơ hồ:
- "giá"
- "vé"
- "đường đi"
- "mấy giờ"
- "có gì"
- "ăn gì"
- "đẹp không"
- "đi sao"

Ví dụ đủ rõ:
- "giá vé cáp treo Núi Bà Đen"
- "đường đi từ TP.HCM đến Núi Bà Đen"
- "Núi Bà Đen có những hoạt động gì?"
- "nên đi Núi Bà Đen mùa nào?"

Chỉ trả về JSON, không giải thích.

Format:
{{
  "needs_clarification": true/false,
  "clarifying_question": "..."
}}

Câu hỏi người dùng: {question}
"""

    try:
        client = get_guard_client()

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=300,
            system="Bạn chỉ trả về JSON hợp lệ.",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        text = response.content[0].text.strip()
        data = json.loads(text)

        return {
            "needs_clarification": bool(data.get("needs_clarification")),
            "clarifying_question": data.get("clarifying_question", "").strip(),
        }

    except Exception:
        return {
            "needs_clarification": False,
            "clarifying_question": "",
        }