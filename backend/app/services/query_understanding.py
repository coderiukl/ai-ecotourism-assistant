from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class QueryUnderstanding:
    intent: str
    should_clarify: bool = False
    clarify_question: str | None = None


def normalize(text: str) -> str:
    value = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return value


INTENT_KEYWORDS: dict[str, set[str]] = {
    "price": {
        "giá",
        "vé",
        "bao nhiêu",
        "combo",
        "buffet",
        "cáp treo",
        "chi phí",
        "tiền",
        "mua vé",
    },
    "opening_hours": {
        "giờ",
        "mở cửa",
        "đóng cửa",
        "lịch",
        "vận hành",
        "mấy giờ",
        "thời gian",
    },
    "activities": {
        "chơi",
        "tham quan",
        "trải nghiệm",
        "check in",
        "làm gì",
        "có gì chơi",
        "có gì tham quan",
        "có gì hay",
        "có gì thú vị",
        "có gì vui",
        "có gì xem",
        "điểm nổi bật",
        "hoạt động",
    },
    "transport": {
        "đi sao",
        "đường",
        "di chuyển",
        "xe",
        "bus",
        "bản đồ",
        "lối đi",
        "gửi xe",
    },
    "itinerary": {
        "lịch trình",
        "1 ngày",
        "một ngày",
        "nửa ngày",
        "buổi sáng",
        "buổi chiều",
        "bao lâu",
        "mất mấy tiếng",
    },
    "food_stay": {
        "ăn",
        "uống",
        "đặc sản",
        "nhà hàng",
        "khách sạn",
        "ở đâu",
        "lưu trú",
    },
    "safety": {
        "an toàn",
        "lưu ý",
        "nguy hiểm",
        "cấp cứu",
        "y tế",
        "trẻ em",
        "người già",
    },
    "weather": {
        "thời tiết",
        "mưa",
        "nắng",
        "mùa khô",
        "mùa mưa",
        "săn mây",
        "nhiệt độ",
        "mang áo",
    },
    "events_culture": {
        "sự kiện",
        "lễ hội",
        "văn hóa",
        "tâm linh",
        "hành hương",
        "lịch sử",
        "phật giáo",
    },
    "photography": {
        "chụp ảnh",
        "sống ảo",
        "góc chụp",
        "tạo dáng",
        "hoàng hôn",
        "bình minh",
        "check-in",
    },
    "family_accessibility": {
        "gia đình",
        "trẻ nhỏ",
        "em bé",
        "đi cùng em bé",
        "đi cùng trẻ nhỏ",
        "xe lăn",
        "người khuyết tật",
        "phụ nữ mang thai",
        "người lớn tuổi",
    },
    "contact": {
        "hotline",
        "liên hệ",
        "số điện thoại",
        "website",
        "đặt vé",
        "booking",
        "địa chỉ",
    },
    "facilities": {
        "nhà vệ sinh",
        "bãi xe",
        "tiện ích",
        "dịch vụ",
        "wifi",
        "ghế nghỉ",
        "mua sắm",
    },
}


AMBIGUOUS_SHORT_WORDS = {
    "giá",
    "vé",
    "giờ",
    "buffet",
    "đi sao",
    "có gì",
    "ăn gì",
    "chơi gì",
}


def _has_any(question: str, words: set[str]) -> bool:
    return any(word in question for word in words)


def _detect_intent(question: str) -> str:
    scores = {
        intent: sum(
            max(1, len(keyword.split()))
            for keyword in keywords
            if keyword in question
        )
        for intent, keywords in INTENT_KEYWORDS.items()
    }
    intent, score = max(scores.items(), key=lambda item: item[1])
    return intent if score > 0 else "general"


def understand_query(question: str, destination_name: str | None = None) -> QueryUnderstanding:
    q = normalize(question)
    tokens = q.split()
    place = destination_name or "địa điểm này"
    intent = _detect_intent(q)

    if not q:
        return QueryUnderstanding(
            intent="general",
            should_clarify=True,
            clarify_question="Bạn muốn hỏi về giá vé, giờ mở cửa, cách đi hay có gì tham quan?",
        )

    if len(tokens) <= 2 and q in AMBIGUOUS_SHORT_WORDS:
        if intent == "price":
            return QueryUnderstanding(
                intent=intent,
                should_clarify=True,
                clarify_question=f"Bạn muốn hỏi giá vé tham quan {place}, hay giá cáp treo/combo/buffet?",
            )

        if intent == "opening_hours":
            return QueryUnderstanding(
                intent=intent,
                should_clarify=True,
                clarify_question=f"Bạn muốn hỏi giờ mở cửa của {place}, hay giờ vận hành cáp treo?",
            )

        return QueryUnderstanding(
            intent=intent,
            should_clarify=True,
            clarify_question=(
                "Bạn hỏi rõ hơn một chút nhé: bạn muốn biết giá vé, giờ mở cửa, "
                "cách đi hay có gì tham quan?"
            ),
        )

    return QueryUnderstanding(intent=intent)
