"""Prompt helpers for Nui Ba Den RAG chatbot."""

import re
import unicodedata

MAX_CONTEXT_CHARS = 1200
MAX_TOTAL_CONTEXT_CHARS = 4200


SYSTEM_PROMPT = (
    "Bạn là Núi Bà AI — trợ lý du lịch của Núi Bà Đen (Tây Ninh), "
    "trò chuyện tự nhiên như một người bạn địa phương am hiểu nơi này.\n\n"
    "PHONG CÁCH TRẢ LỜI:\n"
    "- Thân thiện, gần gũi, dễ hiểu; xưng 'mình' và gọi người dùng là 'bạn'.\n"
    "- Trả lời như đang tư vấn trực tiếp, không đọc lại dữ liệu thô.\n"
    "- Ưu tiên câu ngắn, tự nhiên; thường 3-6 dòng.\n"
    "- Nếu có nhiều thông tin như giá, giờ đẹp, đường đi, lịch trình thì chia bullet ngắn.\n"
    "- Dùng emoji vừa phải để dễ nhìn, không lạm dụng.\n"
    "- Không quảng cáo hoa mỹ kiểu 'đẹp nhất thế giới', 'không thể bỏ lỡ'.\n\n"
    "QUY TẮC AN TOÀN DỮ LIỆU:\n"
    "1. Chỉ trả lời dựa trên dữ liệu tham khảo được cung cấp. Tuyệt đối không bịa đặt.\n"
    "2. Nếu chưa có dữ liệu phù hợp, nói rõ: 'Mình chưa có dữ liệu chi tiết về vấn đề này'.\n"
    "3. Nếu thông tin có thể thay đổi như giá vé, thời tiết, giờ vận hành, hãy nhắc nhẹ nên kiểm tra lại nguồn chính thức.\n"
    "4. Không nói các câu như 'Theo dữ liệu nội bộ', 'Dựa trên context', 'Dữ liệu cung cấp cho biết'.\n"
    "5. Nếu người dùng hỏi ngoài phạm vi Núi Bà Đen/Tây Ninh, trả lời lịch sự rằng mình chỉ hỗ trợ tốt nhất về Núi Bà Đen.\n"
)


def truncate_text(text, max_chars=MAX_CONTEXT_CHARS):
    """Keep prompt context compact and avoid cutting in the middle of a word."""
    text = str(text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0].strip() + "..."


def build_system_prompt(contexts=None):
    """Build Anthropic system prompt with compact RAG context.

    Anthropic expects the system prompt in the `system=` argument, not as a
    message with role='system'.
    """
    context_block = _format_contexts(contexts or [])
    if not context_block:
        context_block = "(không có dữ liệu liên quan)"

    return (
        SYSTEM_PROMPT
        + "\n\nDỮ LIỆU THAM KHẢO ĐƯỢC PHÉP DÙNG:\n"
        + context_block
        + "\n\nHãy trả lời tự nhiên cho người dùng, chỉ dùng dữ liệu ở trên."
    )


def build_messages(question, contexts=None, history=None):
    """Build conversation messages for Anthropic.

    Context is intentionally not placed inside the user message so the model
    focuses on answering the actual question naturally.
    """
    history = history or []
    messages = []
    messages.extend(history)
    messages.append({"role": "user", "content": str(question or "").strip()})
    return messages


def _format_contexts(contexts):
    blocks = []
    total_chars = 0

    for index, ctx in enumerate(contexts or [], start=1):
        title = ctx.get("title") or "Thông tin"
        text = truncate_text(ctx.get("text", ""))
        source = ctx.get("source_url") or ""

        if not text:
            continue

        block = f"[{index}] {title}\n{text}"
        if source:
            block += f"\nNguồn: {source}"

        if total_chars + len(block) > MAX_TOTAL_CONTEXT_CHARS:
            break

        blocks.append(block)
        total_chars += len(block)

    return "\n\n".join(blocks)


def _extract_fields(text):
    lines = [line.strip() for line in str(text or "").split("\n") if line.strip()]
    fields = {}
    current_key = None

    for line in lines:
        if ":" in line and not line.startswith("-") and not line.startswith("["):
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            fields[key] = value
            current_key = key
        elif current_key:
            fields[current_key] = (fields.get(current_key, "") + " " + line).strip()

    return fields


def _first_value(fields, keys):
    for key in keys:
        value = fields.get(key, "")
        if value:
            return value
    return ""


def _slugify(value):
    value = str(value or "").replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")


