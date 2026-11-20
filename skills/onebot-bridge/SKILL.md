---
name: onebot-bridge
description: >-
  Manage, configure, start, and monitor the Antigravity-OneBot Bridge gateway.
  Use when connecting Antigravity with external OneBot v11 or Milky protocol endpoints.
---

# OneBot Bridge Management Skill

This skill provides step-by-step instructions and command tools to manage the connection between Google Antigravity and OneBot v11 / Milky endpoints.

## Operations

### 1. Start the Bridge Gateway
Run the launch script from the plugin root:
```bash
python run_gateway.py --config config.yaml
```
Options:
- `--config <path>`: Specify path to configuration file (defaults to `config.yaml` or `config.example.yaml`).
- `--mode <forward|reverse>`: Override WebSocket mode.

### 2. Verify Connection Status
Run the status check script:
```bash
python skills/onebot-bridge/scripts/bridge_status.py
```

### 3. Key Configuration Settings
In `config.yaml`:
- `onebot.mode`: `forward` (connects to OneBot WS server) or `reverse` (listens for incoming OneBot connection).
- `onebot.ws_url`: e.g. `ws://127.0.0.1:3001`
- `antigravity.mode`: `auto`, `sdk`, `cli`, or `api`.
- `trigger.require_at_in_group`: Require @mention in groups to prevent unintentional chatter.
