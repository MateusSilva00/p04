import json
import logging
from collections.abc import Callable

import pika
from pika.adapters.blocking_connection import BlockingChannel

from src.core.models import EventEnvelope
from src.core.security import CryptoService

logger = logging.getLogger(__name__)


class RabbitMQClient:
    """
    Cliente Abstraído para o RabbitMQ
    """

    def __init__(
        self,
        amqp_url: str = "amqp://localhost?heartbeat=0",
        exchange_name: str = "Promocoes",
    ):
        """Inicializa a conexão e garante que a exchange exista."""
        parameters = pika.URLParameters(amqp_url)
        self.connection = pika.BlockingConnection(parameters=parameters)
        self.channel: BlockingChannel = self.connection.channel()
        self.exchange_name = exchange_name

        self.channel.exchange_declare(exchange=self.exchange_name, exchange_type="topic")

    def publish_signed_event(self, envelope: EventEnvelope, private_key_pem: bytes) -> None:
        """
        Gera o hash, assina o evento e  o publica na exchange
        """
        payload_bytes = envelope.get_hashable_content()
        signature = CryptoService.sign_message(
            private_key_pem=private_key_pem, payload_bytes=payload_bytes
        )
        envelope.signature = signature
        self.channel.basic_publish(
            exchange=self.exchange_name,
            routing_key=envelope.routing_key,
            body=envelope.model_dump_json(),
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
        )

        logger.info(f"Evento publicado e assinado: {envelope.routing_key}")

    def publish_unsigned_event(self, envelope: EventEnvelope) -> None:
        self.channel.basic_publish(
            exchange=self.exchange_name,
            routing_key=envelope.routing_key,
            body=envelope.model_dump_json(),
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
        )
        logger.info(f"Evento publicado SEM assinatura: {envelope.routing_key}")

    def setup_consumer(
        self,
        queue_name: str,
        routing_keys: list[str],
        public_key_pem: bytes,
        callback: Callable[[EventEnvelope], None],
    ) -> None:
        """
        Configura uma fila, faz os bindings necessários e inicia o consumo
        com validação de assinatura.
        """
        self.channel.queue_declare(queue=queue_name, durable=True)

        for rk in routing_keys:
            self.channel.queue_bind(exchange=self.exchange_name, queue=queue_name, routing_key=rk)

            def internal_callback(ch, method, properties, body):
                try:
                    data = json.loads(body)
                    envelope = EventEnvelope(**data)
                    payload_bytes = envelope.get_hashable_content()

                    if envelope.signature and CryptoService.verify_signature(
                        public_key_pem=public_key_pem,
                        payload_byes=payload_bytes,
                        signature_b64=envelope.signature,
                    ):
                        callback(envelope)
                    else:
                        logger.warning(
                            "Messagem descartada! Assinatura inválida"
                            f" na routing_key: {method.routing_key}"
                        )

                except Exception as e:
                    logger.error(f"Erro ao processar mensagem recebida: {e}")
                finally:
                    ch.basic_ack(delivery_tag=method.delivery_tag)

            self.channel.basic_consume(
                queue=queue_name, on_message_callback=internal_callback, auto_ack=False
            )

            logger.info(
                f"[*] Aguardando mensagens na fila '{queue_name}'. Para sair pressione CTRL+C"
            )
            self.channel.start_consuming()

    def close(self):
        if self.connection and self.connection.is_open:
            self.connection.close()

    def setup_multi_consumer(
        self,
        queue_name: str,
        handlers: dict[str, tuple[bytes, Callable[[EventEnvelope], None]]],
    ) -> None:
        """
        Fila única com múltiplas routing_keys, cada uma com sua própria
        chave pública e callback.

        handlers: { routing_key: (public_key_pem, callback) }
        """
        self.channel.queue_declare(queue=queue_name, durable=True)

        for rk in handlers:
            self.channel.queue_bind(exchange=self.exchange_name, queue=queue_name, routing_key=rk)

        def internal_callback(ch, method, properties, body):
            try:
                data = json.loads(body)
                envelope = EventEnvelope(**data)

                handler_entry = handlers.get(method.routing_key)
                if handler_entry is None:
                    logger.warning(f"Sem handler para routing_key: {method.routing_key}")
                    return

                public_key_pem, callback = handler_entry
                payload_bytes = envelope.get_hashable_content()

                if envelope.signature and CryptoService.verify_signature(
                    public_key_pem=public_key_pem,
                    payload_byes=payload_bytes,
                    signature_b64=envelope.signature,
                ):
                    callback(envelope)
                else:
                    logger.warning(
                        "Messagem descartada! Assinatura inválida"
                        f" na routing_key: {method.routing_key}"
                    )
            except Exception as e:
                logger.error(f"Erro ao processar mensagem recebida: {e}")
            finally:
                ch.basic_ack(delivery_tag=method.delivery_tag)

        self.channel.basic_consume(
            queue=queue_name, on_message_callback=internal_callback, auto_ack=False
        )

        logger.info(f"[*] Aguardando mensagens na fila '{queue_name}'. Para sair pressione CTRL+C")
        self.channel.start_consuming()

    def setup_unsigned_consumer(
        self,
        queue_name: str,
        routing_keys: list[str],
        callback: Callable[[EventEnvelope], None],
    ) -> None:
        self.channel.queue_declare(queue=queue_name, durable=True)

        for rk in routing_keys:
            self.channel.queue_bind(exchange=self.exchange_name, queue=queue_name, routing_key=rk)

        def internal_callback(ch, method, properties, body):
            try:
                data = json.loads(body)
                envelope = EventEnvelope(**data)
                callback(envelope)
            except Exception as e:
                logger.error(f"Erro ao processar mensagem não assinada: {e}")
            finally:
                ch.basic_ack(delivery_tag=method.delivery_tag)

        self.channel.basic_consume(
            queue=queue_name, on_message_callback=internal_callback, auto_ack=False
        )

        logger.info(f"[*] Aguardando notificações na fila '{queue_name}'.")
        self.channel.start_consuming()
