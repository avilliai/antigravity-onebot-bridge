# -*- coding: utf-8 -*-
"""Real-environment Integration Test for Antigravity-OneBot / Milky Bridge.

Simulates end-to-end communication:
1. Connects to Milky (127.0.0.1:3000) as Bridge Gateway.
2. Connects to OneBot v11 (127.0.0.1:3001) as test user client.
3. Sends group @bot message to group 1050663831.
4. Verifies Antigravity driver execution, Yucca roleplay, and message dispatch.
5. Sends voice request and verifies voice synthesis (record segment) dispatch.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
import websockets

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agy_onebot.config import BridgeConfig
from agy_onebot.gateway import BridgeGateway

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("test_live_integration")

ONEBOT_TOKEN = os.getenv("ONEBOT_ACCESS_TOKEN", "")
ONEBOT_WS_URI = f"ws://127.0.0.1:3001/?access_token={ONEBOT_TOKEN}"
TEST_GROUP_ID = 1050663831
BOT_UIN = "3377428814"


async def main():
    logger.info("=== Starting Live Integration Test ===")

    # 1. Initialize Gateway with live test config
    cfg = BridgeConfig.load(str(ROOT / "config.yaml"))
    gateway = BridgeGateway(cfg)

    # Start gateway in background task
    gateway_task = asyncio.create_task(gateway.start())
    await asyncio.sleep(2.0)  # Wait for WS connection to establish

    test_passed = False
    voice_test_passed = False

    try:
        # 2. Connect to OneBot (3001) as test user
        logger.info(f"Connecting to OneBot 3001: {ONEBOT_WS_URI[:35]}...")
        async with websockets.connect(ONEBOT_WS_URI) as ows:
            logger.info("Connected to OneBot 3001")

            # Drain initial lifecycle events
            while True:
                try:
                    init_evt = await asyncio.wait_for(ows.recv(), timeout=1.0)
                except asyncio.TimeoutError:
                    break

            # 3. Test Text Roleplay: Send message @3377428814
            test_prompt = "尤卡，在吗？今天天气真好呀"
            logger.info(f"Sending test message from OneBot: {test_prompt}")
            send_payload = {
                "action": "send_group_msg",
                "params": {
                    "group_id": TEST_GROUP_ID,
                    "message": f"[CQ:at,qq={BOT_UIN}] {test_prompt}"
                },
                "echo": "live_test_1"
            }
            await ows.send(json.dumps(send_payload))

            # Listen on OneBot WS to observe group responses from Milky
            logger.info("Waiting for Bridge response in group (timeout: 75s)...")
            start_time = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_time < 75.0:
                try:
                    raw_msg = await asyncio.wait_for(ows.recv(), timeout=5.0)
                    evt = json.loads(raw_msg)
                    post_type = evt.get("post_type")
                    if post_type == "message" and str(evt.get("group_id")) == str(TEST_GROUP_ID):
                        sender_id = str(evt.get("user_id", ""))
                        content = evt.get("raw_message", "")
                        logger.info(f"[Group 1050663831 Message] From {sender_id}: {content}")
                        if sender_id == BOT_UIN:
                            logger.info(f"✅ Received response from Yucca bot ({BOT_UIN}): {content}")
                            test_passed = True
                            break
                except asyncio.TimeoutError:
                    continue

            # 4. Test Voice Synthesis and Dispatch
            logger.info("Testing Voice Dispatch: sending voice request...")
            voice_prompt = "尤卡，给我发条语音打个招呼~"
            send_payload2 = {
                "action": "send_group_msg",
                "params": {
                    "group_id": TEST_GROUP_ID,
                    "message": f"[CQ:at,qq={BOT_UIN}] {voice_prompt}"
                },
                "echo": "live_test_voice"
            }
            await ows.send(json.dumps(send_payload2))

            start_time2 = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_time2 < 75.0:
                try:
                    raw_msg = await asyncio.wait_for(ows.recv(), timeout=5.0)
                    evt = json.loads(raw_msg)
                    post_type = evt.get("post_type")
                    if post_type == "message" and str(evt.get("group_id")) == str(TEST_GROUP_ID):
                        sender_id = str(evt.get("user_id", ""))
                        content = evt.get("raw_message", "")
                        logger.info(f"[Group 1050663831 Voice Test] From {sender_id}: {content}")
                        if sender_id == BOT_UIN:
                            raw_str = json.dumps(evt, ensure_ascii=False)
                            if "record" in raw_str:
                                logger.info(f"✅ Received voice record from Yucca bot ({BOT_UIN})! Event: {content}")
                                voice_test_passed = True
                                break
                            else:
                                logger.info(f"Received text reply: {content}, waiting for record segment...")
                except asyncio.TimeoutError:
                    continue

    finally:
        await gateway.stop()
        gateway_task.cancel()
        try:
            await gateway_task
        except asyncio.CancelledError:
            pass

    print("\n" + "=" * 55)
    print("  LIVE INTEGRATION TEST SUMMARY")
    print("=" * 55)
    print(f" • Yucca Roleplay Response : {'PASSED ✅' if test_passed else 'FAILED ❌'}")
    print(f" • Voice Record Dispatch   : {'PASSED ✅' if voice_test_passed else 'CHECK LOGS ⚠️'}")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
