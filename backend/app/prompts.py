"""Prompt helpers for Nui Ba Den RAG chatbot.

Owns only the prompt text and context assembly. All business logic
(field extraction, price formatting, fallback answer composition) lives
in domain/ so it can be reused by rag.py and tests without pulling
in prompt text.
"""

from .domain import extract_fields, field

MAX_CONTEXT_CHARS = 1200
MAX_TOTAL_CONTEXT_CHARS = 4200


SYSTEM_PROMPT = (
    "Bạn là Núi Bà AI, trợ lý du lịch của Núi Bà Đen (Tây Ninh). "
    "Bạn trả lời như một người địa phương am hiểu, thân thiện và thực tế.\n\n"
    "PHONG CÁCH:\n"
    "- Xưng 'mình', gọi người dùng là 'bạn'.\n"
    "- Trả lời trực tiếp câu hỏi, 3-6 dòng nếu câu hỏi đơn giản.\n"
    "- Nếu có giá, giờ, đường đi, lịch trình: dùng bullet ngắn, dễ quét.\n"
    "- Không dùng emoji hoặc icon trang trí tùy ý.\n"
    "- Không quảng cáo quá đà, không nói kiểu đọc dữ liệu thô.\n\n"
    "QUY TẮC DỮ LIỆU:\n"
    "1. Chỉ dùng dữ liệu tham khảo được cung cấp, không bịa.\n"
    "2. Nếu thiếu dữ liệu phù hợp, nói rõ: 'Mình chưa có dữ liệu chi tiết về vấn đề này'.\n"
    "3. Với giá vé, giờ vận hành, thời tiết, sự kiện: nhắc người dùng kiểm tra lại nguồn chính thức trước khi đi.\n"
    "4. Không nói 'theo dữ liệu nội bộ', 'dựa trên context' hoặc câu tương tự.\n"
    "5. Nếu câu hỏi ngoài Núi Bà Đen/Tây Ninh, lịch sự giới hạn phạm vi hỗ trợ.\n"
    "6. Khi câu hỏi nhắc một địa điểm cụ thể, ưu tiên trả lời đúng địa điểm đó; không trộn sang địa điểm khác.\n"
    "7. Với câu hỏi giá vé: nhóm theo loại vé, dùng markdown rõ ràng, mỗi bullet ngắn; rà chính tả và khoảng trắng trước khi trả lời.\n"
)


def truncate_text(text, max_chars=MAX_TOTAL_CONTEXT_CHARS):
    text = str(text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0].strip() + "..."


def _format_contexts(contexts):
    from .domain import is_price_related, build_price_answer
    price_answer = build_price_answer("", contexts or [])
    if price_answer:
        return price_answer
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


def build_system_prompt(contexts=None):
    context_block = _format_contexts(contexts or []) or "(không có dữ liệu liên quan)"
    return (
        SYSTEM_PROMPT
        + "\n\nDỮ LIỆU THAM KHẢO ĐƯỢC PHÉP DÙNG:\n"
        + context_block
        + "\n\nHãy trả lời tự nhiên cho người dùng, chỉ dùng dữ liệu ở trên."
    )


def build_messages(question, contexts=None, history=None):
    messages = []
    messages.extend(history or [])
    messages.append({"role": "user", "content": str(question or "").strip()})
    return messages


def fallback_rag_answer(question, contexts=None):
    contexts = contexts or []
    question = str(question or "").strip()

    if not question:
        return "Bạn nhập câu hỏi giúp mình nhé."

    if not contexts:
        return (
            "Mình chưa tìm thấy thông tin phù hợp trong dữ liệu hiện có. "
            "Bạn có thể hỏi cụ thể hơn về giá vé, đường đi, thời điểm tham quan "
            "hoặc hoạt động tại Núi Bà Đen nha."
        )

    from .domain import is_price_related, build_price_answer
    price_answer = build_price_answer(question, contexts)
    if price_answer:
        return price_answer

    ctx = contexts[0] or {}
    title = ctx.get("title") or "Thông tin Núi Bà Đen"
    fields = extract_fields(ctx.get("text", ""))

    details = []
    answer = field(fields, "answer")
    location = field(fields, "location")
    short_desc = field(fields, "short_desc")
    highlight = field(fields, "highlight")
    best_time = field(fields, "best_time")
    duration = field(fields, "duration")
    transport = field(fields, "transport")
    note = field(fields, "note")

    if answer:
        details.append(answer)
    if location:
        details.append(f"Vị trí: {location}")
    if short_desc:
        details.append(short_desc)
    if highlight and highlight != short_desc:
        details.append(f"Nổi bật: {highlight}")
    if best_time:
        details.append(f"Thời điểm phù hợp: {best_time}")
    if duration:
        details.append(f"Thời lượng gợi ý: {duration}")
    if transport:
        details.append(f"Di chuyển: {transport}")
    if note:
        details.append(f"Lưu ý: {note}")

    if not details:
        details.append(truncate_text(ctx.get("text", ""), max_chars=700))

    return "\n".join([f"Mình gửi bạn thông tin về **{title}**:"] + details[:7])
