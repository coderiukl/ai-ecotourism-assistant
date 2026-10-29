from __future__ import annotations

from datetime import date
import re
from typing import Any
import unicodedata

MAX_CONTEXT_TEXT_CHARS = 1200
MAX_CONTEXT_BLOCKS = 6


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _normalize_text(value: Any) -> str:
    """Normalize Vietnamese text for the small offline intent matcher."""
    text = unicodedata.normalize("NFD", _clean_text(value).lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", text.replace("đ", "d")).strip()


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _context_fields(contexts: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Read the structured key/value lines embedded in retrieved documents."""
    fields: dict[str, list[str]] = {}
    for context in contexts:
        for line in str(context.get("text") or "").splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = _normalize_text(key).replace(" ", "_")
            value = _clean_text(value)
            if value and value not in fields.setdefault(key, []):
                fields[key].append(value)
    return fields


def _first_field(fields: dict[str, list[str]], *keys: str) -> str:
    for key in keys:
        values = fields.get(key)
        if values:
            return values[0]
    return ""


SYSTEM_PROMPT = """
Bạn là "Núi Bà AI", một hướng dẫn viên du lịch địa phương, dễ gần tại Núi Bà Đen, Tây Ninh. Hãy trò chuyện như một người bạn địa phương am hiểu — tự nhiên, linh hoạt, không máy móc hay lặp công thức. Xưng "mình", gọi người dùng là "bạn".

Chỉ dùng thông tin tham khảo được cung cấp trong yêu cầu; không tự bịa giá vé, giờ mở cửa, số điện thoại, website, khuyến mãi, sự kiện hoặc lịch vận hành. Nếu không có thông tin chắc chắn, nói thẳng là mình chưa chắc, rồi gợi ý hướng khác nếu có thể — đừng chỉ dừng ở một câu từ chối khô khan.

Địa điểm đang chọn (nếu có) là trọng tâm; hiểu "ở đây", "chỗ này" là địa điểm đó, và không tự lan sang địa điểm khác khi người dùng không hỏi. Nếu câu hỏi nằm ngoài phạm vi du lịch Núi Bà Đen, trả lời ngắn gọn, thân thiện rằng mình chỉ hỗ trợ thông tin tham quan ở đây.

Với thông tin dễ thay đổi (giá vé, giờ vận hành, cáp treo, buffet, sự kiện, khuyến mãi), nhắc nhẹ là nên kiểm tra lại gần ngày đi — không cần công thức "Lưu ý:" cứng nhắc mỗi lần, chỉ cần tự nhiên lồng vào câu. Đừng coi một ưu đãi hoặc sự kiện cũ còn hiệu lực nếu ngày áp dụng đã qua hoặc bài viết không xác nhận còn hiệu lực hiện tại.

Khi có thông tin được đánh dấu "Cập nhật trực tiếp từ Sun World", đó là nguồn ưu tiên cho dữ liệu dễ thay đổi. Chỉ dẫn link nguồn đó khi nó thực sự liên quan trực tiếp đến câu hỏi và bạn có dùng thông tin từ đó — đừng gắn link theo thói quen nếu câu trả lời không thật sự cần đến nó. Tối đa 1-2 nguồn, đặt trên dòng riêng dạng "Nguồn: [Xem trang chính thức](URL)", không chèn URL giữa câu.

Nếu câu hỏi quá ngắn hoặc mơ hồ, hỏi lại một câu ngắn gọn để làm rõ ý, đừng đoán bừa.

Trả lời đi thẳng vào điều người dùng hỏi, theo văn phong hội thoại bình thường — không bắt buộc phải mở đầu hay kết thúc theo khuôn mẫu cố định, và tránh lặp lại y nguyên các câu mở đầu giữa các lượt trả lời. Với lời chào, chào lại tự nhiên và gợi ý ngắn vài điều có thể giúp được, không cần dốc hết thông tin địa điểm ngay. Độ dài và cách trình bày nên theo đúng độ phức tạp của câu hỏi: vài câu cho câu hỏi đơn giản, danh sách khi liệt kê, bảng khi so sánh giá/lịch/phương án, dài hơn khi người dùng cần lịch trình chi tiết. Dùng gạch đầu dòng khi có từ 2 ý trở lên, có thể thêm một gợi ý thực tế kiểu "Mẹo:" nếu hợp lý. Luôn có khoảng trắng giữa chữ và số (ví dụ "chiều 15:30", "30 phút"). Không nhắc đến các từ nội bộ như context, sheet, Excel, database hay "dữ liệu được cung cấp" — viết lại mọi thông tin thành câu văn tự nhiên, không copy nguyên field/value thô.
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

        source_url = _clean_text(context.get("source_url"))
        if source_url:
            source_label = (
                "Cập nhật trực tiếp từ Sun World"
                if context.get("type") == "live_sunworld"
                else "Nguồn tham khảo"
            )
            parts.append(f"{source_label}: {source_url}")

        last_updated = _clean_text(context.get("last_updated"))
        if last_updated:
            parts.append(f"Ngày cập nhật nguồn: {last_updated}")

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

    lines = [f"- {label}: {_clean_text(value)}" for label, value in fields if _clean_text(value)]
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
NGÀY HIỆN TẠI: {date.today().isoformat()}

ĐỊA ĐIỂM ĐANG CHỌN:
{destination_scope}

PHẠM VI TRẢ LỜI:
- Ưu tiên trả lời về địa điểm đang chọn.
- Nếu thiếu thông tin riêng cho địa điểm này, nói rõ là mình chưa có thông tin chắc chắn.
- Không suy đoán giá, giờ vận hành hoặc chính sách từ địa điểm khác.

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
    """Useful, natural response when the external language model is unavailable."""
    normalized = _normalize_text(question)
    destination = destination or {}
    name = _clean_text(destination.get("name")) or "địa điểm này"
    fields = _context_fields(contexts)

    greetings = ("xin chao", "chao ban", "hello", "hi", "hey", "alo")
    if normalized in greetings or _has_any(normalized, ("xin chao", "hello")):
        return (
            "Chào bạn! Mình là AI Guide tại Núi Bà Đen 👋\n\n"
            "Mình có thể giúp bạn tìm **điểm tham quan, giờ đi đẹp, cách di chuyển, "
            "giá vé** hoặc gợi ý lịch trình. Bạn muốn khám phá điều gì trước?"
        )

    if _has_any(normalized, ("co gi choi", "choi gi", "lam gi", "tham quan gi", "diem noi bat")):
        highlights = [item.strip() for item in re.split(r"[;•]", _clean_text(destination.get("highlight"))) if item.strip()]
        description = _clean_text(destination.get("short_description"))
        duration = _clean_text(destination.get("estimated_duration"))
        lines = [f"Ở **{name}**, bạn có thể vừa tham quan, chiêm bái vừa chụp ảnh check-in."]
        if description:
            lines.append(description)
        if highlights:
            lines.append("\n".join(f"- {item[0].upper() + item[1:]}" for item in highlights[:4]))
        if duration:
            lines.append(f"Bạn nên dành khoảng **{duration}** để tham quan thoải mái.")
        return "\n\n".join(lines)

    asks_opening_hours = _has_any(normalized, ("gio mo cua", "gio dong cua", "gio hoat dong", "lich van hanh"))
    asks_best_time = _has_any(normalized, ("nen di gio nao", "di luc nao", "may gio", "thoi diem nao", "mua nao", "luc nao dep"))
    if asks_best_time and not asks_opening_hours:
        best_time = _clean_text(destination.get("best_time")) or _first_field(fields, "best_time", "answer", "recommendation")
        if best_time:
            return (
                f"Bạn nên đi **{best_time}**. Khung giờ này thường dễ chịu và thuận lợi hơn để ngắm cảnh, chụp ảnh.\n\n"
                "Mẹo: Nếu muốn ít đông, bạn nên đến sớm và kiểm tra thời tiết trước khi lên núi."
            )

    if _has_any(normalized, ("di bang cach nao", "di nhu the nao", "cach di", "duong di", "di chuyen")):
        transport = _clean_text(destination.get("transport")) or _first_field(fields, "transport", "navigation_note", "answer")
        navigation_note = _clean_text(destination.get("navigation_note"))
        map_url = _clean_text(destination.get("google_maps_url"))
        if transport or navigation_note:
            route = transport[:1].lower() + transport[1:] if transport else navigation_note[:1].lower() + navigation_note[1:]
            parts = [f"Để đến **{name}**, bạn đi {route}."]
            if navigation_note and navigation_note.lower() not in transport.lower():
                parts.append(f"Mốc dễ nhớ: {navigation_note}.")
            if map_url:
                parts.append(f"[Mở chỉ đường trên Google Maps]({map_url})")
            return "\n\n".join(parts)

    if _has_any(normalized, ("gia ve", "bao nhieu tien", "chi phi", "gia cap treo")):
        answer = _first_field(fields, "answer", "price_note")
        if _has_any(_normalize_text(answer), ("file", "sheet", "database")):
            answer = "Giá vé thay đổi theo tuyến cáp, đối tượng khách và chương trình áp dụng. Mình chưa có mức giá hiện hành đủ chắc chắn để báo bạn."
        if answer:
            return f"{answer}\n\n**Lưu ý:** Giá có thể thay đổi theo ngày và chương trình ưu đãi; bạn nên kiểm tra lại nguồn chính thức trước khi đi."

    if asks_opening_hours:
        answer = _first_field(fields, "answer", "answer_hint", "operation_hours", "opening_hours", "time", "note")
        if answer:
            return f"{answer}\n\n**Lưu ý:** Giờ vận hành có thể thay đổi theo ngày hoặc điều kiện thời tiết, bạn nên kiểm tra lại trước chuyến đi."

    direct_answer = _first_field(
        fields,
        "answer",
        "answer_hint",
        "answer_hit",
        "answer_snippet",
        "recommendation",
        "content",
        "description_detail",
        "description_short",
    )
    if direct_answer:
        return f"Về **{name}**: {direct_answer}\n\nBạn muốn mình nói thêm về cách đi, thời điểm đẹp hay các hoạt động ở đây?"

    description = _clean_text(destination.get("description_detail") or destination.get("short_description"))
    if description:
        return f"**{name}** là một điểm đáng ghé tại Núi Bà Đen. {description}\n\nBạn muốn biết thêm về cách đi, giờ tham quan hay điểm chụp ảnh đẹp?"

    return (
        "Mình chưa có thông tin đủ chắc chắn cho câu hỏi này. "
        "Bạn nói rõ hơn một chút nhé — chẳng hạn bạn muốn hỏi về giá vé, giờ hoạt động, cách đi hay điểm tham quan?"
    )
