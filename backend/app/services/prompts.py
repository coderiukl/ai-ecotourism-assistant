from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = """Bạn là AI Guide chuyên nghiệp cho du lịch Núi Bà Đen, Tây Ninh.
Trả lời bằng tiếng Việt tự nhiên, ngắn gọn, hữu ích cho du khách đang ở điểm tham quan.
Chỉ dùng thông tin trong CONTEXT. Nếu context thiếu hoặc có thể thay đổi theo ngày, nói rõ cần kiểm tra nguồn chính thức.
Ưu tiên: giá vé/giờ mở cửa phải nêu điều kiện áp dụng; lịch trình phải thực tế; an toàn phải rõ ràng.
Không bịa link, không bịa số điện thoại, không khẳng định thông tin ngoài context.
"""


def build_context(contexts: list[dict[str, Any]]) -> str:
    if not contexts:
        return "Không có context phù hợp."
    blocks = []
    for index, context in enumerate(contexts, start=1):
        source = context.get("source_url") or "Excel nội bộ"
        blocks.append(
            f"[Nguồn {index}] {context.get('title') or context.get('id')}\n"
            f"Sheet: {context.get('sheet') or context.get('type')}\n"
            f"URL: {source}\n"
            f"{context.get('text', '')}"
        )
    return "\n\n---\n\n".join(blocks)


def messages(question: str, contexts: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"CONTEXT:\n{build_context(contexts)}\n\nCÂU HỎI: {question}"},
    ]


def fallback_answer(question: str, contexts: list[dict[str, Any]]) -> str:
    if not contexts:
        return "Mình chưa tìm thấy dữ liệu phù hợp trong file Excel. Bạn hỏi cụ thể hơn về giá vé, giờ mở cửa, đường đi hoặc địa điểm muốn tham quan nhé."
    lines = ["Mình tìm thấy vài thông tin liên quan trong dữ liệu nội bộ:"]
    for context in contexts[:4]:
        title = context.get("title") or context.get("id")
        text = " ".join(str(context.get("text", "")).split())
        snippet = text[:420] + ("..." if len(text) > 420 else "")
        lines.append(f"- **{title}**: {snippet}")
    lines.append("Bạn nên kiểm tra lại thông tin giá vé/giờ vận hành trên nguồn chính thức trước khi đi vì có thể thay đổi theo ngày.")
    return "\n".join(lines)
