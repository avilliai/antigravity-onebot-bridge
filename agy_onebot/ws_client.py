# -*- coding: utf-8 -*-
"""WebSocket Client & Server for OneBot v11 / Milky Protocol.

Supports both Forward WebSocket (client connects to OneBot endpoint)
and Reverse WebSocket (server listens for OneBot client connections).
Implements asynchronous action calling with unique echo tracking.
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Callable, Coroutine, Dict, Optional, Set
import websockets

logger = logging.getLogger("agy_onebot.ws")


class OneBotWebSocketTransport:
    """Handles WebSocket transport for OneBot v11 / Milky."""

    def __init__(
        self,
        mode: str = "forward",  # "forward" or "reverse"
        url: str = "ws://127.0.0.1:3001",
        host: str = "0.0.0.0",
        port: int = 8080,
        access_token: Optional[str] = None,
        heartbeat_interval: float = 30.0,
    ):
        self.mode = mode.lower()
        self.url = url
        self.host = host
        self.port = port
        self.access_token = access_token
        self.heartbeat_interval = heartbeat_interval

        self._active_connections: Set[Any] = set()
        self._pending_actions: Dict[str, asyncio.Future] = {}
        self._running = False
        self._event_handler: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None

    def set_event_handler(self, handler: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]) -> None:
        """Register callback for incoming OneBot / Milky events."""
        self._event_handler = handler

    async def start(self) -> None:
        """Start the WebSocket transport."""
        self._running = True
        if self.mode == "reverse":
            await self._run_reverse_server()
        else:
            asyncio.create_task(self._run_forward_client())

    async def stop(self) -> None:
        """Stop transport and disconnect."""
        self._running = False
        for ws in list(self._active_connections):
            try:
                await ws.close()
            except Exception:
                pass
        self._active_connections.clear()

    async def _run_reverse_server(self) -> None:
        """Run reverse WebSocket server listening for OneBot clients."""
        logger.info(f"Starting OneBot Reverse WebSocket server on {self.host}:{self.port}")

        async def _handler(websocket):
            logger.info(f"OneBot client connected: {websocket.remote_address}")
            self._active_connections.add(websocket)
            try:
                async for message in websocket:
                    await self._on_raw_message(message, websocket)
            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"OneBot client disconnected: {websocket.remote_address}")
            finally:
                self._active_connections.discard(websocket)

        server = await websockets.serve(_handler, self.host, self.port)
        logger.info("Reverse WebSocket server running.")
        try:
            await asyncio.Future()  # run forever
        finally:
            server.close()
            await server.wait_closed()

    async def _run_forward_client(self) -> None:
        """Run forward WebSocket client with auto-reconnection."""
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        retry_delay = 2.0
        while self._running:
            try:
                logger.info(f"Connecting to OneBot WebSocket at {self.url}...")
                # Note: websockets version compatibility for headers
                kwargs = {}
                if headers:
                    kwargs["additional_headers"] = headers

                async with websockets.connect(self.url, **kwargs) as ws:
                    logger.info("Successfully connected to OneBot WebSocket.")
                    self._active_connections.add(ws)
                    retry_delay = 2.0  # reset backoff

                    async for message in ws:
                        await self._on_raw_message(message, ws)
            except (websockets.exceptions.ConnectionClosed, OSError, Exception) as e:
                logger.warning(f"WebSocket disconnected ({e}). Retrying in {retry_delay:.1f}s...")
            finally:
                self._active_connections.clear()

            if self._running:
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, 30.0)

    async def _on_raw_message(self, raw_str: str, ws: Any) -> None:
        """Handle incoming raw WebSocket text payload."""
        try:
            payload = json.loads(raw_str)
        except json.JSONDecodeError:
            logger.warning("Received invalid JSON payload from WebSocket.")
            return

        # Check if this is an action reply matching an echo ID
        echo = payload.get("echo")
        if echo and echo in self._pending_actions:
            fut = self._pending_actions.pop(echo)
            if not fut.done():
                fut.set_result(payload)
            return

        # Otherwise dispatch to registered event handler
        if self._event_handler:
            asyncio.create_task(self._event_handler(payload))

    async def call_action(self, action: str, params: Optional[Dict[str, Any]] = None, timeout: float = 20.0) -> Dict[str, Any]:
        """Invoke a OneBot / Milky action and await the response."""
        if not self._active_connections:
            raise RuntimeError("No active OneBot WebSocket connection available.")

        echo_id = f"agy_{uuid.uuid4().hex[:12]}"
        req = {
            "action": action,
            "params": params or {},
            "echo": echo_id,
        }

        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending_actions[echo_id] = fut

        # Broadcast or send to first active connection
        ws = next(iter(self._active_connections))
        await ws.send(json.dumps(req, ensure_ascii=False))

        try:
            res = await asyncio.wait_for(fut, timeout=timeout)
            return res
        except asyncio.TimeoutError:
            self._pending_actions.pop(echo_id, None)
            raise TimeoutError(f"Action '{action}' timed out after {timeout}s")
