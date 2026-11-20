# -*- coding: utf-8 -*-
"""Unit tests for OneBot v11 & Milky Protocol event parser."""

import unittest
from agy_onebot.event_parser import parse_onebot_event
from agy_onebot.milky_protocol import onebot_to_milky_api


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

    def test_parse_milky_protocol_event(self):
        milky_raw = {
            "event_type": "message_receive",
            "self_id": 123456,
            "time": 1700000020,
            "data": {
                "message_scene": "group",
                "peer_id": 77777,
                "sender_id": 30001,
                "message_seq": 888,
                "segments": [
                    {"type": "mention", "data": {"user_id": 123456}},
                    {"type": "text", "data": {"text": " 白白早上好！"}},
                    {"type": "image", "data": {"temp_url": "https://example.com/milky_pic.jpg"}}
                ],
                "group_member": {
                    "nickname": "Charlie",
                    "card": "CharlieCard",
                    "role": "member"
                }
            }
        }
        parsed = parse_onebot_event(milky_raw, bot_qq="123456")
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed.is_group)
        self.assertEqual(parsed.group_id, "77777")
        self.assertEqual(parsed.user_id, "30001")
        self.assertEqual(parsed.message_id, "888")
        self.assertEqual(parsed.plain_text, "白白早上好！")
        self.assertTrue(parsed.is_at_bot)
        self.assertEqual(parsed.sender_display_name, "CharlieCard")
        self.assertEqual(parsed.image_urls, ["https://example.com/milky_pic.jpg"])
        self.assertEqual(parsed.session_id, "group_77777")

    def test_milky_api_mapping(self):
        endpoint, body = onebot_to_milky_api("send_group_msg", {
            "group_id": 77777,
            "message": "Hello from Antigravity"
        })
        self.assertEqual(endpoint, "send_group_message")
        self.assertEqual(body["group_id"], 77777)
        self.assertEqual(body["message"], [{"type": "text", "data": {"text": "Hello from Antigravity"}}])


if __name__ == "__main__":
    unittest.main()
