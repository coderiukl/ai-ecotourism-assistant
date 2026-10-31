from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from app.db import postgres
from app.services import chat_service


class WebKnowledgeScoringTests(unittest.TestCase):
    def test_relevant_saved_source_scores_higher(self) -> None:
        question = "giá vé cáp treo Núi Bà Đen"
        relevant = {
            "title": "Giá vé cáp treo Núi Bà Đen",
            "content": "Thông tin giá vé và tuyến cáp treo mới nhất.",
            "search_query": "giá vé hiện tại",
        }
        unrelated = {
            "title": "Nhà hàng tại Tây Ninh",
            "content": "Gợi ý món ăn địa phương.",
            "search_query": "ăn gì",
        }

        self.assertGreater(
            postgres._web_knowledge_score(question, relevant),
            postgres._web_knowledge_score(question, unrelated),
        )


class WebKnowledgeFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_and_saved_sources_are_merged_and_cited(self) -> None:
        live = {
            "id": "web:live",
            "type": "live_web",
            "title": "Nguồn mới",
            "source_url": "https://official.example/new",
            "text": "Thông tin trực tiếp mới nhất",
        }
        stored = {
            "id": "stored-web:old",
            "type": "stored_web",
            "title": "Nguồn đã lưu",
            "source_url": "https://guide.example/old",
            "text": "Kinh nghiệm tham quan bổ sung",
        }
        local = {
            "id": "faq:1",
            "type": "faq",
            "title": "Dữ liệu nội bộ",
            "source_url": "",
            "text": "Thông tin nội bộ",
        }

        with (
            patch.object(chat_service, "retrieve", return_value=[local]),
            patch.object(chat_service.web_search, "search", AsyncMock(return_value=[live])),
            patch.object(
                chat_service.postgres,
                "search_web_knowledge",
                AsyncMock(return_value=[stored]),
            ),
            patch.object(
                chat_service.postgres,
                "save_web_knowledge",
                AsyncMock(return_value=1),
            ) as save_mock,
        ):
            contexts = await chat_service.contexts_for_question(
                "Có gì tham quan ở đây?",
                destination_id=None,
                intent="activities",
                destination_name="Núi Bà Đen",
            )

        self.assertEqual([item["type"] for item in contexts], ["live_web", "stored_web", "faq"])
        self.assertEqual(contexts[0]["citation_index"], 1)
        self.assertEqual(contexts[1]["citation_index"], 2)
        save_mock.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
