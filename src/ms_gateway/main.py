import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger

from src.core.models import (
    InterestRequest,
    PromoCreateRequest,
    PromoPayload,
    SSEMessage,
    VotoPayload,
    VotoRequest,
)
from src.ms_gateway.manager import connection_manager
from src.ms_gateway.service import gateway_service


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    loop = asyncio.get_running_loop()
    gateway_service.start(loop)
    logger.info("MS Gateway API iniciado")
    yield
    gateway_service.stop()
    logger.info("MS Gateway API encerrado")


app = FastAPI(
    title="MS Gateway - API de Promoções",
    description="API REST/SSE DE PROMOÇÕES",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post(
    "/promocoes",
    response_model=PromoPayload,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar nova promoção",
)
async def criar_promocao(request: PromoCreateRequest) -> PromoPayload:
    return await asyncio.to_thread(gateway_service.publish_promocao, request)


@app.get(
    "/promocoes",
    response_model=list[PromoPayload],
    summary="Listar promoções aprovadas",
)
async def listar_promocoes() -> list[PromoPayload]:
    return list(gateway_service.approved_promotions.values())


@app.post(
    "/promocoes/{id_promocao}/votos",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Registrar voto em uma promoção",
)
async def registrar_voto(id_promocao: str, request: VotoRequest) -> dict[str, str]:
    promos = gateway_service.approved_promotions

    if id_promocao not in promos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Promoção '{id_promocao}' não encontrado",
        )

    promo = promos[id_promocao]
    voto_payload = VotoPayload(
        id_promocao=id_promocao, nome_produto=promo.nome_produto, voto=request.voto
    )

    await asyncio.to_thread(gateway_service.publish_voto, voto_payload)
    return {"status": "voto registrado"}


@app.post(
    "/clientes/{client_id}/interesses",
    status_code=status.HTTP_201_CREATED,
    summary="Registrar interesse em categoria",
)
async def registrar_interesse(
    client_id: str, request: InterestRequest
) -> dict[str, str | list[str]]:
    connection_manager.register_interest(client_id, request.category)
    return {
        "client_id": client_id,
        "interesses": sorted(connection_manager.get_interests(client_id)),
    }


@app.delete(
    "/clientes/{client_id}/interesses/{categoria}",
    summary="Remover interesse em categoria",
)
async def remover_interesse(client_id: str, categoria: str) -> dict[str, str | list[str]]:
    connection_manager.remove_interest(client_id, categoria)
    return {
        "client_id": client_id,
        "interesses": sorted(connection_manager.get_interests(client_id)),
    }


@app.get(
    "/clientes/{client_id}/sse",
    summary="Stream SSE de notificações",
)
async def sse_stream(client_id: str) -> StreamingResponse:
    """
    Abre uma conexão persistente Server-Sent Events.
    """

    async def event_generator() -> AsyncGenerator[str]:
        queue = await connection_manager.connect(client_id)
        try:
            while True:
                message: SSEMessage = await queue.get()
                yield message.to_sse_format()
        except asyncio.CancelledError:
            logger.debug("SSE cancelado para cliente {}", client_id)
        finally:
            connection_manager.disconnect(client_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
