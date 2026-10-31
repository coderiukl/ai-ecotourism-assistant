from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services import chat_service, llm
from app.services.query_understanding import understand_query


class DestinationScopeFeedbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.destinations = {
            1: {"id": 1, "name": "Tôn tượng Phật Bà Tây Bổ Đà Sơn"},
            2: {"id": 2, "name": "Chùa Hang"},
        }

    def test_total_cable_car_price_ignores_selected_destination(self) -> None:
        with patch.object(chat_service.postgres, "destinations", return_value=self.destinations):
            destination_id, destination = chat_service.resolve_destination(
                "Tổng giá vé cáp treo Núi Bà Đen hiện tại là bao nhiêu?",
                selected_destination_id=1,
            )

        self.assertIsNone(destination_id)
        self.assertIsNone(destination)

    def test_cable_car_question_ignores_selected_destination(self) -> None:
        with patch.object(chat_service.postgres, "destinations", return_value=self.destinations):
            destination_id, destination = chat_service.resolve_destination(
                "Giá vé cáp treo bao nhiêu?",
                selected_destination_id=1,
            )

        self.assertIsNone(destination_id)
        self.assertIsNone(destination)

    def test_here_keeps_selected_destination(self) -> None:
        with patch.object(chat_service.postgres, "destinations", return_value=self.destinations):
            destination_id, destination = chat_service.resolve_destination(
                "Giá vé ở đây bao nhiêu?",
                selected_destination_id=1,
            )

        self.assertEqual(destination_id, 1)
        self.assertEqual(destination, self.destinations[1])

    def test_explicit_destination_wins_over_global_service_rule(self) -> None:
        with patch.object(chat_service.postgres, "destinations", return_value=self.destinations):
            destination_id, destination = chat_service.resolve_destination(
                "Cáp treo đi Chùa Hang có giá bao nhiêu?",
                selected_destination_id=1,
            )

        self.assertEqual(destination_id, 2)
        self.assertEqual(destination, self.destinations[2])

    def test_short_cable_car_question_is_answered_without_clarification(self) -> None:
        result = understand_query("cáp treo", "Chùa Hang")

        self.assertEqual(result.intent, "price")
        self.assertFalse(result.should_clarify)


class AnswerSpacingFeedbackTests(unittest.TestCase):
    def test_repairs_price_units_and_concatenated_sentences(self) -> None:
        result = llm.polish_answer("Giá vé:300.000đ/người.Lưu ý:kiểm tra trước khi đi.")

        self.assertEqual(
            result,
            "Giá vé: 300.000 đ/người. Lưu ý: kiểm tra trước khi đi.",
        )


if __name__ == "__main__":
    unittest.main()
