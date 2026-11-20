# Antigravity OneBot & Milky Bridge

An Antigravity community plugin and bidirectional messaging gateway that bridges Google Antigravity agents with OneBot v11 and Milky protocol endpoints.

## Features

- **Multi-Protocol Support**: Seamless auto-detection and support for both **OneBot v11** and **Milky Protocol 1.3**.
- **Bidirectional Gateway**: Supports both Forward WebSocket client and Reverse WebSocket server modes.
- **Antigravity Driver Integration**: Connects via Antigravity Python SDK, CLI (`agy`), or API fallback.
- **Model Context Protocol (MCP)**: Bundles stdio MCP server exposing messaging and group management tools directly to agents.
- **Roleplay Support**: Markdown persona cards with section scope filtering (`[群聊]` and `[私聊]`).
- **QQ Text Formatting**: Clean Markdown-to-plain conversion and UTF-16 surrogate-safe message chunking.

## Quick Start

1. Install requirements:
   ```bash
   pip install websockets pyyaml
   ```

2. Copy and customize configuration:
   ```bash
   cp config.example.yaml config.yaml
   ```

3. Start the gateway:
   ```bash
   python run_gateway.py --config config.yaml
   ```

## Milky Protocol Configuration

To connect with a Milky protocol endpoint:
```yaml
onebot:
  protocol: "milky"
  mode: "forward"
  ws_url: "ws://127.0.0.1:3001/event"
  api_url: "http://127.0.0.1:3001/api"
  access_token: ""
  bot_qq: "12345678"
```

## Antigravity Plugin Installation

To use this project as an Antigravity plugin:
1. Place or symlink this directory into your Antigravity plugins directory (`~/.gemini/config/plugins/antigravity-onebot-bridge` or `.agents/plugins/antigravity-onebot-bridge`).
2. Antigravity will discover the plugin manifest `plugin.json`, MCP tools in `mcp_config.json`, and bundled skills in `skills/`.
