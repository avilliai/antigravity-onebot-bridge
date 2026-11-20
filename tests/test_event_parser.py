# -*- coding: utf-8 -*-
"""Unit tests for OneBot v11 / Milky event parser."""

import unittest
from agy_onebot.event_parser import parse_onebot_event


class TestEventParser(unittest.TestCase):

    def test_parse_private_message(self):
        raw = {
            "post_type": "message",
            "message_type": "private",
            "sub_type": "friend",
            "message_id": 12345,
            "user_id": 10001,
            "time": 1700000000,
            "raw_message": "Hello Bot!",
            "message": [
                {"type": "text", "data": {"text": "Hello Bot!"}}
            ],
            "sender": {"nickname": "Alice", "user_id": 10001}
        }
        parsed = parse_onebot_event(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.user_id, "10001")
        self.assertEqual(parsed.plain_text, "Hello Bot!")
        self.assertFalse(parsed.is_group)
        self.assertEqual(parsed.session_id, "private_10001")

    def test_parse_group_message_with_at(self):
        raw = {
            "post_type": "message",
            "message_type": "group",
            "sub_type": "normal",
            "message_id": 99999,
            "user_id": 10002,
            "group_id": 88888,
            "time": 1700000010,
            "raw_message": "[CQ:at,qq=123456] 你好呀",
            "message": [
                {"type": "at", "data": {"qq": "123456"}},
                {"type": "text", "data": {"text": " 你好呀"}},
                {"type": "image", "data": {"url": "https://example.com/pic.jpg"}}
            ],
            "sender": {"nickname": "Bob", "card": "BobCard", "role": "admin"}
        }
        parsed = parse_onebot_event(raw, bot_qq="123456")
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed.is_group)
        self.assertTrue(parsed.is_at_bot)
        self.assertEqual(parsed.sender_display_name, "BobCard")
        self.assertEqual(parsed.image_urls, ["https://example.com/pic.jpg"])
        self.assertEqual(parsed.session_id, "group_88888")


if __name__ == "__main__":
    unittest.main()
