---
name: qq-roleplay
description: >-
  Inspect, list, and switch character personas (role cards) for Antigravity QQ roleplay.
  Use when configuring personas or altering the agent's character in QQ chats.
---

# QQ Roleplay Persona Skill

This skill allows Antigravity agents and users to view and switch character persona cards.

## Available Actions

### 1. List Available Personas
```bash
python skills/qq-roleplay/scripts/switch_role.py --list
```

### 2. Inspect Persona Card Details
```bash
python skills/qq-roleplay/scripts/switch_role.py --show shiro
```

### 3. Adding New Personas
Create a new Markdown file under `roles/<name>.md`. You can use section tags:
- `## Heading 〔群聊〕`: Injected only in group chats.
- `## Heading 〔私聊〕`: Injected only in private messages.
- `## Heading`: Injected everywhere.
