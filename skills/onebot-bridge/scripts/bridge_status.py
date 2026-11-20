# -*- coding: utf-8 -*-
"""Check OneBot bridge connectivity and local endpoint status."""

import json
import sys
import urllib.request
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from agy_onebot.config import BridgeConfig


def check_status():
    cfg = BridgeConfig.load()
    print("=== Antigravity OneBot Bridge Status Check ===")
    print(f"OneBot Mode     : {cfg.onebot.mode}")
    print(f"OneBot WS URL   : {cfg.onebot.ws_url}")
    print(f"Antigravity Mode: {cfg.antigravity.mode}")
    print(f"Default Persona : {cfg.roleplay.default_role}")

    # Check HTTP endpoint if configured
    test_url = cfg.onebot.ws_url.replace("ws://", "http://").replace("wss://", "https://")
    print(f"\nProbing OneBot HTTP endpoint ({test_url})...")
    try:
        req = urllib.request.Request(f"{test_url}/get_version_info", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[SUCCESS] OneBot Version: {data.get('data', {}).get('app_version', 'Unknown')}")
    except Exception as e:
        print(f"[NOTICE] Direct HTTP probe ({e}). Note that WebSocket mode connects dynamically upon gateway startup.")


if __name__ == "__main__":
    check_status()
