from __future__ import annotations

import time
import threading
from typing import Any


class OpenPIWebsocketClient:
    def __init__(self, host: str, port: int, api_key: str | None = None) -> None:
        import websockets.sync.client
        from rollout.serialization import Packer, unpackb

        self._uri = host if host.startswith("ws://") or host.startswith("wss://") else f"ws://{host}:{port}"
        self._api_key = api_key
        self._packer = Packer()
        self._unpackb = unpackb
        self._io_lock = threading.Lock()
        self._ws, self._metadata = self._wait_for_server(websockets.sync.client)

    @property
    def metadata(self) -> dict[str, Any]:
        return dict(self._metadata)

    def infer(self, observation: dict[str, Any]) -> dict[str, Any]:
        with self._io_lock:
            self._ws.send(self._packer.pack(observation))
            response = self._ws.recv()
            if isinstance(response, str):
                raise RuntimeError(f"Error in OpenPI server:\n{response}")
            return self._unpackb(response)

    def reset(self) -> None:
        return

    def _wait_for_server(self, websocket_client_module) -> tuple[Any, dict[str, Any]]:
        headers = {"Authorization": f"Api-Key {self._api_key}"} if self._api_key else None
        while True:
            try:
                conn = websocket_client_module.connect(
                    self._uri,
                    compression=None,
                    max_size=None,
                    additional_headers=headers,
                )
                metadata = self._unpackb(conn.recv())
                return conn, metadata
            except ConnectionRefusedError:
                time.sleep(2.0)
