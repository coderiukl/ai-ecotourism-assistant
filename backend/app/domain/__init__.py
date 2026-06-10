"""Domain layer for Nui Ba Den RAG chatbot.

Centralizes all business rules previously scattered across prompts.py,
vector_store.py, and rag.py:
  - field aliases / normalization
  - query classification (price, route, hours, activity)
  - price analysis (grouping, formatting, dedup)
  - retrieval scoring (intent bonus, keyword bonus)

Adding a new field alias or scoring rule means editing this file only.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Field registry
# ---------------------------------------------------------------------------

FIELD_ALIASES: Dict[str, List[str]] = {
    "location": ["Vị trí", "location", "area", "address_or_location", "place_name"],
    "answer": ["Answer hint", "answer", "answer_snippet", "Trả lời"],
    "short_desc": [
        "Mô tả ngắn",
        "description_short",
        "description",
        "description_detail",
        "content",
        "Nội dung",
    ],
    "highlight": ["Điểm nổi bật", "highlight"],
    "best_time": ["Thời điểm đẹp", "best_time", "season_or_time", "opening_time"],
    "duration": ["Thời lượng", "estimated_duration", "duration"],
    "transport": ["Di chuyển", "transport", "transport_mode", "navigation_note"],
    "service_name": ["service_name", "Dịch vụ", "title"],
    "direction": ["direction", "Direction"],
    "day_type": ["valid_day_type", "Valid day type"],
    "customer_type": ["customer_type", "Customer type"],
    "price_vnd": ["price_vnd", "Price VND"],
    "adult_price": ["adult_price_vnd", "Giá người lớn"],
    "child_price": ["child_price_vnd", "Giá trẻ em"],
    "combo_price": ["combo_price_vnd", "Giá combo"],
    "note": ["Ghi chú", "note", "conditions", "safety_note", "verification_note"],
}


def slugify(value: str) -> str:
    if not value:
        return ""
    value = str(value).replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")


def first_value(fields: Dict[str, str], names: Sequence[str]) -> str:
    for name in names:
        value = fields.get(name, "")
        if value:
            return str(value).strip()
    return ""


def field(fields: Dict[str, str], alias_name: str) -> str:
    return first_value(fields, FIELD_ALIASES[alias_name])


def extract_fields(text: str) -> Dict[str, str]:
    lines = [line.strip() for line in str(text or "").split("\n") if line.strip()]
    fields: Dict[str, str] = {}
    current_key: Optional[str] = None
    for line in lines:
        if ":" in line and not line.startswith("-") and not line.startswith("["):
            key, value = line.split(":", 1)
            current_key = key.strip()
            fields[current_key] = value.strip()
        elif current_key:
            fields[current_key] = (fields.get(current_key, "") + " " + line).strip()
    return fields


# ---------------------------------------------------------------------------
# Query classification
# ---------------------------------------------------------------------------

GENERIC_ALIAS_TOKENS = {
    "nui", "ba", "den", "tay", "ninh", "khu", "du", "lich", "diem",
}
ACTION_ALIAS_TOKENS = {
    "kham", "pha", "tham", "quan", "check", "in", "chup", "anh",
    "trai", "nghiem", "hanh", "huong", "ngam", "thuong", "thuc",
    "di", "le", "mua", "san", "may",
}

PRICE_TOKENS = {"gia", "ve", "phi", "ticket", "price", "cost", "combo", "buffet"}
ROUTE_TOKENS = {"duong", "di", "xe", "route", "map", "toa", "do"}
HOURS_TOKENS = {"gio", "may", "time", "open", "dong", "mo", "cua"}
ACTIVITY_TOKENS = {"choi", "lam", "activity", "activities", "tham", "quan", "check", "in"}


def query_tokens(question: str) -> set:
    return set(re.findall(r"[a-z0-9]+", slugify(question or "")))


def is_price_related(question: str) -> bool:
    return bool(query_tokens(question) & PRICE_TOKENS)


def is_route_related(question: str) -> bool:
    return bool(query_tokens(question) & ROUTE_TOKENS)


def is_hours_related(question: str) -> bool:
    return bool(query_tokens(question) & HOURS_TOKENS)


def is_activity_related(question: str) -> bool:
    return bool(query_tokens(question) & ACTIVITY_TOKENS)


# ---------------------------------------------------------------------------
# Price analysis
# ---------------------------------------------------------------------------

_PRICE_REPLACEMENTS = {
    "baogồm": "bao gồm",
    "baogom": "bao gồm",
    "cổg": "cổng",
    "cong": "cổng",
    "trẻ emlà": "trẻ em là",
    "tre emla": "trẻ em là",
    "người lớnlà": "người lớn là",
    "nguoi lonla": "người lớn là",
    "chưabao": "chưa bao",
    "chuabao": "chưa bao",
}


def clean_answer_text(text: str) -> str:
    text = str(text or "").strip()
    for old, new in _PRICE_REPLACEMENTS.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    return text.strip()


def format_price(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if re.fullmatch(r"\d+(?:\.0)?", value):
        return f"{int(float(value)):,}".replace(",", ".") + ".000đ"
    return value


def normalize_customer(value: str) -> str:
    value = slugify(value).replace("_", " ")
    if "tre" in value or "child" in value:
        return "Trẻ em"
    if "lon" in value or "adult" in value:
        return "Người lớn"
    return "Khách"


def ticket_group(service_name: str) -> str:
    slug = slugify(service_name)
    if "cong" in slug:
        return "Vé cổng"
    if "combo" in slug:
        return "Combo"
    if "buffet" in slug:
        return "Buffet"
    if "cap" in slug or "tuyen" in slug:
        return "Cáp treo"
    return "Dịch vụ khác"


def ticket_label(service_name: str, direction: str, day_type: str = "") -> str:
    label = str(service_name or "Dịch vụ").strip()
    label = re.sub(r"^Vé\s+", "", label, flags=re.I).strip()
    label = re.sub(r"^tuyến\s+cáp\s+", "", label, flags=re.I).strip()
    label = re.sub(r"^cáp\s+", "", label, flags=re.I).strip()
    if direction and str(direction).strip().lower() not in {"không áp dụng", "khong ap dung"}:
        direction_text = str(direction).strip()
        if direction_text.lower() not in label.lower():
            label = f"{label} {direction_text}"
    if day_type and str(day_type).strip().lower() not in {"tất cả", "tat ca", "all"}:
        label = f"{label} - {str(day_type).strip()}"
    return clean_answer_text(label[:1].upper() + label[1:])


def price_note(service_name: str, fields: Dict[str, str]) -> str:
    slug = slugify(service_name)
    conditions = clean_answer_text(first_value(fields, ["Conditions", "conditions"]))
    if "cong" in slug:
        return "chưa bao gồm cáp treo"
    if "tam_an" in slug and conditions:
        return conditions
    return ""


def build_price_answer(question: str, contexts: List[Dict[str, Any]]) -> str:
    if not is_price_related(question):
        return ""

    grouped: Dict[str, Dict[Tuple[str, str], List[Tuple[str, str]]]] = {}
    seen: set = set()

    for ctx in contexts or []:
        fields = extract_fields(ctx.get("text", ""))
        service = field(fields, "service_name") or ctx.get("title") or "Dịch vụ"
        direction = field(fields, "direction")
        day_type = field(fields, "day_type")
        customer = normalize_customer(field(fields, "customer_type"))
        price = (
            format_price(field(fields, "price_vnd"))
            or format_price(field(fields, "adult_price"))
            or format_price(field(fields, "child_price"))
            or format_price(field(fields, "combo_price"))
        )
        if not price:
            continue

        group = ticket_group(service)
        label = ticket_label(service, direction, day_type)
        note = price_note(service, fields)
        key = (group, label, customer, price, note)
        if key in seen:
            continue
        seen.add(key)

        grouped.setdefault(group, {}).setdefault((label, note), []).append((customer, price))
        if len(seen) >= 10:
            break

    if not grouped:
        return ""

    lines = ["Mình thấy dữ liệu giá phù hợp như sau:"]
    group_order = ["Vé cổng", "Cáp treo", "Combo", "Buffet", "Dịch vụ khác"]
    for group in group_order:
        items = grouped.get(group)
        if not items:
            continue
        lines.append("")
        lines.append(f"**{group}**")
        for (label, note), prices in items.items():
            customer_prices = "; ".join(f"{customer}: {price}" for customer, price in prices)
            note_text = f" ({note})." if note else "."
            lines.append(f"- {label}: {customer_prices}{note_text}")

    lines.append("")
    lines.append(
        "**Lưu ý:** Giá có thể thay đổi theo ngày hoặc khung giờ. "
        "Bạn nên kiểm tra lại Sun World hoặc kênh đặt vé chính thức trước khi đi nha."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Retrieval scoring
# ---------------------------------------------------------------------------

def intent_bonus(question: str, metadata: Dict[str, Any]) -> float:
    doc_type = metadata.get("type")
    if is_price_related(question):
        return 0.6 if doc_type == "service_pricing" else 0.0
    if doc_type == "service_pricing":
        return -0.6
    if is_activity_related(question):
        if doc_type == "activity":
            return 0.4
        if doc_type == "destination":
            return 0.6
    return 0.0


def keyword_bonus(question: str, document: Dict[str, Any]) -> float:
    tokens = query_tokens(question)
    if not tokens:
        return 0.0
    haystack = slugify(
        " ".join(str(document.get(field, "")) for field in ("title", "type", "text"))
    )
    matched = sum(1 for token in tokens if token and token in haystack)
    return min(0.3, matched * 0.04)


# ---------------------------------------------------------------------------
# Destination resolution (facade over rag.py to avoid duplicating alias logic)
# ---------------------------------------------------------------------------

def resolve_target_codes(question: str, destination_id: Optional[int] = None) -> Tuple[List[str], bool]:
    from .rag import resolve_target_codes as _resolve
    return _resolve(question, destination_id=destination_id)
