#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entrypoint script for Antigravity OneBot Bridge Gateway."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from agy_onebot.config import BridgeConfig
from agy_onebot.gateway import BridgeGateway


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    parser = argparse.ArgumentParser(description="Antigravity OneBot / Milky Gateway")
    parser.add_argument("--config", "-c", type=str, default="config.yaml", help="Path to configuration file")
    parser.add_argument("--mode", "-m", type=str, choices=["forward", "reverse"], help="Override WebSocket connection mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging")
    args = parser.parse_args()

    setup_logging(args.verbose)

    # Load configuration
    config = BridgeConfig.load(args.config)
    if args.mode:
        config.onebot.mode = args.mode

    gateway = BridgeGateway(config)

    print("\n" + "=" * 55)
    print("  🚀 Antigravity - OneBot v11 / Milky Bridge Gateway")
    print("=" * 55)
    print(f" • OneBot Mode : {config.onebot.mode}")
    if config.onebot.mode == "forward":
        print(f" • Target WS   : {config.onebot.ws_url}")
    else:
        print(f" • Listening On: {config.onebot.reverse_host}:{config.onebot.reverse_port}")
    print(f" • Driver Mode : {config.antigravity.mode} ({config.antigravity.model_name})")
    print(f" • Active Role : {config.roleplay.default_role}")
    print("=" * 55 + "\n")

    try:
        asyncio.run(gateway.start())
    except KeyboardInterrupt:
        print("\n[Shutting down] Bridge stopped by user.")


if __name__ == "__main__":
    main()
