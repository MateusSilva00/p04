import asyncio
import os
import threading
import uuid

from loguru import logger

from src.core.models import (
    EventEnvelope,
    PromoCreateRequest,
    PromoPayload,
    SSEEventType,
    SSEMessage,
    VotoPayload,
)
from src.core.rabbitmq import RabbitMQClient
from src.core.security import CryptoService
from src.ms_gateway.manager import connection_manager


class GatewayService:
    """
    Ponte entre RabbitMQ e FastAPI
    """

    def __init__(self) -> None:
        self._publisher: RabbitMQClient | None = None
        self._consumer: RabbitMQClient | None = None
        self._private_key: bytes = b""
        self._promocao_public_key: bytes = b""
        self._ranking_public_key: bytes = b""
        self._consumer_thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._approved: dict[str, PromoPayload] = {}

    @property
    def approved_promotions(self) -> dict[str, PromoPayload]:
        return self._approved

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._load_keys()

        self._publisher = RabbitMQClient()
        logger.info("Publisher RabbitMQ conectado")

        self._consumer_thread = threading.Thread(target=self._run_consumer, daemon=True)
        self._consumer_thread.start()
        logger.info("Consumer RabbitMQ iniciado em background")

    def _run_consumer(self) -> None:
        """Loop blocking do pika - rodando em thread daemon"""
        logger.info("Iniciando consumer RabbitMQ...")
        try:
            self._consumer = RabbitMQClient()
            self._consumer.setup_multi_consumer(
                queue_name="Fila_Gateway_API",
                handlers={
                    "promocao.publicada": (
                        self._promocao_public_key,
                        self._on_promocao_publicada,
                    ),
                    "promocao.destaque": (
                        self._ranking_public_key,
                        self._on_destaque,
                    ),
                },
            )
        except Exception:
            logger.exception("Erro fatal no consumer RabbitMQ")

    def _load_keys(self) -> None:
        self._private_key, _ = CryptoService.load_or_generate_keys("ms_gateway")
        keys_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../keys"))

        promocao_pub_path = os.path.join(keys_dir, "ms_promocao_public.pem")
        if os.path.exists(promocao_pub_path):
            with open(promocao_pub_path, "rb") as file:
                self._promocao_public_key = file.read()
            logger.info("Chave pública do MS Promoção carrega")

        ranking_pub_path = os.path.join(keys_dir, "ms_ranking.pem")
        if os.path.exists(ranking_pub_path):
            with open(ranking_pub_path, "rb") as file:
                self._ranking_public_key = file.read()
            logger.info("Chave pública do MS Ranking carregada")

    def _on_promocao_publicada(self, envelope: EventEnvelope) -> None:
        data = envelope.payload
        promo = PromoPayload(**{k: data[k] for k in PromoPayload.model_fields})
        self._approved[promo.id_promocao] = promo

        message = SSEMessage(event=SSEEventType.PROMOCAO_PUBLICADA, data=data)
        self._dispatch_sse(message)
        logger.info("Promoção aprovada: {}", promo.nome_produto)

    def _on_destaque(self, envelope: EventEnvelope) -> None:
        data = envelope.payload
        id_promo = data["id_promocao"]

        if id_promo in self._approved:
            enriched = self._approved[id_promo].model_dump()
            enriched["score"] = data.get("score")
            enriched["aviso"] = "hot_deal"
            data = enriched

        message = SSEMessage(event=SSEEventType.HOT_DEAL, data=data)
        self._dispatch_sse(message)
        logger.info(f"Hot Deal recebido: {id_promo}")

    def _dispatch_sse(self, message: SSEMessage) -> None:
        if self._loop is None:
            logger.warning("Event loop indisponível para dispatch SSE")
            return

        asyncio.run_coroutine_threadsafe(
            connection_manager.broadcast(message),
            self._loop,
        )

    def stop(self) -> None:
        if self._publisher:
            self._publisher.close()
        if self._consumer:
            self._consumer.close()
        logger.info("GatewayService encerrado")

    def publish_promocao(self, request: PromoCreateRequest) -> PromoPayload:
        if not self._publisher:
            raise RuntimeError("Publisher não inicializado!")

        payload = PromoPayload(
            id_promocao=str(uuid.uuid4())[:4],
            nome_produto=request.nome_produto,
            categoria=request.categoria,
            preco=request.preco,
            loja=request.loja,
        )

        payload_dict = payload.model_dump()
        payload_dict["loja_email"] = request.loja_email

        envelope = EventEnvelope(
            routing_key="promocao.recebida", payload=payload_dict, signature=""
        )

        self._publisher.publish_signed_event(envelope=envelope, private_key_pem=self._private_key)

        logger.info(f"Promoção enviada ao broker: {payload.nome_produto} - {payload.id_promocao}")

        return payload

    def publish_voto(self, voto: VotoPayload) -> None:
        if not self._publisher:
            raise RuntimeError("Publisher não inicializado")

        envelope = EventEnvelope(routing_key="promocao.voto", payload=voto.model_dump())

        self._publisher.publish_signed_event(envelope, self._private_key)
        emoji = ("👍" if voto.voto > 0 else "👎",)
        logger.info(f"Voto publicado: {voto.id_promocao} - {emoji}")


gateway_service = GatewayService()
