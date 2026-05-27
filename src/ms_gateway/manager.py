import asyncio

from loguru import logger

from src.core.models import SSEEventType, SSEMessage


class ConnectionManager:
    """
    Gerencia conexões SSE ativas e os interesses (categorias) de cada cliente.
    """

    def __init__(self) -> None:
        self._connections: dict[str, asyncio.Queue[SSEMessage]] = {}
        self._interests: dict[str, set[str]] = {}

    @property
    def active_count(self) -> int:
        return len(self._connections)

    async def connect(self, client_id: str) -> asyncio.Queue[SSEMessage]:
        queue: asyncio.Queue[SSEMessage] = asyncio.Queue()
        self._connections[client_id] = queue
        self._interests.setdefault(client_id, set())
        logger.info("Cliente SSE conectado: {} (total: {})", client_id, self.active_count)
        return queue

    def disconnect(self, client_id: str) -> None:
        self._connections.pop(client_id, None)
        logger.info("Cliente SSE desconectado: {} (total: {})", client_id, self.active_count)

    def get_interests(self, client_id: str) -> set[str]:
        return self._interests.get(client_id, set())

    def register_interest(self, client_id: str, category: str) -> None:
        normalized = category.strip().lower()
        self._interests.setdefault(client_id, set()).add(normalized)
        logger.info("Interesse registrado: {} -> '{}'", client_id, normalized)

    def remove_interest(self, client_id: str, category: str) -> None:
        normalized = category.strip().lower()
        interests = self._interests.get(client_id)
        if interests and normalized in interests:
            interests.discard(normalized)
            logger.info("Interesse removido: {} -> '{}'", client_id, normalized)

    async def broadcast(self, message: SSEMessage) -> None:
        category = message.data.get("categoria", "").strip().lower()

        for client_id, queue in self._connections.items():
            if self._should_deliver(message.event, category, client_id):
                try:
                    await queue.put(message)
                except Exception:
                    logger.exception("Falha ao enfileirar SSE para cliente {}", client_id)

    def _should_deliver(self, event_type: SSEEventType, category: str, client_id: str) -> bool:
        """Determina se o cliente deve receber o evento."""
        if event_type == SSEEventType.HOT_DEAL:
            return True
        return category in self._interests.get(client_id, set())


# Instância singleton — importada pelos endpoints do FastAPI
connection_manager = ConnectionManager()