def _is_price_question(question):
    tokens = set(_slugify(question).split("_"))
    return bool(tokens & {"gia", "ve", "phi", "ticket", "price", "cost"})


def _price_hint_answer(question, contexts):
    if not _is_price_question(question):
        return ""

    hints = []
    seen = set()
    for ctx in contexts or []:
        fields = _extract_fields(ctx.get("text", ""))
        hint = _first_value(fields, ["Answer hint"])
        if not hint or hint in seen:
            continue
        seen.add(hint)
        hints.append(hint)

    if not hints:
        return ""

    lines = ["Có nha, mình thấy dữ liệu giá như sau:"]
    lines.extend(f"- {hint}" for hint in hints[:6])
    lines.append("Giá có thể thay đổi theo thời điểm, bạn nên kiểm tra lại nguồn chính thức trước khi đi nha.")
    return "\n".join(lines)


def fallback_rag_answer(question, contexts=None):
    """Friendly fallback when Claude is not configured or fails."""
    contexts = contexts or []
    question = str(question or "").strip()

    if not question:
        return "Bạn nhập câu hỏi giúp mình nhé 😊"

    if not contexts:
        return (
            "Mình chưa tìm thấy thông tin phù hợp trong dữ liệu hiện có bạn nhé. "
            "Bạn có thể hỏi cụ thể hơn về giá vé, đường đi, thời điểm tham quan "
            "hoặc hoạt động trải nghiệm tại Núi Bà Đen."
        )

    price_hint_answer = _price_hint_answer(question, contexts)
    if price_hint_answer:
        return price_hint_answer

    ctx = contexts[0] or {}
    title = ctx.get("title") or "Thông tin Núi Bà Đen"
    text = ctx.get("text", "")
    fields = _extract_fields(text)

    if not text.strip():
        return (
            "Mình chưa có dữ liệu chi tiết về vấn đề này bạn nhé. "
            "Bạn thử hỏi cụ thể hơn một chút, ví dụ về giá vé, đường đi hoặc hoạt động tham quan nha."
        )

    location = _first_value(fields, ["Vị trí", "Địa chỉ"])
    answer_hint = _first_value(fields, ["Answer hint", "Trả lời"])
    short_desc = _first_value(fields, ["Mô tả ngắn", "Chi tiết", "Nội dung", "Trả lời"])
    highlights = _first_value(fields, ["Điểm nổi bật"])
    best_time = _first_value(fields, ["Thời điểm đẹp"])
    duration = _first_value(fields, ["Thời lượng"])
    transport = _first_value(fields, ["Di chuyển"])
    adult_price = _first_value(fields, ["Giá người lớn"])
    child_price = _first_value(fields, ["Giá trẻ em"])
    combo_price = _first_value(fields, ["Giá combo"])
    price_vnd = _first_value(fields, ["Price VND"])
    customer_type = _first_value(fields, ["Customer type"])
    note = _first_value(fields, ["Ghi chú", "Lưu ý an toàn", "Xác minh"])

    parts = [f"Có nha, mình gửi bạn thông tin về **{title}** nè:"]

    details = []
    if answer_hint:
        details.append(answer_hint)
    if location:
        details.append(f"📍 {location}")
    if short_desc:
        details.append(f"{short_desc}")
    if highlights and highlights != short_desc:
        details.append(f"✨ {highlights}")
    if best_time:
        details.append(f"🕐 Thời điểm phù hợp: {best_time}")
    if duration:
        details.append(f"⏱ Thời lượng gợi ý: {duration}")
    if transport:
        details.append(f"🚗 Di chuyển: {transport}")
    if adult_price:
        details.append(f"💰 Người lớn: {adult_price}")
    if child_price:
        details.append(f"👶 Trẻ em: {child_price}")
    if combo_price:
        details.append(f"🎫 Combo: {combo_price}")
    if price_vnd and not answer_hint:
        label = f" cho {customer_type}" if customer_type else ""
        details.append(f"💰 Giá{label}: {price_vnd}.000đ")
    if note:
        details.append(f"📌 Lưu ý: {note}")

    if not details:
        details.append(truncate_text(text, max_chars=700))

    parts.extend(details[:8])

    if adult_price or child_price or combo_price or price_vnd or answer_hint:
        parts.append("Giá có thể thay đổi theo thời điểm, bạn nên kiểm tra lại nguồn chính thức trước khi đi nha.")

    if len(contexts) > 1:
        parts.append("Bạn muốn mình nói kỹ hơn phần giá vé, đường đi hay lịch trình tham quan không?")

    return "\n".join(parts)
