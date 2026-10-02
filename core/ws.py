"""
Gerenciamento de conexÃµes WebSocket (abstraÃ§Ã£o simples).
"""
from typing import Callable, Dict, Any


class WebSocketService:
    def __init__(self):
        self.callbacks = {}

    def register(self, key: str, callback: Callable[[Dict[str, Any]], None]):
        self.callbacks[key] = callback

    def emit(self, key: str, message: Dict[str, Any]):
        callback = self.callbacks.get(key)
        if callback:
            callback(message)


