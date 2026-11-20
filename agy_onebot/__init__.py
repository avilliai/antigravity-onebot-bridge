# -*- coding: utf-8 -*-
"""Antigravity OneBot & Milky Bridge Package.

A clean, native bridge between Google Antigravity and OneBot v11 / Milky protocols.
"""

from .config import BridgeConfig
from .gateway import BridgeGateway
from .event_parser import parse_onebot_event, InboundMessage
from .md_to_plain import md_to_plain, split_for_qq
from .roleplay_engine import RoleplayEngine

__all__ = [
    "BridgeConfig",
    "BridgeGateway",
    "InboundMessage",
    "parse_onebot_event",
    "md_to_plain",
    "split_for_qq",
    "RoleplayEngine",
]
