import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    """
    Envelope padrão para todos os eventos do sistema.
    """

    routing_key: str = Field(
        ..., description="Chave de roteamento hierárquica (ex: promocao.recebida)"
    )
    payload: dict[str, Any] = Field(
        ..., description="Os dados reais do evento (o corpo da mensagem)"
    )
    signature: str | None = Field(
        None, description="Assinatura digital gerada com a chave privada do produtor"
    )

    def get_hashable_content(self) -> bytes:
        content_str = json.dumps(self.payload, sort_keys=True, separators=(",", ":"))
        return content_str.encode("utf-8")


class PromoPayload(BaseModel):
    """Payload para criação e publicação de promoões"""

    id_promocao: str
    nome_produto: str
    categoria: str
    preco: float
    loja: str


class VotoPayload(BaseModel):
    """Payload para o registro de votos."""

    id_promocao: str
    nome_produto: str
    voto: int = Field(..., description="1 para positivo, -1 para negativo")


class SSEEventType(StrEnum):
    PROMOCAO_PUBLICADA = "promocao_publicada"
    HOT_DEAL = "hot_deal"


class SSEMessage(BaseModel):
    event: SSEEventType
    data: dict[str, Any]

    def to_sse_format(self) -> str:
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"


class InterestRequest(BaseModel):
    category: str = Field(
        ...,
        min_length=1,
        description="Categoria de interesse (ex: 'eletronicos', 'moda', etc.)",
    )


class PromoCreateRequest(BaseModel):
    nome_produto: str = Field(..., description="Nome do produto em promoção", min_length=1)
    categoria: str = Field(..., description="Categoria do produto", min_length=1)
    preco: float = Field(..., gt=0, description="Preço do produto em promoção")
    loja: str = Field(..., description="Loja onde a promoção é válida", min_length=1)
    loja_email: str = Field(..., description="Email de contato da loja", min_length=1)
    signature: str = Field(..., description="Assinatura digital do payload")
