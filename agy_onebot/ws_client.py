# -*- coding: utf-8 -*-
"""WebSocket Client & Server for OneBot v11 / Milky Protocol.

Supports:
- Forward WebSocket (connects to OneBot / Milky event WS)
- Reverse WebSocket (server listens for OneBot client connections)
- WebSocket action calling with unique echo tracking
- HTTP REST API calling fallback (for Milky Protocol 1.3 / OneBot HTTP endpoints)
"""

import asyncio
import json
import logging
import urllib.request
import urllib.error
import uuid
from typing import Any, Callable, Coroutine, Dict, Optional, Set
import websockets

logger = logging.getLogger("agy_onebot.ws")


class OneBotWebSocketTransport:
    """Handles WebSocket transport and HTTP API calling for OneBot v11 & Milky."""

    def __init__(
        self,
        mode: str = "forward",  # "forward" or "reverse"
        url: str = "ws://127.0.0.1:3001",
        api_url: str = "http://127.0.0.1:3000",
        host: str = "0.0.0.0",
        port: int = 8080,
        access_token: Optional[str] = None,
        heartbeat_interval: float = 30.0,
    ):
        self.mode = mode.lower()
        self.url = url
        self.api_url = api_url.rstrip("/")
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
        logger.info(f"Starting Reverse WebSocket server on {self.host}:{self.port}")

        async def _handler(websocket):
            logger.info(f"Client connected: {websocket.remote_address}")
            self._active_connections.add(websocket)
            try:
                async for message in websocket:
                    await self._on_raw_message(message, websocket)
            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"Client disconnected: {websocket.remote_address}")
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
                logger.info(f"Connecting to WebSocket at {self.url}...")
                kwargs = {}
                if headers:
                    kwargs["additional_headers"] = headers

                async with websockets.connect(self.url, **kwargs) as ws:
                    logger.info("Successfully connected to WebSocket.")
                    self._active_connections.add(ws)
                    retry_delay = 2.0

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
        """Invoke action via active WebSocket connection, falling back to HTTP API if no WS available."""
        if self._active_connections:
            echo_id = f"agy_{uuid.uuid4().hex[:12]}"
            req = {
                "action": action,
                "params": params or {},
                "echo": echo_id,
            }

            loop = asyncio.get_running_loop()
            fut = loop.create_future()
            self._pending_actions[echo_id] = fut

            ws = next(iter(self._active_connections))
            try:
                await ws.send(json.dumps(req, ensure_ascii=False))
                res = await asyncio.wait_for(fut, timeout=timeout)
                return res
            except (asyncio.TimeoutError, Exception) as e:
                self._pending_actions.pop(echo_id, None)
                logger.debug(f"WS call_action '{action}' not answered ({e}). Trying HTTP API...")

        # Fallback to HTTP REST API
        return await self.call_http_api(action, params, timeout=timeout)

    async def call_http_api(self, action: str, params: Optional[Dict[str, Any]] = None, timeout: float = 15.0) -> Dict[str, Any]:
        """Invoke HTTP REST API endpoint (supports both OneBot and Milky)."""
        api_root = self.api_url
        url = f"{api_root}/{action}"
        body = json.dumps(params or {}, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        def _do_post():
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as he:
                err_text = he.read().decode("utf-8", errors="replace")
                logger.warning(f"HTTP API [{action}] error {he.code}: {err_text}")
                return {"status": "failed", "retcode": he.code, "msg": err_text}
            except Exception as ex:
                logger.warning(f"HTTP API [{action}] request failed: {ex}")
                return {"status": "failed", "retcode": -1, "msg": str(ex)}

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _do_post)
