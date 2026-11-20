# -*- coding: utf-8 -*-
"""Antigravity Agent Driver Interface.

Provides unified execution bridges for Google Antigravity:
1. Native Antigravity Python SDK (`google.antigravity.Agent`).
2. Antigravity CLI subprocess (`agy`).
3. Standard fallback LLM client (Gemini / OpenAI API compatible) for development & testing.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
from typing import AsyncGenerator, Dict, List, Optional

logger = logging.getLogger("agy_onebot.driver")

# Check if official google.antigravity SDK is installed
try:
    from google.antigravity import Agent as AgySdkAgent, LocalAgentConfig, CapabilitiesConfig
    HAS_AGY_SDK = True
except ImportError:
    HAS_AGY_SDK = False


class AntigravityDriver:
    """Driver connecting bridge requests to Antigravity agents."""

    def __init__(
        self,
        mode: str = "auto",  # "sdk", "cli", "api", "auto"
        cli_command: str = "agy",
        api_base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: float = 120.0,
    ):
        self.cli_command = cli_command
        self.api_base_url = api_base_url
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "") or os.getenv("ANTIGRAVITY_API_KEY", "")
        self.model_name = model_name or "gemini-2.5-pro"
        self.timeout = timeout

        if mode == "auto":
            if HAS_AGY_SDK:
                self.mode = "sdk"
            elif shutil.which(cli_command):
                self.mode = "cli"
            else:
                self.mode = "api"
        else:
            self.mode = mode

        logger.info(f"AntigravityDriver initialized in mode: {self.mode}")

    async def chat(
        self,
        prompt: str,
        system_instructions: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        image_bytes: Optional[bytes] = None,
        image_mime: Optional[str] = None,
    ) -> str:
        """Execute chat turn and return the agent's textual response."""
        if self.mode == "sdk" and HAS_AGY_SDK:
            return await self._chat_via_sdk(prompt, system_instructions, history)
        elif self.mode == "cli":
            return await self._chat_via_cli(prompt, system_instructions)
        else:
            return await self._chat_via_api(prompt, system_instructions, history, image_bytes, image_mime)

    async def _chat_via_sdk(
        self,
        prompt: str,
        system_instructions: Optional[str],
        history: Optional[List[Dict[str, str]]],
    ) -> str:
        """Call Antigravity through Python SDK."""
        try:
            config = LocalAgentConfig(
                system_instructions=system_instructions or "You are an intelligent assistant.",
                capabilities=CapabilitiesConfig(),
            )
            async with AgySdkAgent(config) as agent:
                response = await agent.chat(prompt)
                chunks = []
                async for token in response:
                    chunks.append(token)
                return "".join(chunks).strip()
        except Exception as e:
            logger.error(f"SDK execution failed: {e}. Falling back to CLI/API...")
            return await self._chat_via_cli(prompt, system_instructions)

    async def _chat_via_cli(self, prompt: str, system_instructions: Optional[str]) -> str:
        """Call Antigravity via agy CLI."""
        cmd = [self.cli_command, "--print", prompt]
        if system_instructions:
            # Pass instructions via temporary environment or args if supported
            pass

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            out_str = stdout.decode("utf-8", errors="replace").strip()
            if proc.returncode != 0:
                err_str = stderr.decode("utf-8", errors="replace").strip()
                logger.warning(f"CLI returned non-zero ({proc.returncode}): {err_str}")
            return out_str
        except Exception as e:
            logger.error(f"CLI execution failed: {e}")
            return f"[Antigravity 执行错误: {e}]"

    async def _chat_via_api(
        self,
        prompt: str,
        system_instructions: Optional[str],
        history: Optional[List[Dict[str, str]]],
        image_bytes: Optional[bytes] = None,
        image_mime: Optional[str] = None,
    ) -> str:
        """Direct API fallback (Gemini / OpenAI compatible) using standard urllib or aiohttp."""
        # Clean fallback mock when keys are not configured yet, ensuring safe out-of-the-box testability
        if not self.api_key and not self.api_base_url:
            return (
                f"【Antigravity 角色回应】已收到您的消息：\"{prompt[:50]}\"。\n"
                f"（提示：检测到当前尚未配置 API Key 或启动本地 Antigravity 守护进程，这是测试模式自动回执。）"
            )

        import urllib.request
        import urllib.error

        base = self.api_base_url or "https://generativelanguage.googleapis.com/v1beta"
        url = f"{base}/models/{self.model_name}:generateContent?key={self.api_key}"

        contents = []
        if history:
            for item in history:
                role = "user" if item.get("role") == "user" else "model"
                contents.append({"role": role, "parts": [{"text": item.get("content", "")}]})

        current_parts = []
        if image_bytes and image_mime:
            import base64
            b64_data = base64.b64encode(image_bytes).decode("ascii")
            current_parts.append({
                "inline_data": {
                    "mime_type": image_mime,
                    "data": b64_data
                }
            })
        current_parts.append({"text": prompt})
        contents.append({"role": "user", "parts": current_parts})

        payload = {"contents": contents}
        if system_instructions:
            payload["system_instruction"] = {
                "parts": [{"text": system_instructions}]
            }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        def _do_request():
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    res_body = resp.read().decode("utf-8")
                    data = json.loads(res_body)
                    cands = data.get("candidates", [])
                    if cands:
                        parts = cands[0].get("content", {}).get("parts", [])
                        return "".join(p.get("text", "") for p in parts).strip()
                    return ""
            except urllib.error.HTTPError as he:
                err_text = he.read().decode("utf-8", errors="replace")
                logger.error(f"HTTPError {he.code}: {err_text}")
                return f"[API 响应错误: {he.code}]"
            except Exception as ex:
                logger.error(f"Request failed: {ex}")
                return f"[请求失败: {ex}]"

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _do_request)
