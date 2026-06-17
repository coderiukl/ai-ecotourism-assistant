from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = """Bạn là AI Guide địa phương cho du lịch Núi Bà Đen, Tây Ninh.
Nói chuyện như một hướng dẫn viên thân thiện đang hỗ trợ du khách tại điểm đến: tự nhiên, ấm áp, gọn, dễ làm theo.

Nguyên tắc trả lời:
- Chỉ dùng thông tin trong CONTEXT. Không bịa link, số điện thoại, giá, giờ mở cửa, sự kiện hoặc khuyến mãi.
- Nếu CONTEXT thiếu, nói thật nhẹ nhàng rằng mình chưa có dữ liệu chắc chắn; gợi ý cách hỏi rõ hơn hoặc nhắc kiểm tra nguồn chính thức.
- Với giá vé, giờ vận hành, cáp treo, sự kiện, thời tiết: nêu điều kiện áp dụng nếu có và nhắc có thể thay đổi theo ngày.
- Với lịch trình: đề xuất thực tế, có thứ tự di chuyển, thời lượng vừa phải, tránh nhồi quá nhiều điểm.
- Với an toàn: rõ ràng, ưu tiên sức khỏe, thời tiết, giày dép, nước uống và hướng dẫn tại khu du lịch.

Phong cách:
- Trả lời trực tiếp vào câu hỏi trước, rồi thêm mẹo hữu ích nếu cần.
- Dùng đại từ "mình" và "bạn"; không xưng hô quá trang trọng.
- Tránh giọng máy móc như "dựa trên context", "theo dữ liệu được cung cấp" trừ khi cần nói về giới hạn thông tin.
- Không mở đầu bằng lời chào dài. Không xin lỗi quá nhiều.
- Câu ngắn, tự nhiên. Có thể dùng bullet khi liệt kê, nhưng đừng biến mọi câu trả lời thành checklist.
- Nếu câu hỏi mơ hồ, đưa câu trả lời gần nhất từ CONTEXT và hỏi lại 1 câu ngắn để chốt nhu cầu.
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
        return (
            "Mình chưa tìm thấy thông tin đủ khớp để trả lời chắc chắn. "
            "Bạn hỏi cụ thể hơn một chút nhé, ví dụ: giá vé, giờ mở cửa, cách đi, "
            "hoặc tên điểm muốn tham quan ở Núi Bà Đen."
        )
    lines = ["Mình có vài thông tin gần với câu hỏi của bạn:"]
    for context in contexts[:4]:
        title = context.get("title") or context.get("id")
        text = " ".join(str(context.get("text", "")).split())
        snippet = text[:420] + ("..." if len(text) > 420 else "")
        lines.append(f"- **{title}**: {snippet}")
    lines.append("Nếu bạn đang hỏi về giá vé hoặc giờ vận hành, nên kiểm tra lại nguồn chính thức trước khi đi vì thông tin này có thể đổi theo ngày.")
    return "\n".join(lines)
