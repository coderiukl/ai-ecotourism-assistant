from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = """Bạn là AI Guide địa phương cho du lịch Núi Bà Đen, Tây Ninh.
Nói chuyện như một hướng dẫn viên thân thiện đang hỗ trợ du khách tại điểm đến: tự nhiên, ấm áp, gọn, dễ làm theo.

Nguyên tắc trả lời:
- Chỉ dùng thông tin tham khảo và ĐỊA ĐIỂM ĐANG CHỌN. Không bịa link, số điện thoại, giá, giờ mở cửa, sự kiện hoặc khuyến mãi.
- Nếu thông tin tham khảo thiếu, nói thật nhẹ nhàng rằng mình chưa có thông tin chắc chắn; gợi ý cách hỏi rõ hơn hoặc nhắc kiểm tra nguồn chính thức.
- Với giá vé, giờ vận hành, cáp treo, sự kiện, thời tiết: nêu điều kiện áp dụng nếu có và nhắc có thể thay đổi theo ngày.
- Với lịch trình: đề xuất thực tế, có thứ tự di chuyển, thời lượng vừa phải, tránh nhồi quá nhiều điểm.
- Với an toàn: rõ ràng, ưu tiên sức khỏe, thời tiết, giày dép, nước uống và hướng dẫn tại khu du lịch.

Phạm vi địa điểm:
- Luôn coi ĐỊA ĐIỂM ĐANG CHỌN là phạm vi duy nhất của cuộc trò chuyện.
- Không trả lời lan sang địa điểm khác, khu vực khác hoặc toàn bộ Núi Bà Đen nếu câu hỏi chỉ hỏi “ở đây”, “chỗ này”, “địa điểm này”.
- Nếu người dùng hỏi sang địa điểm khác, nhắc ngắn rằng hiện mình đang hỗ trợ riêng địa điểm đang chọn.

Phong cách:
- Trả lời trực tiếp vào câu hỏi trước, rồi thêm mẹo hữu ích nếu cần.
- Dùng đại từ "mình" và "bạn"; không xưng hô quá trang trọng.
- Tránh giọng máy móc như "dựa trên context", "theo dữ liệu được cung cấp" trừ khi cần nói về giới hạn thông tin.
- Không mở đầu bằng lời chào dài. Không xin lỗi quá nhiều.
- Câu ngắn, tự nhiên. Có thể dùng bullet khi liệt kê, nhưng đừng biến mọi câu trả lời thành checklist.
- Nếu câu hỏi mơ hồ, đưa câu trả lời gần nhất từ thông tin tham khảo và hỏi lại 1 câu ngắn để chốt nhu cầu.
"""

SYSTEM_PROMPT += (
    "\n\n"
    "Định dạng hiển thị:\n"
    "- Giữ mỗi câu trả lời trong 2-4 khối ngắn; mỗi khối 1-2 câu.\n"
    "- Dùng gạch đầu dòng '-' khi liệt kê từ 2 ý trở lên.\n"
    "- Không trộn giá vé, giờ mở cửa, di chuyển, an toàn và mẹo trong cùng một đoạn.\n"
    "- Thông tin chưa chắc chắn hoặc có thể thay đổi phải tách riêng, bắt đầu bằng 'Lưu ý:'.\n"
    "- Mẹo thực tế nên tách riêng, bắt đầu bằng 'Mẹo:'.\n"
    "- Chỉ dùng tiêu đề ngắn khi thật hữu ích, ví dụ 'Gợi ý nhanh'."
)


SYSTEM_PROMPT += (
    "\n\n"
    "Luật diễn đạt bắt buộc:\n"
    "- Không bao giờ nói các từ nội bộ như 'context', 'sheet', 'Excel nội bộ', 'nguồn 1', 'dữ liệu được cung cấp'.\n"
    "- Khi thiếu thông tin, nói tự nhiên: 'Mình chỉ có thông tin chắc về...' hoặc 'Mình chưa có thông tin chắc về...'.\n"
    "- Không copy nguyên cặp field/value. Hãy viết lại thành câu hoàn chỉnh, có dấu câu và khoảng trắng đúng."
)


def build_context(contexts: list[dict[str, Any]]) -> str:
    if not contexts:
        return "Không có thông tin phù hợp."
    blocks = []
    for index, context in enumerate(contexts, start=1):
        source = context.get("source_url") or "Thông tin nội bộ"
        blocks.append(
            f"[Thông tin {index}] {context.get('title') or context.get('id')}\n"
            f"Nhóm thông tin: {context.get('sheet') or context.get('type')}\n"
            f"URL: {source}\n"
            f"{context.get('text', '')}"
        )
    return "\n\n---\n\n".join(blocks)


def build_destination_scope(destination: dict[str, Any] | None = None) -> str:
    if not destination:
        return "Chưa chọn địa điểm cụ thể."

    fields = [
        ("Tên", destination.get("name")),
        ("Mã", destination.get("dest_code")),
        ("Khu vực", destination.get("location")),
        ("Nhóm", destination.get("category")),
        ("Tóm tắt", destination.get("short_description")),
        ("Nổi bật", destination.get("highlight")),
        ("Thời điểm đẹp", destination.get("best_time")),
        ("Thời lượng gợi ý", destination.get("estimated_duration")),
        ("Cách di chuyển", destination.get("transport")),
    ]
    return "\n".join(f"{label}: {value}" for label, value in fields if value)


def messages(
    question: str,
    contexts: list[dict[str, Any]],
    destination: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "ĐỊA ĐIỂM ĐANG CHỌN:\n"
                f"{build_destination_scope(destination)}\n\n"
                "QUY TẮC PHẠM VI:\n"
                "- Chỉ trả lời về địa điểm đang chọn.\n"
                "- Nếu câu hỏi nhắc sang địa điểm khác, hãy nói ngắn rằng mình đang hỗ trợ riêng địa điểm đang chọn.\n"
                "- Nếu thiếu thông tin riêng cho địa điểm này, nói rõ là chưa có thông tin chắc chắn, không suy đoán từ địa điểm khác.\n\n"
                f"THÔNG TIN THAM KHẢO RIÊNG CỦA ĐỊA ĐIỂM:\n{build_context(contexts)}\n\n"
                f"CÂU HỎI: {question}"
            ),
        },
    ]


def fallback_answer(
    question: str,
    contexts: list[dict[str, Any]],
    destination: dict[str, Any] | None = None,
) -> str:
    destination_name = destination.get("name") if destination else "địa điểm này"
    if not contexts:
        return (
            f"Mình chưa có dữ liệu đủ chắc riêng cho **{destination_name}** để trả lời ý này.\n\n"
            "Gợi ý: Bạn hỏi cụ thể hơn một chút nhé, ví dụ: điểm nổi bật, cách đi, thời điểm đẹp, "
            "hoặc thời lượng tham quan tại địa điểm này."
        )
    lines = [f"Mình có vài thông tin gần với **{destination_name}**:"]
    for context in contexts[:4]:
        title = context.get("title") or context.get("id")
        text = " ".join(str(context.get("text", "")).split())
        snippet = text[:420] + ("..." if len(text) > 420 else "")
        lines.append(f"- **{title}**: {snippet}")
    lines.append(
        "Lưu ý: Nếu bạn đang hỏi về giá vé hoặc giờ vận hành, nên kiểm tra lại nguồn chính thức trước khi đi vì thông tin này có thể đổi theo ngày."
    )
    return "\n".join(lines)
