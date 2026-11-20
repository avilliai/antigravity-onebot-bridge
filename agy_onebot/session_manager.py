# -*- coding: utf-8 -*-
"""Session and Conversation State Manager.

Maintains multi-user and multi-group session contexts, sliding history windows,
per-session persona mapping, message deduplication, and concurrency gates.
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional


@dataclass
class ConversationTurn:
    """A single turn in session history."""
    role: str  # "user" or "assistant"
    sender_name: str
    content: str
    timestamp: float = field(default_factory=time.time)


class SessionState:
    """State of an individual conversation session (private or group)."""

    def __init__(self, session_id: str, max_turns: int = 15):
        self.session_id: str = session_id
        self.max_turns: int = max_turns
        self.history: Deque[ConversationTurn] = deque(maxlen=max_turns)
        self.active_role: Optional[str] = None
        self.last_activity: float = time.time()
        self.lock: asyncio.Lock = asyncio.Lock()

    def add_turn(self, role: str, sender_name: str, content: str) -> None:
        self.history.append(ConversationTurn(role=role, sender_name=sender_name, content=content))
        self.last_activity = time.time()

    def clear(self) -> None:
        self.history.clear()
        self.last_activity = time.time()

    def get_history_summary(self) -> str:
        """Render recent history as contextual dialogue for the prompt."""
        if not self.history:
            return ""
        lines: List[str] = []
        for turn in self.history:
            lines.append(f"{turn.sender_name}: {turn.content}")
        return "\n".join(lines)


class SessionManager:
    """Manages all active sessions, deduplication, and persistence."""

    def __init__(self, max_turns_per_session: int = 15, deduplication_cache_size: int = 1000):
        self.max_turns: int = max_turns_per_session
        self.dedup_size: int = deduplication_cache_size
        self._sessions: Dict[str, SessionState] = {}
        self._seen_messages: Deque[str] = deque(maxlen=deduplication_cache_size)
        self._default_role: str = "default"

    def is_duplicate(self, message_id: str) -> bool:
        """Check if message_id was recently seen and mark as seen."""
        if not message_id:
            return False
        if message_id in self._seen_messages:
            return True
        self._seen_messages.append(message_id)
        return False

    def get_session(self, session_id: str) -> SessionState:
        """Retrieve or create session state."""
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id, max_turns=self.max_turns)
        return self._sessions[session_id]

    def set_session_role(self, session_id: str, role_name: str) -> None:
        """Set the active persona for a specific session."""
        session = self.get_session(session_id)
        session.active_role = role_name.lower().strip()

    def get_session_role(self, session_id: str) -> str:
        """Get the active persona for a session."""
        session = self.get_session(session_id)
        return session.active_role or self._default_role

    def reset_session(self, session_id: str) -> None:
        """Clear memory for a session."""
        if session_id in self._sessions:
            self._sessions[session_id].clear()
