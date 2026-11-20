# -*- coding: utf-8 -*-
"""Model Context Protocol (MCP) Server for OneBot v11 / Milky.

Provides standard JSON-RPC 2.0 stdio MCP server for Google Antigravity agents.
Enables agents to call OneBot v11 messaging, group management, and forward chat retrieval tools.
"""

import asyncio
import json
import os
import sys
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional


class OneBotMcpServer:
    """Stdio-based Model Context Protocol Server."""

    def __init__(self, onebot_http_url: Optional[str] = None, access_token: Optional[str] = None):
        self.http_url = (onebot_http_url or os.getenv("ONEBOT_HTTP_URL") or "http://127.0.0.1:3000").rstrip("/")
        self.access_token = access_token or os.getenv("ONEBOT_ACCESS_TOKEN", "")

    def _call_onebot_api(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Invoke OneBot HTTP endpoint synchronously."""
        url = f"{self.http_url}/{endpoint}"
        body = json.dumps(params or {}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                res_bytes = resp.read()
                return json.loads(res_bytes.decode("utf-8"))
        except Exception as e:
            return {"status": "failed", "retcode": -1, "error": str(e)}

    def get_tools(self) -> List[Dict[str, Any]]:
        """Return list of tools exposed to Antigravity agents."""
        return [
            {
                "name": "onebot_send_private_msg",
                "description": "Send a private chat message to a QQ user via OneBot v11.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "Target QQ user ID."},
                        "message": {"type": "string", "description": "Message text or CQ code content."},
                    },
                    "required": ["user_id", "message"],
                },
            },
            {
                "name": "onebot_send_group_msg",
                "description": "Send a message to a QQ group via OneBot v11.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "group_id": {"type": "string", "description": "Target QQ group ID."},
                        "message": {"type": "string", "description": "Message text or CQ code content."},
                    },
                    "required": ["group_id", "message"],
                },
            },
            {
                "name": "onebot_get_msg",
                "description": "Fetch message details by message ID.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message_id": {"type": "string", "description": "OneBot message ID."},
                    },
                    "required": ["message_id"],
                },
            },
            {
                "name": "onebot_get_forward_msg",
                "description": "Retrieve and inspect merged forward chat history by forward ID.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "forward_id": {"type": "string", "description": "Forward/resource ID."},
                    },
                    "required": ["forward_id"],
                },
            },
            {
                "name": "onebot_delete_msg",
                "description": "Recall a previously sent message by message ID.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message_id": {"type": "string", "description": "Message ID to recall."},
                    },
                    "required": ["message_id"],
                },
            },
            {
                "name": "onebot_get_group_info",
                "description": "Get group details (name, member count, max member count).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "group_id": {"type": "string", "description": "QQ group ID."},
                    },
                    "required": ["group_id"],
                },
            },
            {
                "name": "onebot_get_group_member_list",
                "description": "Get list of members in a specified QQ group.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "group_id": {"type": "string", "description": "QQ group ID."},
                    },
                    "required": ["group_id"],
                },
            },
            {
                "name": "onebot_set_group_ban",
                "description": "Mute/ban a user in a QQ group (duration in seconds, 0 to unmute).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "group_id": {"type": "string", "description": "QQ group ID."},
                        "user_id": {"type": "string", "description": "Target user ID."},
                        "duration": {"type": "integer", "description": "Mute duration in seconds (0 for unmute).", "default": 1800},
                    },
                    "required": ["group_id", "user_id"],
                },
            },
            {
                "name": "onebot_send_voice",
                "description": "Send a voice/audio message to a QQ group or private user.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target_type": {"type": "string", "enum": ["group", "private"], "description": "Destination type."},
                        "target_id": {"type": "string", "description": "Group ID or User ID."},
                        "file": {"type": "string", "description": "Local path or URL of audio file (amr/silk/mp3/wav)."},
                    },
                    "required": ["target_type", "target_id", "file"],
                },
            },
        ]

    def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute tool call and return result."""
        if name == "onebot_send_private_msg":
            return self._call_onebot_api("send_private_msg", {
                "user_id": int(arguments["user_id"]),
                "message": arguments["message"],
            })
        elif name == "onebot_send_group_msg":
            return self._call_onebot_api("send_group_msg", {
                "group_id": int(arguments["group_id"]),
                "message": arguments["message"],
            })
        elif name == "onebot_get_msg":
            return self._call_onebot_api("get_msg", {
                "message_id": int(arguments["message_id"]),
            })
        elif name == "onebot_get_forward_msg":
            return self._call_onebot_api("get_forward_msg", {
                "id": str(arguments["forward_id"]),
            })
        elif name == "onebot_delete_msg":
            return self._call_onebot_api("delete_msg", {
                "message_id": int(arguments["message_id"]),
            })
        elif name == "onebot_get_group_info":
            return self._call_onebot_api("get_group_info", {
                "group_id": int(arguments["group_id"]),
            })
        elif name == "onebot_get_group_member_list":
            return self._call_onebot_api("get_group_member_list", {
                "group_id": int(arguments["group_id"]),
            })
        elif name == "onebot_set_group_ban":
            return self._call_onebot_api("set_group_ban", {
                "group_id": int(arguments["group_id"]),
                "user_id": int(arguments["user_id"]),
                "duration": int(arguments.get("duration", 1800)),
            })
        elif name == "onebot_send_voice":
            ttype = arguments["target_type"]
            tid = int(arguments["target_id"])
            file_val = arguments["file"]
            msg = f"[CQ:record,file={file_val}]"
            endpoint = "send_group_msg" if ttype == "group" else "send_private_msg"
            key = "group_id" if ttype == "group" else "user_id"
            return self._call_onebot_api(endpoint, {key: tid, "message": msg})
        else:
            raise ValueError(f"Unknown tool name: {name}")

    def run(self) -> None:
        """Main stdio JSON-RPC loop."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            if method == "initialize":
                res = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {
                            "name": "antigravity-onebot-mcp",
                            "version": "1.0.0",
                        },
                    },
                }
                sys.stdout.write(json.dumps(res, ensure_ascii=False) + "\n")
                sys.stdout.flush()
            elif method == "tools/list":
                res = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": self.get_tools()},
                }
                sys.stdout.write(json.dumps(res, ensure_ascii=False) + "\n")
                sys.stdout.flush()
            elif method == "tools/call":
                tname = params.get("name")
                targs = params.get("arguments", {})
                try:
                    out = self.handle_tool_call(tname, targs)
                    res = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False, indent=2)}]
                        },
                    }
                except Exception as e:
                    res = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{"type": "text", "text": f"Error: {e}"}],
                            "isError": True,
                        },
                    }
                sys.stdout.write(json.dumps(res, ensure_ascii=False) + "\n")
                sys.stdout.flush()
            else:
                if msg_id is not None:
                    res = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32601, "message": f"Method '{method}' not found"},
                    }
                    sys.stdout.write(json.dumps(res, ensure_ascii=False) + "\n")
                    sys.stdout.flush()


if __name__ == "__main__":
    server = OneBotMcpServer()
    server.run()
