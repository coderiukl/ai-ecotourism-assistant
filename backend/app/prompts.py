from .config import ANTHROPIC_MAX_TOKENS

SYSTEM_PROMPT = (
    "Bạn là Núi Bà AI — trợ lý du lịch của Núi Bà Đen (Tây Ninh), "
    "trò chuyện tự nhiên như một người bạn địa phương.\n"
    "\n"
    "PHONG CÁCH:\n"
    "- Trả lời ngắn gọn, tự nhiên như tư vấn trực tiếp — không đọc liệt kê dữ liệu thô.\n"
    "- Nếu có nhiều thông tin (giá + giờ đẹp + đường đi), chia đoạn ngắn kèm bullet point.\n"
    "- Giọng thân thiện, tích cực nhưng không quảng cáo hoa mỹ "
    "('tuyệt đẹp nhất thế giới', 'không thể bỏ lỡ'). Để dữ liệu tự nói lên chất lượng.\n"
    "- Nếu không chắc chắn (giá theo mùa, thời tiết), ghi chú nhẹ cần xác nhận với nguồn chính thức.\n"
    "\n"
    "QUY TẮC:\n"
    "1. Chỉ trả lời dựa trên context được cung cấp. Nếu không có thông tin, "
    "nói rõ 'Mình chưa có dữ liệu chi tiết về vấn đề này' và gợi ý liên hệ hỗ trợ. "
    "TUYỆT ĐỐI không bịa đặt.\n"
    "2. Độ dài thường 3-6 dòng; chỉ dài hơn khi cần liệt kê nhiều mục.\n"
    "3. KHÔNG nhắc 'Theo dữ liệu nội bộ...' hay 'Dựa trên context...'. "
    "Đưa thông tin ra tự nhiên.\n"
)


def build_messages(question, contexts, history):
    context_block = _format_contexts(contexts) if contexts else "(không có dữ liệu liên quan)"
    messages = history + [
        {
            "role": "user",
            "content": (
                "Thông tin tham khảo từ dữ liệu Núi Bà Đen:\n"
                f"{context_block}\n\n"
                f"Câu hỏi: {question}"
            ),
        }
    ]
    return messages


def _format_contexts(contexts):
    blocks = []
    for ctx in contexts:
        source = ctx.get("source_url", "")
        block = f"- {ctx['title']}\n {ctx['text']}"
        if source:
            block += f"\n (Nguồn: {source})"
        blocks.append(block)
    return "\n\n".join(blocks)


def fallback_rag_answer(question, contexts):
    if not question:
        return "Bạn nhập câu hỏi giúp mình nhé."
    if not contexts:
        return (
            "Mình chưa tìm thấy thông tin phù hợp trong dữ liệu hiện có. "
            "Bạn có thể hỏi cụ thể hơn về giá vé, thời điểm tham quan, "
            "di chuyển hoặc hoạt động trải nghiệm tại Núi Bà Đen, "
            "hoặc liên hệ bộ phận hỗ trợ để được giải đáp chi tiết hơn."
        )
    ctx = contexts[0]
    text = ctx.get("text", "")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    fields = {}
    current_key = None
    for line in lines:
        if ":" in line and not line.startswith("-") and not line.startswith("["):
            parts = line.split(":", 1)
            key = parts[0].strip()
            val = parts[1].strip() if len(parts) > 1 else ""
            if val:
                fields[key] = val
                current_key = key
        elif current_key:
            fields[current_key] += " " + line

    extras = {
        "Vị trí": "📍 Vị trí",
        "Điểm nổi bật": "✨ Điểm nổi bật",
        "Thời điểm đẹp": "🕐 Thời điểm đẹp",
        "Thời lượng": "⏱ Thời lượng",
        "Loại hình": "🎯 Loại hình",
        "Độ khó": "💪 Độ khó",
        "Di chuyển": "🚗 Di chuyển",
        "Giá người lớn": "💰 Giá người lớn",
        "Giá trẻ em": "👶 Giá trẻ em",
        "Giá combo": "🎫 Combo",
        "Ghi chú": "📌 Ghi chú",
        "Lưu ý an toàn": "⚠️ Lưu ý",
        "Loại dịch vụ": "🛎 Loại dịch vụ",
        "Loại hoạt động": "🎯 Loại hoạt động",
    }

    parts = []
    priority = [
        "Vị trí", "Mô tả ngắn", "Chi tiết", "Điểm nổi bật",
        "Thời điểm đẹp", "Thời lượng", "Loại hình", "Độ khó", "Di chuyển",
        "Giá người lớn", "Giá trẻ em", "Giá combo", "Ghi chú", "Lưu ý an toàn",
    ]
    shown = set()
    for key in priority:
        val = fields.get(key, "")
        if val and val not in shown:
            parts.append(f"- {extras.get(key, key)}: {val}")
            shown.add(val)
    if len(contexts) > 1:
        parts.append("\nBạn muốn mình nói thêm phần nào không?")
    return "\n".join(parts)
