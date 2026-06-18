from __future__ import annotations

import re
from dataclasses import dataclass

@dataclass
class QueryUnderstanding:
    intent: str
    should_clarify: bool
    clarify_question: str | None = None

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())

def understand_query(question: str, destination_name: str | None = None) -> QueryUnderstanding:
    q = normalize(question)
    tokens = q.split()
    place = destination_name or 'địa điểm này'

    price_words = {"giá", "vé", "tiền", "combo", "buffet", "cáp treo", "bao nhiêu"}
    hour_words = {"giờ", "mở cửa", "đóng cửa", "lịch", "vận hành"}
    activity_words = {"chơi", "tham quan", "trải nghiệm", "check in", "làm gì"}
    transport_words = {"đi", "đường", "bus", "di chuyển"}
    itinerary_words = {"lịch trình", "1 ngày", "nửa ngày", "buổi sáng", "buổi chiều"}

    def has_any(words: set[str]) -> bool:
        return any(word in q for word in words)
    
    if len(tokens) <= 2:
        if has_any(price_words):
            return QueryUnderstanding(
                intent="price",
                should_clarify=True,
                clarify_question=f"Bạn muốn hỏi giá vé của {place}, hay giá cáp treo/combo/buffet?",
            )
        
        if has_any(hour_words):
            return QueryUnderstanding(
                intent="opening_hours",
                shoud_clarify=True,
                clarify_question=f"Bạn muốn hỏi giờ mở cửa của {place}, hay giờ vận hành cáp treo?"
            )
        
        return QueryUnderstanding(
            intent="general",
            shoud_clarify=True,
            clarify_question="Bạn hỏi rõ hơn một chút nhé: bạn muốn biết giá vé, giờ mở cửa, cách đi hay có gì chơi?"
        )

    if has_any(price_words):
        return QueryUnderstanding("price", False)
    
    if has_any(hour_words):
        return QueryUnderstanding("opening_hours", False)
    
    if has_any(hour_words):
        return QueryUnderstanding("activities", False)
    
    if has_any(hour_words):
        return QueryUnderstanding("transport", False)
    
    if has_any(hour_words):
        return QueryUnderstanding("itinerary", False)
    
    return QueryUnderstanding("general", False)