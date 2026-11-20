# -*- coding: utf-8 -*-
"""Milky Protocol (Milky 1.3) Handler for Antigravity-OneBot Bridge.

Provides full bi-directional support for Milky protocol endpoints:
- Inbound event parsing (event_type: "message_receive", "group_message_recall", etc.)
- Segment conversion (OneBot v11 <-> Milky protocol)
  - mention <-> at
  - mention_all <-> at all
  - image / temp_url / uri <-> image url
  - reply message_seq <-> reply id
- Outbound API dispatching for Milky HTTP/WS APIs (send_group_message, send_private_message, etc.)
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from .event_parser import InboundMessage, MessageSegment

import re

logger = logging.getLogger("agy_onebot.milky")


def is_milky_event(raw: Dict[str, Any]) -> bool:
    """Check if the payload is a Milky protocol event."""
    if not isinstance(raw, dict):
        return False
    return "event_type" in raw or "message_scene" in raw.get("data", {})


def parse_milky_event(raw_event: Dict[str, Any], bot_qq: Optional[str] = None) -> Optional[InboundMessage]:
    """Parse a Milky protocol event dictionary into a normalized InboundMessage."""
    if not isinstance(raw_event, dict):
        return None

    event_type = raw_event.get("event_type", "")
    if event_type != "message_receive":
        return None

    data = raw_event.get("data") or {}
    event_time = int(raw_event.get("time", 0))

    scene = data.get("message_scene", "group" if "group_id" in data else "friend")
    is_group = (scene == "group")
    peer_id = str(data.get("peer_id", data.get("group_id", data.get("sender_id", ""))))
    sender_id = str(data.get("sender_id", ""))
    message_seq = str(data.get("message_seq", data.get("message_id", "")))

    sender_info = data.get("group_member") or data.get("friend") or data.get("sender", {})
    nickname = sender_info.get("nickname", "")
    card = sender_info.get("card", "")
    role = sender_info.get("role", "member")

    raw_segments = data.get("segments") or []
    segments: List[MessageSegment] = []
    text_parts: List[str] = []
    is_at_bot = False
    at_users: List[str] = []
    image_urls: List[str] = []
    reply_id: Optional[str] = None
    voice_url: Optional[str] = None

    bot_qq_str = str(bot_qq).strip() if bot_qq else ""

    for seg in raw_segments:
        if not isinstance(seg, dict):
            continue
        stype = seg.get("type", "text")
        sdata = seg.get("data") or {}

        if stype == "text":
            txt = str(sdata.get("text", ""))
            text_parts.append(txt)
            segments.append(MessageSegment(type="text", data={"text": txt}))
        elif stype == "mention":
            uid = str(sdata.get("user_id", ""))
            at_users.append(uid)
            if bot_qq_str and uid == bot_qq_str:
                is_at_bot = True
            segments.append(MessageSegment(type="at", data={"qq": uid}))
        elif stype == "mention_all":
            at_users.append("all")
            is_at_bot = True
            segments.append(MessageSegment(type="at", data={"qq": "all"}))
        elif stype in ("image", "mface"):
            uri = sdata.get("temp_url") or sdata.get("uri") or sdata.get("url") or ""
            if uri:
                image_urls.append(uri)
            segments.append(MessageSegment(type="image", data={"url": uri, "file": uri}))
        elif stype == "record":
            uri = sdata.get("temp_url") or sdata.get("uri") or sdata.get("url") or ""
            if uri:
                voice_url = uri
            segments.append(MessageSegment(type="record", data={"url": uri, "file": uri}))
        elif stype == "reply":
            seq = str(sdata.get("message_seq", ""))
            if seq:
                reply_id = seq
            segments.append(MessageSegment(type="reply", data={"id": seq}))
        elif stype == "face":
            face_id = str(sdata.get("face_id", ""))
            segments.append(MessageSegment(type="face", data={"id": face_id}))
        else:
            segments.append(MessageSegment(type=stype, data=sdata))

    plain_text = "".join(text_parts).strip()

    return InboundMessage(
        post_type="message",
        message_type="group" if is_group else "private",
        sub_type="normal",
        message_id=message_seq,
        user_id=sender_id,
        group_id=peer_id if is_group else None,
        time=event_time,
        raw_message=plain_text,
        sender_nickname=nickname,
        sender_card=card,
        sender_role=role,
        segments=segments,
        plain_text=plain_text,
        is_at_bot=is_at_bot,
        at_users=at_users,
        image_urls=image_urls,
        forward_ids=[],
        reply_message_id=reply_id,
        voice_url=voice_url,
    )


def text_to_milky_segments(text: str) -> List[Dict[str, Any]]:
    """Convert text with optional embedded CQ codes into Milky segments."""
    if not text:
        return []

    cq_pattern = re.compile(r"\[CQ:([a-zA-Z_]+)(?:,([^\]]*))?\]")
    segments: List[Dict[str, Any]] = []
    last_idx = 0

    for match in cq_pattern.finditer(text):
        start, end = match.span()
        if start > last_idx:
            prefix = text[last_idx:start]
            if prefix:
                segments.append({"type": "text", "data": {"text": prefix}})

        cq_type = match.group(1).lower()
        param_str = match.group(2) or ""
        params: Dict[str, str] = {}
        for part in param_str.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k.strip()] = v.strip()

        if cq_type == "at":
            qq = params.get("qq", "")
            if qq in ("all", "0"):
                segments.append({"type": "mention_all", "data": {}})
            elif qq.isdigit():
                segments.append({"type": "mention", "data": {"user_id": int(qq)}})
        elif cq_type == "record":
            file_path = params.get("file") or params.get("url", "")
            if file_path:
                if not (file_path.startswith("file://") or file_path.startswith("http://") or file_path.startswith("https://") or file_path.startswith("data:")):
                    norm_path = file_path.replace("\\", "/")
                    if not norm_path.startswith("/"):
                        norm_path = "/" + norm_path
                    file_path = f"file://{norm_path}"
                segments.append({"type": "record", "data": {"uri": file_path}})
        elif cq_type == "image":
            file_path = params.get("file") or params.get("url", "")
            if file_path:
                if not (file_path.startswith("file://") or file_path.startswith("http://") or file_path.startswith("https://") or file_path.startswith("data:")):
                    norm_path = file_path.replace("\\", "/")
                    if not norm_path.startswith("/"):
                        norm_path = "/" + norm_path
                    file_path = f"file://{norm_path}"
                segments.append({"type": "image", "data": {"uri": file_path}})
        elif cq_type == "face":
            face_id = params.get("id", "0")
            segments.append({"type": "face", "data": {"face_id": str(face_id)}})
        else:
            segments.append({"type": cq_type, "data": params})

        last_idx = end

    if last_idx < len(text):
        remaining = text[last_idx:]
        if remaining:
            segments.append({"type": "text", "data": {"text": remaining}})

    return segments if segments else [{"type": "text", "data": {"text": text}}]


def onebot_to_milky_api(action: str, params: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Map OneBot v11 action and parameters to Milky protocol API endpoint and body."""
    p = dict(params)

    if action in ("send_group_msg", "send_group_message"):
        endpoint = "send_group_message"
        gid = p.get("group_id")
        msg = p.get("message")
        if isinstance(msg, str):
            segments = text_to_milky_segments(msg)
        elif isinstance(msg, list):
            segments = []
            for seg in msg:
                if isinstance(seg, dict):
                    st = seg.get("type", "text")
                    sd = seg.get("data", {})
                    if st == "text":
                        segments.append({"type": "text", "data": {"text": sd.get("text", "")}})
                    elif st == "at":
                        qq = str(sd.get("qq", ""))
                        if qq in ("all", "0"):
                            segments.append({"type": "mention_all", "data": {}})
                        else:
                            segments.append({"type": "mention", "data": {"user_id": int(qq)}})
                    elif st == "image":
                        segments.append({"type": "image", "data": {"uri": sd.get("file") or sd.get("url", "")}})
                    elif st == "record":
                        segments.append({"type": "record", "data": {"uri": sd.get("file") or sd.get("url", "")}})
                    else:
                        segments.append({"type": st, "data": sd})
                else:
                    segments.append({"type": "text", "data": {"text": str(seg)}})
        else:
            segments = text_to_milky_segments(str(msg or ""))
        return endpoint, {"group_id": int(gid), "message": segments}

    elif action in ("send_private_msg", "send_private_message"):
        endpoint = "send_private_message"
        uid = p.get("user_id")
        msg = p.get("message")
        if isinstance(msg, str):
            segments = text_to_milky_segments(msg)
        else:
            segments = text_to_milky_segments(str(msg or ""))
        return endpoint, {"user_id": int(uid), "message": segments}

    elif action in ("delete_msg", "recall_group_message", "recall_private_message"):
        if "group_id" in p:
            return "recall_group_message", {
                "group_id": int(p["group_id"]),
                "message_seq": int(p.get("message_seq", p.get("message_id", 0)))
            }
        else:
            return "recall_private_message", {
                "user_id": int(p.get("user_id", 0)),
                "message_seq": int(p.get("message_seq", p.get("message_id", 0)))
            }

    return action, p
