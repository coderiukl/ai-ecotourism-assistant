"""Prompt helpers for Nui Ba Den RAG chatbot."""

import re
import unicodedata

MAX_CONTEXT_CHARS = 1200
MAX_TOTAL_CONTEXT_CHARS = 4200

SYSTEM_PROMPT = (
    "Bạn là Núi Bà AI, trợ lý du lịch của Núi Bà Đen (Tây Ninh). "
    "Bạn trả lời như một người địa phương am hiểu, thân thiện và thực tế.\n\n"
    "PHONG CÁCH:\n"
    "- Xưng 'mình', gọi người dùng là 'bạn'.\n"
    "- Trả lời trực tiếp câu hỏi, 3-6 dòng nếu câu hỏi đơn giản.\n"
    "- Nếu có giá, giờ, đường đi, lịch trình: dùng bullet ngắn, dễ quét.\n"
    "- Không quảng cáo quá đà, không nói kiểu đọc dữ liệu thô.\n\n"
    "QUY TẮC DỮ LIỆU:\n"
    "1. Chỉ dùng dữ liệu tham khảo được cung cấp, không bịa.\n"
    "2. Nếu thiếu dữ liệu phù hợp, nói rõ: 'Mình chưa có dữ liệu chi tiết về vấn đề này'.\n"
    "3. Với giá vé, giờ vận hành, thời tiết, sự kiện: nhắc người dùng kiểm tra lại nguồn chính thức trước khi đi.\n"
    "4. Không nói 'theo dữ liệu nội bộ', 'dựa trên context' hoặc câu tương tự.\n"
    "5. Nếu câu hỏi ngoài Núi Bà Đen/Tây Ninh, lịch sự giới hạn phạm vi hỗ trợ.\n"
    "6. Khi câu hỏi nhắc một địa điểm cụ thể, ưu tiên trả lời đúng địa điểm đó; không trộn sang địa điểm khác.\n"
)

FIELD_ALIASES = {
    "location": ["Vị trí", "location", "area", "address_or_location", "place_name"],
    "answer": ["Answer hint", "answer", "answer_snippet", "Trả lời"],
    "short_desc": ["Mô tả ngắn", "description_short", "description", "description_detail", "content", "Nội dung"],
    "highlight": ["Điểm nổi bật", "highlight"],
    "best_time": ["Thời điểm đẹp", "best_time", "season_or_time", "opening_time"],
    "duration": ["Thời lượng", "estimated_duration", "duration"],
    "transport": ["Di chuyển", "transport", "transport_mode", "navigation_note"],
    "service_name": ["service_name", "Dịch vụ", "title"],
    "direction": ["direction"],
    "customer_type": ["customer_type"],
    "price_vnd": ["price_vnd", "Price VND"],
    "adult_price": ["adult_price_vnd", "Giá người lớn"],
    "child_price": ["child_price_vnd", "Giá trẻ em"],
    "combo_price": ["combo_price_vnd", "Giá combo"],
    "note": ["Ghi chú", "note", "conditions", "safety_note", "verification_note"],
}

def truncate_text(text, max_chars=MAX_CONTEXT_CHARS):
    text = str(text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0].strip() + "..."

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
            current_key = key.strip()
            fields[current_key] = value.strip()
        elif current_key:
            fields[current_key] = (fields.get(current_key, "") + " " + line).strip()

    return fields

def _first_value(fields, names):
    for name in names:
        value = fields.get(name, "")
        if value:
            return str(value).strip()
    return ""

def _field(fields, alias_name):
    return _first_value(fields, FIELD_ALIASES[alias_name])

def _slugify(value):
    value = str(value or "").replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")

def _is_price_question(question):
    tokens = set(_slugify(question).split("_"))
    return bool(tokens & {"gia", "ve", "phi", "ticket", "price", "cost", "combo", "buffet"})

def _format_price(value):
    value = str(value or "").strip()
    if not value:
        return ""
    if re.fullmatch(r"\d+(?:\.0)?", value):
        return f"{int(float(value)):,}".replace(",", ".") + ".000đ"
    return value

def _price_hint_answer(question, contexts):
    if not _is_price_question(question):
        return ""

    lines = []
    seen = set()

    for ctx in contexts or []:
        fields = _extract_fields(ctx.get("text", ""))
        hint = _field(fields, "answer")
        if hint:
            line = hint
        else:
            service = _field(fields, "service_name") or ctx.get("title") or "Dịch vụ"
            direction = _field(fields, "direction")
            customer = _field(fields, "customer_type")
            price = (
                _format_price(_field(fields, "price_vnd"))
                or _format_price(_field(fields, "adult_price"))
                or _format_price(_field(fields, "child_price"))
                or _format_price(_field(fields, "combo_price"))
            )
            if not price:
                continue
            label = " - ".join(part for part in [service, direction, customer] if part)
            line = f"{label}: {price}"

        if line in seen:
            continue
        seen.add(line)
        lines.append(f"- {line}")
        if len(lines) >= 8:
            break

    if not lines:
        return ""

    return "\n".join(
        ["Mình thấy dữ liệu giá phù hợp như sau:"]
        + lines
        + ["Giá có thể thay đổi theo ngày/khung giờ, bạn nên kiểm tra lại Sun World hoặc kênh đặt vé chính thức trước khi đi nha."]
    )

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

    price_answer = _price_hint_answer(question, contexts)
    if price_answer:
        return price_answer

    ctx = contexts[0] or {}
    title = ctx.get("title") or "Thông tin Núi Bà Đen"
    fields = _extract_fields(ctx.get("text", ""))

    details = []
    answer = _field(fields, "answer")
    location = _field(fields, "location")
    short_desc = _field(fields, "short_desc")
    highlight = _field(fields, "highlight")
    best_time = _field(fields, "best_time")
    duration = _field(fields, "duration")
    transport = _field(fields, "transport")
    note = _field(fields, "note")

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
