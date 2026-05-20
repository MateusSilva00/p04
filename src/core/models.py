import json
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    """
    Envelope padrão para todos os eventos do sistema.
    """

    routing_key: str = Field(
        ..., description="Chave de roteamento hierárquica (ex: promocao.recebida)"
    )
    payload: Dict[str, Any] = Field(
        ..., description="Os dados reais do evento (o corpo da mensagem)"
    )
    signature: Optional[str] = Field(
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
