# -*- coding: utf-8 -*-
"""Forward Message Helper for OneBot v11 / Milky.

Extracts forward IDs, traverses nested forward message trees, and formats
forward chat history records into clean, compact text for Antigravity agents.
"""

import re
from typing import Any, Dict, List, Optional
from .md_to_plain import truncate_text


def sanitize_forward_id(value: Any) -> str:
    """Sanitize and validate OneBot forward / resource ID."""
    s = str(value or "").strip()
    if not s or len(s) > 256:
        return ""
    # Safe character set: alphanumerics, colons, dots, dashes, slashes, plus, equals, @
    if not re.match(r"^[\w:.\-/=+@]+$", s):
        return ""
    return s


def forward_id_from_data(data: Any) -> str:
    """Extract valid forward ID from a segment's data dict."""
    if not isinstance(data, dict):
        return ""
    cand = data.get("id") or data.get("res_id") or data.get("file_id") or data.get("forward_id") or ""
    return sanitize_forward_id(cand)


def extract_forward_ids(segments: List[Dict[str, Any]]) -> List[str]:
    """Extract all forward IDs found in a list of message segments."""
    if not isinstance(segments, list):
        return []
    ids: List[str] = []
    for seg in segments:
        if isinstance(seg, dict) and seg.get("type") == "forward":
            fid = forward_id_from_data(seg.get("data"))
            if fid and fid not in ids:
                ids.append(fid)
    return ids


def _segment_to_text(seg: Any) -> str:
    """Render a single message segment into human-readable placeholder text."""
    if isinstance(seg, str):
        return seg
    if not isinstance(seg, dict):
        return ""
    stype = seg.get("type")
    data = seg.get("data") or {}

    if stype == "text":
        return str(data.get("text", ""))
    elif stype == "at":
        qq = data.get("qq")
        return "@全体成员" if str(qq).lower() == "all" else f"@{qq}"
    elif stype == "face":
        return f"[表情{data.get('id', '')}]"
    elif stype == "image":
        return "[图片]"
    elif stype == "record":
        return "[语音]"
    elif stype == "video":
        return "[视频]"
    elif stype == "file":
        return f"[文件: {data.get('name', '')}]"
    elif stype == "reply":
        return "[回复]"
    elif stype == "forward":
        return "[合并转发]"
    elif stype == "json":
        return "[小程序/卡片消息]"
    return f"[{stype or '消息'}]"


def _sanitize_cq_string(text: str) -> str:
    """Strip raw CQ codes into safe media placeholders."""
    return re.sub(r"\[CQ:[^\]]*\]", "[媒体]", text)


def node_to_text(node: Dict[str, Any]) -> str:
    """Extract plain text message content from a OneBot forward node."""
    if not isinstance(node, dict):
        return ""
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    top_content = node.get("message") or node.get("content") or node.get("text")
    data_content = data.get("message") or data.get("content") or data.get("text")
    content = top_content or data_content

    if isinstance(content, str):
        return _sanitize_cq_string(content)
    if isinstance(content, list):
        return _sanitize_cq_string("".join(_segment_to_text(s) for s in content).strip())
    if isinstance(content, dict):
        if content.get("type"):
            return _sanitize_cq_string(_segment_to_text(content).strip())
        if "text" in content:
            return _sanitize_cq_string(str(content["text"]))
    return ""


def format_forward_response(response_data: Any, max_nodes: int = 50) -> str:
    """Format the result of get_forward_msg into a readable chat transcript for the agent."""
    if not response_data:
        return "[无转发内容]"

    nodes: List[Dict[str, Any]] = []
    if isinstance(response_data, list):
        nodes = response_data
    elif isinstance(response_data, dict):
        raw = response_data.get("messages") or response_data.get("nodes") or response_data.get("data")
        if isinstance(raw, list):
            nodes = raw
        elif isinstance(raw, dict) and "messages" in raw:
            nodes = raw["messages"]

    if not nodes:
        return "[转发消息内容为空]"

    lines: List[str] = ["--- 合并转发聊天记录 ---"]
    count = 0
    for node in nodes[:max_nodes]:
        if not isinstance(node, dict):
            continue
        count += 1
        data = node.get("data") if isinstance(node.get("data"), dict) else {}
        sender = node.get("sender") or {}
        name = ""
        if isinstance(sender, dict):
            name = sender.get("nickname") or sender.get("card") or str(sender.get("user_id", ""))
        if not name:
            name = data.get("name") or data.get("nickname") or str(data.get("uin") or data.get("user_id", ""))
        name = truncate_text(name or "用户", 30)

        content = node_to_text(node)
        lines.append(f"{name}: {content}")

    if len(nodes) > max_nodes:
        lines.append(f"... (共 {len(nodes)} 条记录，已截取前 {max_nodes} 条)")
    lines.append("-------------------------")
    return "\n".join(lines)
