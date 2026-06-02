import asyncio
import json
from typing import Any
from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        # sala_id → lista de WebSockets activos
        self._conexiones: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def conectar(self, sala_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            if sala_id not in self._conexiones:
                self._conexiones[sala_id] = []
            self._conexiones[sala_id].append(ws)

    async def desconectar(self, sala_id: str, ws: WebSocket) -> None:
        async with self._lock:
            if sala_id in self._conexiones:
                self._conexiones[sala_id] = [c for c in self._conexiones[sala_id] if c is not ws]
                if not self._conexiones[sala_id]:
                    del self._conexiones[sala_id]

    async def broadcast(self, sala_id: str, mensaje: dict[str, Any]) -> None:
        conexiones = list(self._conexiones.get(sala_id, []))
        if not conexiones:
            return

        texto = json.dumps(mensaje, ensure_ascii=False)
        muertos: list[WebSocket] = []

        for ws in conexiones:
            try:
                await ws.send_text(texto)
            except Exception:
                muertos.append(ws)

        for ws in muertos:
            await self.desconectar(sala_id, ws)

    def conteo_conexiones(self, sala_id: str) -> int:
        return len(self._conexiones.get(sala_id, []))


# Instancia global — un solo manager para toda la app
manager = WebSocketManager()
