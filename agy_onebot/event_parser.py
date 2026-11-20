# -*- coding: utf-8 -*-
"""OneBot v11 & Milky Protocol Event Parser.

Deserializes WebSocket events and normalizes message segments (Text, At, Image,
Reply, Forward, Record, Face) into structured Python objects.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from .forward_helper import extract_forward_ids, forward_id_from_data


@dataclass
class MessageSegment:
    """A single normalized message segment."""
    type: str
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MessageSegment":
        return cls(type=d.get("type", "text"), data=d.get("data") or {})


@dataclass
class InboundMessage:
    """Normalized inbound message from QQ/OneBot v11/Milky."""
    post_type: str
    message_type: str  # "private" or "group"
    sub_type: str
    message_id: str
    user_id: str
    group_id: Optional[str]
    time: int
    raw_message: str
    sender_nickname: str
    sender_card: Optional[str]
    sender_role: Optional[str]

    # Parsed components
    segments: List[MessageSegment] = field(default_factory=list)
    plain_text: str = ""
    is_at_bot: bool = False
    at_users: List[str] = field(default_factory=list)
    image_urls: List[str] = field(default_factory=list)
    forward_ids: List[str] = field(default_factory=list)
    reply_message_id: Optional[str] = None
    voice_url: Optional[str] = None

    @property
    def sender_display_name(self) -> str:
        return self.sender_card or self.sender_nickname or self.user_id

    @property
    def is_group(self) -> bool:
        return self.message_type == "group"

    @property
    def session_id(self) -> str:
        if self.is_group:
            return f"group_{self.group_id}"
        return f"private_{self.user_id}"


def parse_onebot_event(raw_event: Dict[str, Any], bot_qq: Optional[str] = None) -> Optional[InboundMessage]:
    """Parse raw JSON event dictionary from OneBot v11 or Milky into an InboundMessage."""
    if not isinstance(raw_event, dict):
        return None

    post_type = raw_event.get("post_type", "")
    if post_type != "message":
        # Meta event, notice or request
        return None

    message_type = raw_event.get("message_type", "private")
    sub_type = raw_event.get("sub_type", "normal")
    msg_id = str(raw_event.get("message_id", raw_event.get("id", "")))
    user_id = str(raw_event.get("user_id", ""))
    group_id = str(raw_event.get("group_id", "")) if "group_id" in raw_event else None
    time_ts = int(raw_event.get("time", 0))
    raw_msg = str(raw_event.get("raw_message", ""))

    sender = raw_event.get("sender") or {}
    nickname = sender.get("nickname", "")
    card = sender.get("card", "")
    role = sender.get("role", "member")

    raw_message_field = raw_event.get("message")
    segments: List[MessageSegment] = []

    if isinstance(raw_message_field, list):
        for item in raw_message_field:
            if isinstance(item, dict):
                segments.append(MessageSegment.from_dict(item))
            elif isinstance(item, str):
                segments.append(MessageSegment(type="text", data={"text": item}))
    elif isinstance(raw_message_field, str):
        segments.append(MessageSegment(type="text", data={"text": raw_message_field}))

    # Extract parsed fields
    text_parts: List[str] = []
    is_at_bot = False
    at_users: List[str] = []
    images: List[str] = []
    reply_id: Optional[str] = None
    voice: Optional[str] = None

    bot_qq_str = str(bot_qq).strip() if bot_qq else ""

    for seg in segments:
        stype = seg.type
        data = seg.data

        if stype == "text":
            text_parts.append(str(data.get("text", "")))
        elif stype == "at":
            target = str(data.get("qq", "")).strip()
            at_users.append(target)
            if bot_qq_str and (target == bot_qq_str or target.lower() == "all"):
                is_at_bot = True
        elif stype == "image":
            url = data.get("url") or data.get("file") or ""
            if url:
                images.append(str(url))
        elif stype == "reply":
            reply_id = str(data.get("id", ""))
        elif stype == "record":
            voice = str(data.get("url") or data.get("file") or "")

    # Forward IDs
    raw_seg_dicts = [s.__dict__ for s in segments]
    forward_ids = extract_forward_ids(raw_seg_dicts)

    plain_text = "".join(text_parts).strip()

    return InboundMessage(
        post_type=post_type,
        message_type=message_type,
        sub_type=sub_type,
        message_id=msg_id,
        user_id=user_id,
        group_id=group_id,
        time=time_ts,
        raw_message=raw_msg,
        sender_nickname=nickname,
        sender_card=card,
        sender_role=role,
        segments=segments,
        plain_text=plain_text,
        is_at_bot=is_at_bot,
        at_users=at_users,
        image_urls=images,
        forward_ids=forward_ids,
        reply_message_id=reply_id,
        voice_url=voice,
    )
