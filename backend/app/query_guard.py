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
            "clarifying_question": "Ban nhap cau hoi giup minh nhe.",
        }

    normalized = slugify(question)
    tokens = re.findall(r"[a-z0-9]+", normalized)

    if normalized in AMBIGUOUS_SHORT_QUERIES and len(tokens) <= 3:
        return {
            "needs_clarification": True,
            "clarifying_question": "Ban muon hoi ve gia ve, duong di, thoi gian, hay hoat dong nao o Nui Ba Den?",
        }

    return {
        "needs_clarification": False,
        "clarifying_question": "",
    }
