# -*- coding: utf-8 -*-
"""Markdown to QQ Plain Text Converter & UTF-16 Surrogate Safe Splitter.

Ensures messages sent to OneBot v11 / Milky:
1. Strip code blocks / fences and formatting that looks messy on QQ.
2. Preserve hyperlinks, list items, and emojis cleanly.
3. Prevent UTF-16 surrogate-pair truncation errors (mojibake).
4. Split oversized messages into safe chunks (default <= 4000 characters).
"""

import re
from typing import List, Optional


def md_to_plain(md: Optional[str]) -> str:
    """Convert agent Markdown response to clean, legible QQ message text."""
    if not md:
        return ""

    s = str(md)

    # 1. Strip code fences: ```lang\ncode\n``` -> code
    s = re.sub(
        r"```[a-zA-Z0-9_\+\-]*\n?([\s\S]*?)```",
        lambda m: m.group(1).rstrip("\n"),
        s,
    )

    # 2. Inline code: `code` -> code
    s = re.sub(r"`([^`\n]+)`", r"\1", s)

    # 3. Images: ![alt](url) -> [图片: alt] or [图片: url]
    s = re.sub(
        r"!\[([^\]\n]{0,500})\]\(([^)\s]{1,2000})\)",
        lambda m: f"[图片: {m.group(1)}]" if m.group(1) else f"[图片: {m.group(2)}]",
        s,
    )

    # 4. Hyperlinks: [title](url) -> title (url)
    s = re.sub(r"\[([^\]\n]{1,500})\]\(([^)\s]{1,2000})\)", r"\1 (\2)", s)

    # 5. Bold & italic formatting
    s = re.sub(r"\*\*\*([^*\n]+)\*\*\*", r"\1", s)
    s = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", s)
    s = re.sub(r"\*(?!\s)([^*\n]*?[^\s*])\*", r"\1", s)
    s = re.sub(r"~~([^~\n]+)~~", r"\1", s)
    s = re.sub(r"__([^_\n]+)__", r"\1", s)

    # 6. Headers: # Title -> Title
    s = re.sub(r"^#{1,6}\s+", "", s, flags=re.MULTILINE)

    # 7. Blockquotes: > Quote -> Quote
    s = re.sub(r"^>\s?", "", s, flags=re.MULTILINE)

    # 8. Unordered / ordered lists: convert to bullet points
    s = re.sub(r"^\s*[-*+]\s+", "• ", s, flags=re.MULTILINE)
    s = re.sub(r"^\s*(\d+)\.\s+", r"\1. ", s, flags=re.MULTILINE)

    # 9. Clean markdown tables: preserve cell content per line
    table_lines = []
    for line in s.split("\n"):
        if re.match(r"^\s*\|?[\s:|\-]+\|?\s*$", line):
            # Header separator line like |---|---|
            continue
        if "|" in line:
            # Strip outer pipes and normalize cells
            cleaned = re.sub(r"^\s*\|\s*", "", line)
            cleaned = re.sub(r"\s*\|\s*$", "", cleaned)
            cells = [c.strip() for c in cleaned.split("|")]
            table_lines.append("  ".join(cells))
        else:
            table_lines.append(line)
    s = "\n".join(table_lines)

    # 10. Collapse multiple blank lines
    s = re.sub(r"\n{3,}", "\n\n", s)

    return s.strip()


def truncate_text(value: Optional[str], max_chars: int) -> str:
    """Truncate text to max_chars without breaking UTF-16 surrogate pairs."""
    if not value or max_chars <= 0:
        return ""
    s = str(value)
    if len(s) <= max_chars:
        return s

    cut = max_chars
    # If cutting in the middle of a high surrogate (0xD800 - 0xDBFF)
    code = ord(s[cut - 1])
    if 0xD800 <= code <= 0xDBFF:
        cut -= 1

    if cut <= 0:
        first = ord(s[0])
        if 0xD800 <= first <= 0xDBFF and len(s) > 1:
            second = ord(s[1])
            cut = 2 if (0xDC00 <= second <= 0xDFFF) else 1
        else:
            cut = 1

    return s[:cut]


def truncate_text_tail(value: Optional[str], max_chars: int) -> str:
    """Keep the last max_chars characters without breaking UTF-16 surrogate pairs."""
    if not value or max_chars <= 0:
        return ""
    s = str(value)
    if len(s) <= max_chars:
        return s

    start = len(s) - max_chars
    code = ord(s[start])
    # If the start character falls on a low surrogate (0xDC00 - 0xDFFF)
    if 0xDC00 <= code <= 0xDFFF:
        before = ord(s[start - 1]) if start > 0 else 0
        if 0xD800 <= before <= 0xDBFF:
            start -= 1
        else:
            start += 1

    return s[start:]


def split_for_qq(text: Optional[str], max_length: int = 4000) -> List[str]:
    """Split long text into safe chunks for QQ messaging (<= max_length chars)."""
    if not text:
        return []
    safe_max = max(100, int(max_length))
    parts: List[str] = []
    rest = str(text)

    while len(rest) > safe_max:
        # Prefer breaking at a newline within the last safe_max range
        cut = rest.rfind("\n", 0, safe_max)
        eat = 0
        if cut <= 0:
            cut = safe_max
        else:
            eat = 1

        # Prevent splitting surrogate pairs
        code = ord(rest[cut - 1])
        if 0xD800 <= code <= 0xDBFF:
            cut -= 1

        if cut <= 0:
            first = ord(rest[0])
            if 0xD800 <= first <= 0xDBFF and len(rest) > 1:
                second = ord(rest[1])
                cut = 2 if (0xDC00 <= second <= 0xDFFF) else 1
            else:
                cut = 1
            eat = 0

        chunk = rest[:cut + eat]
        if chunk:
            parts.append(chunk)
        rest = rest[cut + eat:]

    if rest:
        parts.append(rest)
    return parts
