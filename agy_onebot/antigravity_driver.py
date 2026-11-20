# -*- coding: utf-8 -*-
"""Antigravity Agent Driver Interface.

Provides unified execution bridges for Google Antigravity:
1. Native Antigravity Python SDK (`google.antigravity.Agent`).
2. Antigravity CLI subprocess (`agy` CLI, supporting non-interactive -p / --print).
3. Direct API fallback (Gemini / Generative Language API compatible).
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
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
        mode: str = "auto",  # "cli", "sdk", "api", "auto"
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
        self._active_sessions = set()

        if mode == "auto":
            if shutil.which(cli_command):
                self.mode = "cli"
            elif HAS_AGY_SDK:
                self.mode = "sdk"
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
        conversation_id: Optional[str] = None,
    ) -> str:
        """Execute chat turn and return the agent's textual response."""
        if self.mode == "cli":
            return await self._chat_via_cli(prompt, system_instructions, conversation_id)
        elif self.mode == "sdk" and HAS_AGY_SDK:
            return await self._chat_via_sdk(prompt, system_instructions, history)
        else:
            return await self._chat_via_api(prompt, system_instructions, history, image_bytes, image_mime)

    async def _chat_via_cli(
        self,
        prompt: str,
        system_instructions: Optional[str],
        conversation_id: Optional[str] = None,
    ) -> str:
        """Invoke Antigravity CLI (agy.exe) non-interactively via subprocess.

        Maintains multi-turn context using --continue for active sessions.
        """
        full_prompt = prompt
        if system_instructions:
            full_prompt = f"[System Instructions: {system_instructions}]\n\n{prompt}"

        is_subsequent = bool(conversation_id and conversation_id in self._active_sessions)
        work_dir = str(Path(__file__).resolve().parent.parent)

        async def _run_command(use_continue: bool, use_new_project: bool = False) -> tuple[int, str, str]:
            cmd = [
                self.cli_command,
                "-p", full_prompt,
                "--dangerously-skip-permissions",
                "--output-format", "text"
            ]
            if self.model_name:
                cmd.extend(["--model", self.model_name])
            if use_continue:
                cmd.append("--continue")
            elif use_new_project:
                cmd.append("--new-project")

            logger.info(f"Executing agy CLI in {work_dir}: {' '.join(cmd[:6])}...")
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            out_s = stdout.decode("utf-8", errors="replace").strip()
            err_s = stderr.decode("utf-8", errors="replace").strip()
            return proc.returncode, out_s, err_s

        try:
            # First attempt: use --continue if already active, retry on transient network EOF
            retcode, out_str, err_str = await _run_command(use_continue=is_subsequent)

            # Retry on transient EOF / network hiccup
            if retcode != 0 and ("EOF" in err_str or "connection" in err_str.lower() or "context deadline" in err_str.lower()):
                logger.info(f"Transient network glitch ({err_str}), retrying agy turn in 1.5s...")
                await asyncio.sleep(1.5)
                retcode, out_str, err_str = await _run_command(use_continue=is_subsequent)

            # If failed on subsequent turn, retry with fresh session
            if retcode != 0 and is_subsequent:
                logger.warning(f"CLI with --continue returned {retcode}: {err_str}. Retrying with fresh session...")
                retcode, out_str, err_str = await _run_command(use_continue=False, use_new_project=True)

            if retcode == 0 and out_str:
                if conversation_id:
                    self._active_sessions.add(conversation_id)
                return out_str
            else:
                logger.warning(f"CLI returned code {retcode}: {err_str}")
                if out_str:
                    return out_str
                # Fallback to direct API if API key configured, otherwise return friendly role response
                if self.api_key:
                    logger.info("Falling back to API mode...")
                    return await self._chat_via_api(prompt, system_instructions, None)
                return "唔…信号好像刚刚卡了一下，你再说一遍试试？"

        except Exception as e:
            logger.error(f"CLI execution failed: {e}.")
            if self.api_key:
                return await self._chat_via_api(prompt, system_instructions, None)
            return "唔…网络好像晃了一下，刚才那句话没听清呢~"

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
            logger.error(f"SDK execution failed: {e}. Falling back to API...")
            return await self._chat_via_api(prompt, system_instructions, history)

    async def _chat_via_api(
        self,
        prompt: str,
        system_instructions: Optional[str],
        history: Optional[List[Dict[str, str]]],
        image_bytes: Optional[bytes] = None,
        image_mime: Optional[str] = None,
    ) -> str:
        """Direct API fallback (Gemini / Generative Language REST API)."""
        if not self.api_key and not self.api_base_url:
            return (
                f"【Antigravity 角色回应】已收到您的消息：\"{prompt[:60]}\"。\n"
                f"（提示：检测到当前 agy 会话尚未登录或未配置 API Key，请先运行 agy 登录或在 config.yaml 中配置 api_key。）"
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
