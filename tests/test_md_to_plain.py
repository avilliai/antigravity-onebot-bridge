# -*- coding: utf-8 -*-
"""Unit tests for Markdown to Plain converter and text splitter."""

import unittest
from agy_onebot.md_to_plain import md_to_plain, split_for_qq, truncate_text, truncate_text_tail


class TestMdToPlain(unittest.TestCase):

    def test_strip_code_fences(self):
        md = "```python\nprint('hello')\n```"
        self.assertEqual(md_to_plain(md), "print('hello')")

    def test_links_and_images(self):
        md = "Here is [Google](https://google.com) and ![Cat](https://cat.jpg)"
        plain = md_to_plain(md)
        self.assertIn("Google (https://google.com)", plain)
        self.assertIn("[图片: Cat]", plain)

    def test_formatting_cleanup(self):
        md = "### Header\n**bold** and *italic* and ~~deleted~~"
        plain = md_to_plain(md)
        self.assertEqual(plain, "Header\nbold and italic and deleted")

    def test_table_cleanup(self):
        md = "| Col1 | Col2 |\n|---|---|\n| Val1 | Val2 |"
        plain = md_to_plain(md)
        self.assertIn("Col1  Col2", plain)
        self.assertIn("Val1  Val2", plain)

    def test_utf16_surrogate_truncation(self):
        emoji_str = "Hello 😀😁😂 Hello"
        # Truncate inside emoji boundary should not crash or produce invalid characters
        res = truncate_text(emoji_str, 8)
        self.assertTrue(len(res) <= 8)
        self.assertTrue(res.encode("utf-8").decode("utf-8") == res)

    def test_split_for_qq(self):
        long_text = "\n".join([f"Line {i}: Sample sentence text" for i in range(100)])
        chunks = split_for_qq(long_text, max_length=200)
        self.assertTrue(len(chunks) > 1)
        for c in chunks:
            self.assertTrue(len(c) <= 200)
            self.assertTrue(c.encode("utf-8").decode("utf-8") == c)


if __name__ == "__main__":
    unittest.main()
