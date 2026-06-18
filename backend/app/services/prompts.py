from __future__ import annotations

from typing import Any

MAX_CONTEXT_TEXT_CHARS = 1200
MAX_CONTEXT_BLOCKS = 6


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


SYSTEM_PROMPT = """
Bạn là "Núi Bà AI" - hướng dẫn viên du lịch địa phương tại Núi Bà Đen, Tây Ninh.

Vai trò:
- Trả lời như một hướng dẫn viên thân thiện, tự nhiên và dễ làm theo.
- Chỉ dùng thông tin tham khảo được cung cấp.
- Xưng "mình", gọi người dùng là "bạn".

Nguyên tắc bắt buộc:
- Không tự tạo giá vé, giờ mở cửa, số điện thoại, website, khuyến mãi, sự kiện hoặc lịch vận hành.
- Nếu không có thông tin chắc chắn, nói: "Mình chưa có thông tin chắc chắn về nội dung này."
- Nếu thông tin có thể thay đổi như giá vé, giờ vận hành, cáp treo hoặc sự kiện, tách riêng bằng dòng bắt đầu với "Lưu ý:".
- Địa điểm đang chọn là phạm vi duy nhất. Không tự mở rộng sang địa điểm khác hoặc toàn bộ Núi Bà Đen.
- Nếu người dùng hỏi "ở đây", "chỗ này", "địa điểm này", hãy hiểu là đang hỏi về địa điểm đang chọn.
- Nếu người dùng hỏi sang nơi khác, trả lời ngắn: "Mình hiện đang hỗ trợ riêng địa điểm bạn đang xem."

Câu hỏi mơ hồ:
- Nếu người dùng chỉ hỏi rất ngắn như "giá", "vé", "giờ", "mở cửa", "cáp treo", "buffet", "đi sao", hãy hỏi lại 1 câu ngắn để làm rõ.
- Không tự đoán nhu cầu của người dùng.

Cách trả lời:
- Trả lời trực tiếp câu hỏi trước.
- Viết ngắn gọn trong 2-4 khối, mỗi khối 1-2 câu.
- Dùng gạch đầu dòng khi liệt kê từ 2 ý trở lên.
- Có thể thêm "Mẹo:" nếu có lời khuyên thực tế.
- Không nói các từ nội bộ như context, sheet, Excel, database, source, dữ liệu được cung cấp.
- Không copy field/value thô; hãy viết lại thành câu tự nhiên.
""".strip()


def build_context(contexts: list[dict[str, Any]]) -> str:
    if not contexts:
        return "Không tìm thấy thông tin phù hợp cho câu hỏi này."

    blocks: list[str] = []

    for index, context in enumerate(contexts[:MAX_CONTEXT_BLOCKS], start=1):
        title = _clean_text(context.get("title") or context.get("name") or context.get("id"))
        text = _clean_text(context.get("text"))

        if not text:
            continue

        if len(text) > MAX_CONTEXT_TEXT_CHARS:
            text = text[:MAX_CONTEXT_TEXT_CHARS].rstrip() + "..."

        parts = [f"[Thông tin {index}]"]

        if title:
            parts.append(f"Tiêu đề: {title}")

        parts.append(f"Nội dung: {text}")
        blocks.append("\n".join(parts))

    return "\n\n---\n\n".join(blocks) if blocks else "Không tìm thấy thông tin phù hợp cho câu hỏi này."


def build_destination_scope(destination: dict[str, Any] | None = None) -> str:
    if not destination:
        return "Chưa chọn địa điểm cụ thể."

    fields = [
        ("Tên địa điểm", destination.get("name")),
        ("Khu vực", destination.get("location")),
        ("Loại địa điểm", destination.get("category")),
        ("Tóm tắt", destination.get("short_description")),
        ("Điểm nổi bật", destination.get("highlight")),
        ("Thời điểm phù hợp", destination.get("best_time")),
        ("Thời lượng gợi ý", destination.get("estimated_duration")),
        ("Cách di chuyển", destination.get("transport")),
    ]

    lines = [
        f"- {label}: {_clean_text(value)}"
        for label, value in fields
        if _clean_text(value)
    ]

    return "\n".join(lines) if lines else "Chưa có thông tin chi tiết về địa điểm đang chọn."


def messages(
    question: str,
    contexts: list[dict[str, Any]],
    destination: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    clean_question = _clean_text(question)
    destination_scope = build_destination_scope(destination)
    context_text = build_context(contexts)

    user_content = f"""
ĐỊA ĐIỂM ĐANG CHỌN:
{destination_scope}

PHẠM VI TRẢ LỜI:
- Chỉ trả lời về địa điểm đang chọn.
- Nếu thiếu thông tin riêng cho địa điểm này, nói rõ là mình chưa có thông tin chắc chắn.
- Không suy đoán từ địa điểm khác.

THÔNG TIN THAM KHẢO:
{context_text}

CÂU HỎI CỦA NGƯỜI DÙNG:
{clean_question}
""".strip()

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def fallback_answer(
    question: str,
    contexts: list[dict[str, Any]],
    destination: dict[str, Any] | None = None,
) -> str:
    destination_name = destination.get("name") if destination else "địa điểm này"

    if not contexts:
        return (
            f"Mình chưa có thông tin chắc chắn riêng cho **{destination_name}** để trả lời ý này.\n\n"
            "Bạn có thể hỏi cụ thể hơn như: giá vé, giờ mở cửa, cách đi, điểm nổi bật hoặc thời lượng tham quan."
        )

    return (
        f"Mình có tìm thấy một vài thông tin liên quan đến **{destination_name}**, "
        "nhưng chưa đủ chắc để trả lời hoàn chỉnh.\n\n"
        "Bạn có thể hỏi cụ thể hơn, ví dụ: giá vé, giờ mở cửa, cách đi hoặc hoạt động nổi bật."
    )