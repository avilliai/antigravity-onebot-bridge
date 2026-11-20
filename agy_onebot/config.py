# -*- coding: utf-8 -*-
"""Configuration Loader for Antigravity-OneBot & Milky Bridge."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


@dataclass
class OneBotConfig:
    protocol: str = "auto"  # "auto", "onebot", "milky"
    mode: str = "forward"  # "forward" or "reverse"
    ws_url: str = "ws://127.0.0.1:3001"
    event_ws_url: str = ""  # Specific event ws URL (e.g. ws://127.0.0.1:3001/event for Milky)
    api_url: str = "http://127.0.0.1:3000"  # HTTP API root (e.g. http://127.0.0.1:3001/api for Milky)
    reverse_host: str = "0.0.0.0"
    reverse_port: int = 8080
    access_token: str = ""
    bot_qq: str = ""


@dataclass
class AntigravityConfig:
    mode: str = "auto"  # "sdk", "cli", "api", "auto"
    cli_command: str = "agy"
    model_name: str = "gemini-2.5-pro"
    api_key: str = ""
    api_base_url: str = ""
    timeout: float = 120.0


@dataclass
class RoleplayConfig:
    default_role: str = "default"
    roles_dir: str = ""
    enable_group_persona: bool = True


@dataclass
class TriggerConfig:
    reply_private: bool = True
    require_at_in_group: bool = True
    command_prefix: str = "/"
    group_whitelist: List[str] = field(default_factory=list)
    group_blacklist: List[str] = field(default_factory=list)


@dataclass
class BridgeConfig:
    onebot: OneBotConfig = field(default_factory=OneBotConfig)
    antigravity: AntigravityConfig = field(default_factory=AntigravityConfig)
    roleplay: RoleplayConfig = field(default_factory=RoleplayConfig)
    trigger: TriggerConfig = field(default_factory=TriggerConfig)
    max_chunk_length: int = 4000
    max_history_turns: int = 15

    @classmethod
    def load(cls, file_path: Optional[str] = None) -> "BridgeConfig":
        """Load configuration from a YAML or JSON file."""
        if not file_path:
            cand = Path("config.yaml")
            if not cand.exists():
                cand = Path("config.example.yaml")
            if not cand.exists():
                return cls()
            file_path = str(cand)

        path = Path(file_path)
        if not path.exists():
            return cls()

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        ob_data = data.get("onebot", {}) or data.get("milky", {})
        ag_data = data.get("antigravity", {})
        rp_data = data.get("roleplay", {})
        tr_data = data.get("trigger", {})

        return cls(
            onebot=OneBotConfig(
                protocol=ob_data.get("protocol", "auto"),
                mode=ob_data.get("mode", "forward"),
                ws_url=ob_data.get("ws_url", "ws://127.0.0.1:3001"),
                event_ws_url=ob_data.get("event_ws_url", ""),
                api_url=ob_data.get("api_url", "http://127.0.0.1:3000"),
                reverse_host=ob_data.get("reverse_host", "0.0.0.0"),
                reverse_port=int(ob_data.get("reverse_port", 8080)),
                access_token=ob_data.get("access_token", ""),
                bot_qq=str(ob_data.get("bot_qq", "")),
            ),
            antigravity=AntigravityConfig(
                mode=ag_data.get("mode", "auto"),
                cli_command=ag_data.get("cli_command", "agy"),
                model_name=ag_data.get("model_name", "gemini-2.5-pro"),
                api_key=ag_data.get("api_key", ""),
                api_base_url=ag_data.get("api_base_url", ""),
                timeout=float(ag_data.get("timeout", 120.0)),
            ),
            roleplay=RoleplayConfig(
                default_role=rp_data.get("default_role", "default"),
                roles_dir=rp_data.get("roles_dir", ""),
                enable_group_persona=bool(rp_data.get("enable_group_persona", True)),
            ),
            trigger=TriggerConfig(
                reply_private=bool(tr_data.get("reply_private", True)),
                require_at_in_group=bool(tr_data.get("require_at_in_group", True)),
                command_prefix=tr_data.get("command_prefix", "/"),
                group_whitelist=[str(x) for x in tr_data.get("group_whitelist", [])],
                group_blacklist=[str(x) for x in tr_data.get("group_blacklist", [])],
            ),
            max_chunk_length=int(data.get("max_chunk_length", 4000)),
            max_history_turns=int(data.get("max_history_turns", 15)),
        )
