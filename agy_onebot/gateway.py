# -*- coding: utf-8 -*-
"""Antigravity-OneBot & Milky Bridge Gateway.

The central bidirectional service coordinating OneBot / Milky WebSocket communication,
session routing, roleplay injection, and Antigravity response dispatching.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
import urllib.request

from .config import BridgeConfig
from .event_parser import InboundMessage, parse_onebot_event
from .forward_helper import format_forward_response
from .md_to_plain import md_to_plain, split_for_qq
from .media_processor import normalize_image_bytes
from .milky_protocol import onebot_to_milky_api
from .roleplay_engine import RoleplayEngine
from .session_manager import SessionManager
from .ws_client import OneBotWebSocketTransport
from .antigravity_driver import AntigravityDriver

logger = logging.getLogger("agy_onebot.gateway")


class BridgeGateway:
    """Main bidirectional gateway connecting Antigravity to OneBot / Milky."""

    def __init__(self, config: Optional[BridgeConfig] = None):
        self.config = config or BridgeConfig.load()
        self.start_time = time.time()

        # Initialize core components
        self.roleplay = RoleplayEngine(
            roles_dir=self.config.roleplay.roles_dir or None
        )
        self.roleplay.default_role = self.config.roleplay.default_role

        self.sessions = SessionManager(
            max_turns_per_session=self.config.max_history_turns
        )
        self.sessions._default_role = self.config.roleplay.default_role

        self.driver = AntigravityDriver(
            mode=self.config.antigravity.mode,
            cli_command=self.config.antigravity.cli_command,
            api_base_url=self.config.antigravity.api_base_url,
            api_key=self.config.antigravity.api_key,
            model_name=self.config.antigravity.model_name,
            timeout=self.config.antigravity.timeout,
        )

        ob_cfg = self.config.onebot
        ws_endpoint = ob_cfg.event_ws_url or ob_cfg.ws_url
        self.transport = OneBotWebSocketTransport(
            mode=ob_cfg.mode,
            url=ws_endpoint,
            api_url=ob_cfg.api_url,
            host=ob_cfg.reverse_host,
            port=ob_cfg.reverse_port,
            access_token=ob_cfg.access_token,
        )
        self.transport.set_event_handler(self._on_event)

    async def start(self) -> None:
        """Start the bridge gateway."""
        proto = self.config.onebot.protocol.upper()
        logger.info(f"Initializing Antigravity Bridge Gateway (Protocol: {proto})...")
        await self.transport.start()

    async def stop(self) -> None:
        """Stop the gateway."""
        logger.info("Stopping gateway...")
        await self.transport.stop()

    async def _on_event(self, raw_event: Dict[str, Any]) -> None:
        """Process incoming raw WebSocket event."""
        inbound = parse_onebot_event(raw_event, bot_qq=self.config.onebot.bot_qq)
        if not inbound:
            return

        # Deduplication
        if self.sessions.is_duplicate(inbound.message_id):
            return

        # Trigger checks
        if not self._should_trigger(inbound):
            return

        session = self.sessions.get_session(inbound.session_id)
        async with session.lock:
            await self._handle_inbound(inbound)

    def _should_trigger(self, msg: InboundMessage) -> bool:
        """Determine if bot should respond based on trigger rules."""
        if msg.is_group:
            gid = str(msg.group_id)
            if self.config.trigger.group_blacklist and gid in self.config.trigger.group_blacklist:
                return False
            if self.config.trigger.group_whitelist and gid not in self.config.trigger.group_whitelist:
                return False

            if self.config.trigger.require_at_in_group and not msg.is_at_bot:
                prefix = self.config.trigger.command_prefix
                if prefix and msg.plain_text.startswith(prefix):
                    return True
                return False
            return True
        else:
            return self.config.trigger.reply_private

    async def _handle_inbound(self, msg: InboundMessage) -> None:
        """Handle inbound message, process built-in commands or forward to Antigravity."""
        text = msg.plain_text.strip()
        prefix = self.config.trigger.command_prefix

        # Built-in fast commands
        if prefix and text.startswith(prefix):
            handled = await self._handle_builtin_command(msg, text[len(prefix):].strip())
            if handled:
                return

        # Build prompt & context
        active_role = self.sessions.get_session_role(msg.session_id)
        context_type = "group" if msg.is_group else "private"
        sys_instructions = self.roleplay.build_system_instructions(active_role, context_type=context_type)

        # Handle forward messages if referenced
        forward_text = ""
        if msg.forward_ids:
            forward_text = await self._fetch_forward_summary(msg.forward_ids[0])

        # Handle image download if present
        img_bytes = None
        img_mime = None
        if msg.image_urls:
            img_bytes, img_mime = await self._download_and_normalize_image(msg.image_urls[0])

        session = self.sessions.get_session(msg.session_id)
        history_summary = session.get_history_summary()

        prompt_parts: List[str] = []
        if history_summary:
            prompt_parts.append(f"【最近对话记录】\n{history_summary}\n")
        if forward_text:
            prompt_parts.append(f"【引用的聊天记录】\n{forward_text}\n")

        prompt_parts.append(f"{msg.sender_display_name}: {text or '[发送了图片/媒体]'}")
        full_prompt = "\n".join(prompt_parts)

        logger.info(f"Dispatching prompt to Antigravity ({msg.session_id}, role: {active_role})...")
        try:
            raw_response = await self.driver.chat(
                prompt=full_prompt,
                system_instructions=sys_instructions,
                image_bytes=img_bytes,
                image_mime=img_mime,
            )
        except Exception as e:
            logger.error(f"Antigravity driver error: {e}")
            raw_response = f"抱歉，处理您的消息时遇到错误：{e}"

        clean_response = md_to_plain(raw_response)
        chunks = split_for_qq(clean_response, max_length=self.config.max_chunk_length)

        session.add_turn("user", msg.sender_display_name, text)
        session.add_turn("assistant", active_role, clean_response)

        for chunk in chunks:
            await self._send_reply(msg, chunk)
            if len(chunks) > 1:
                await asyncio.sleep(0.3)

    async def _handle_builtin_command(self, msg: InboundMessage, cmd_text: str) -> bool:
        """Handle commands like /role, /roles, /reset, /status."""
        parts = cmd_text.split()
        if not parts:
            return False
        cmd = parts[0].lower()

        if cmd in ("reset", "new", "clear"):
            self.sessions.reset_session(msg.session_id)
            await self._send_reply(msg, "已清空当前会话记忆，开启新对话！")
            return True

        if cmd in ("roles", "rolelist"):
            available = self.roleplay.list_roles()
            cur = self.sessions.get_session_role(msg.session_id)
            reply = f"当前生效角色：【{cur}】\n可用角色列表：\n• " + "\n• ".join(available)
            reply += "\n提示：使用 /role <角色名> 进行切换。"
            await self._send_reply(msg, reply)
            return True

        if cmd in ("role", "setrole") and len(parts) > 1:
            target = parts[1].lower()
            if target in self.roleplay.list_roles():
                self.sessions.set_session_role(msg.session_id, target)
                await self._send_reply(msg, f"角色已成功切换为：【{target}】")
            else:
                await self._send_reply(msg, f"未找到角色「{target}」，输入 /roles 查看所有可用角色。")
            return True

        if cmd in ("status", "info"):
            uptime = int(time.time() - self.start_time)
            cur = self.sessions.get_session_role(msg.session_id)
            status_text = (
                f"【Antigravity Bridge 运行状态】\n"
                f"• 运行时间: {uptime // 3600}小时{(uptime % 3600) // 60}分{uptime % 60}秒\n"
                f"• 接入协议: {self.config.onebot.protocol.upper()} ({self.config.onebot.mode})\n"
                f"• Antigravity 驱动: {self.driver.mode} ({self.config.antigravity.model_name})\n"
                f"• 当前会话: {msg.session_id} (角色: {cur})"
            )
            await self._send_reply(msg, status_text)
            return True

        return False

    async def _send_reply(self, original_msg: InboundMessage, text: str) -> None:
        """Send message back to OneBot or Milky endpoint."""
        if not text:
            return

        is_milky = (self.config.onebot.protocol == "milky")

        if original_msg.is_group:
            action = "send_group_msg"
            params = {"group_id": int(original_msg.group_id), "message": text}
        else:
            action = "send_private_msg"
            params = {"user_id": int(original_msg.user_id), "message": text}

        if is_milky:
            action, params = onebot_to_milky_api(action, params)

        try:
            await self.transport.call_action(action, params)
        except Exception as e:
            logger.error(f"Failed to send reply via {action}: {e}")

    async def _fetch_forward_summary(self, forward_id: str) -> str:
        """Call get_forward_msg and format into text."""
        try:
            res = await self.transport.call_action("get_forward_msg", {"id": forward_id})
            data = res.get("data")
            return format_forward_response(data)
        except Exception as e:
            logger.warning(f"Failed to fetch forward message {forward_id}: {e}")
            return ""

    async def _download_and_normalize_image(self, url: str) -> tuple[Optional[bytes], Optional[str]]:
        """Download remote image and normalize for multi-modal model."""
        def _fetch():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Antigravity-Bridge/1.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    return resp.read()
            except Exception as e:
                logger.warning(f"Failed to download image {url}: {e}")
                return None

        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, _fetch)
        if not raw:
            return None, None
        return normalize_image_bytes(raw)
