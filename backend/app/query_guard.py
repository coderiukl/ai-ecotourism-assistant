import re

from .text_utils import slugify

AMBIGUOUS_SHORT_QUERIES = {
    "gia",
    "ve",
    "phi",
    "duong di",
    "may gio",
    "co gi",
    "an gi",
    "dep khong",
    "di sao",
}


def check_query_clarity(question: str):
    question = (question or "").strip()

    if not question:
        return {
            "needs_clarification": True,
            "clarifying_question": "Bạn nhập câu hỏi giúp mình nhé.",
        }

    normalized = slugify(question)
    tokens = re.findall(r"[a-z0-9]+", normalized)

    if normalized in AMBIGUOUS_SHORT_QUERIES and len(tokens) <= 3:
        return {
            "needs_clarification": True,
            "clarifying_question": "Bạn muốn hỏi về giá vé, đường đi, thời gian hay hoạt động nào ở Núi Bà Đen?",
        }

    return {
        "needs_clarification": False,
        "clarifying_question": "",
    }
