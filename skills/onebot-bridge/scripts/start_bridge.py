# -*- coding: utf-8 -*-
"""Launcher helper for Antigravity-OneBot Bridge."""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from agy_onebot.gateway import BridgeGateway
from agy_onebot.config import BridgeConfig


def main():
    config = BridgeConfig.load()
    gateway = BridgeGateway(config)
    print(f"Starting Antigravity-OneBot Bridge Gateway ({config.onebot.mode} mode)...")
    try:
        asyncio.run(gateway.start())
    except KeyboardInterrupt:
        print("\nGateway stopped by user.")


if __name__ == "__main__":
    main()
