import asyncio

from loguru import logger


class ConnectionManager:
    """
    Gerencia conexões ativas
    """

    def __init__(self) -> None:
        self.active_connections: dict[str, asyncio.Queue] = {}
        self.client_interests: dict[str, set[str]] = {}

    async def connect(self, client_id) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self.active_connections[client_id] = queue

        if client_id not in self.client_interests:
            self.client_interests[client_id] = set()
        logger.info(f"Cliente SSE connectado: {client_id}")
        return queue

    def disconnect(self, client_id) -> None:
        if client_id not in self.active_connections:
            return None
        del self.active_connections[client_id]
        logger.info(f"Cliente SSE desconectado: {client_id}")

    def register_interest(self, client_id: str, category: str) -> None:
        clean_category = category.strip().lower()
        if client_id not in self.client_interests:
            self.client_interests[client_id] = set()
        self.client_interests[client_id].add(clean_category)
        logger.info(f"Interesse registrado: Cliente {client_id} -> Categoria {category}")

    def remove_interest(self, client_id: str, category: str) -> None:
        clean_category = category.strip().lower()
        if (
            client_id in self.client_interests
            and clean_category in self.client_interests[client_id]
        ):
            self.client_interests[client_id].remove(clean_category)
            logger.info(
                "Interesse removido: Cliente {} -> Categoria '{}'",
                client_id,
                clean_category,
            )

    async def broadcast_event(self, event_type: str, payload: dict) -> None:
        """
        Envia mensagem para as conexões ativas baseando-se nos filtros
        """
        message = {"event": event_type, "data": payload}

        for client_id, queue in list(self.active_connections.items()):
            should_send = False

            if event_type == "hot_deal":
                should_send = True

            elif event_type == "promocao_publicada":
                category = payload.get("categoria", "").strip().lower()
                interests = self.client_interests.get(client_id, set())
                if category in interests:
                    should_send = True

            if should_send:
                try:
                    await queue.put(message)
                except Exception as e:
                    logger.error(f"Falha ao enviar mensagem SSE para {client_id}. Error {e}")


connection_manager = ConnectionManager()
