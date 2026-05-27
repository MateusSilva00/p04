"""
Script de Teste de Carga — Bypass da interface do Gateway.

Publica diretamente no RabbitMQ:
  • X promoções  (routing_key = promocao.recebida)
  • Y votos aleatórios (routing_key = promocao.voto)

Os eventos são devidamente assinados com a chave privada do Gateway para
que os microsserviços downstream os aceitem sem rejeitar por assinatura.

Uso:
    uv run python -m src.scripts.load_test --promocoes 20 --votos 60
    uv run python -m src.scripts.load_test -p 10 -v 30 --delay 0.05
"""

import argparse
import random
import sys
import time
import uuid

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from src.core.models import EventEnvelope, PromoPayload, VotoPayload
from src.core.rabbitmq import RabbitMQClient
from src.core.security import CryptoService

# ─── Dados sintéticos para geração aleatória ────────────────────────────────

PRODUTOS = [
    'TV 4K OLED 55"',
    "Notebook Gamer RTX 4070",
    "iPhone 15 Pro Max",
    "Samsung Galaxy S24 Ultra",
    "Mouse Logitech MX Master 3S",
    "Cadeira Gamer ThunderX3",
    "Fone Sony WH-1000XM5",
    "Kindle Paperwhite",
    "Echo Dot 5ª Geração",
    "iPad Air M2",
    "PS5 Slim Digital",
    "Webcam Logitech Brio 4K",
    "SSD NVMe 1TB Samsung 990 Pro",
    'Monitor Ultrawide 34" LG',
    "Teclado Mecânico Keychron K8 Pro",
    "Smartwatch Apple Watch Ultra 2",
    "Caixa JBL Charge 5",
    "Câmera GoPro Hero 12",
    "Aspirador Robô Roomba j7+",
    "Air Fryer Philips Walita XXL",
]

CATEGORIAS = [
    "eletronicos",
    "informatica",
    "celulares",
    "perifericos",
    "moveis",
    "audio",
    "games",
    "livros",
    "casa",
]

LOJAS = [
    "Amazon",
    "Magazine Luiza",
    "Casas Bahia",
    "Mercado Livre",
    "Kabum",
    "Americanas",
    "Ponto",
    "AliExpress",
    "Shopee",
]

console = Console()


def gerar_promocao() -> PromoPayload:
    """Gera uma promoção aleatória."""
    return PromoPayload(
        id_promocao=str(uuid.uuid4()),
        nome_produto=random.choice(PRODUTOS),
        categoria=random.choice(CATEGORIAS),
        preco=round(random.uniform(29.90, 9999.90), 2),
        loja=random.choice(LOJAS),
    )


def main():
    parser = argparse.ArgumentParser(
        description="🔥 Teste de carga — publica promoções e votos diretamente no RabbitMQ."
    )
    parser.add_argument(
        "-p",
        "--promocoes",
        type=int,
        default=10,
        help="Quantidade de promoções a publicar (padrão: 10)",
    )
    parser.add_argument(
        "-v",
        "--votos",
        type=int,
        default=30,
        help="Quantidade total de votos aleatórios a publicar (padrão: 30)",
    )
    parser.add_argument(
        "-d",
        "--delay",
        type=float,
        default=0.0,
        help="Delay entre publicações em segundos (padrão: 0.0 — sem delay)",
    )
    parser.add_argument(
        "-w",
        "--wait",
        type=float,
        default=5.0,
        help="Segundos de espera entre promoções e votos para o MS Promoção validar (padrão: 5.0)",
    )
    args = parser.parse_args()

    num_promo = args.promocoes
    num_votos = args.votos
    delay = args.delay
    wait_between = args.wait

    # ── Header ──────────────────────────────────────────────────────────────
    title = Text()
    title.append("⚡", style="bold white")
    title.append("  |  ", style="dim white")
    title.append("Load Test", style="bold red")
    title.append(f"  |  {num_promo} promoções  •  {num_votos} votos", style="dim yellow")
    console.print(Panel(title, style="red", padding=(0, 2)))
    console.print()

    # ── Carregar chave privada do Gateway ────────────────────────────────────
    try:
        gateway_private_key, _ = CryptoService.load_or_generate_keys("ms_gateway")
    except Exception as e:
        console.print(f"[red]Erro ao carregar chaves do Gateway:[/red] {e}")
        console.print("[yellow]Dica: rode o MS Gateway pelo menos uma vez antes.[/yellow]")
        sys.exit(1)

    # ── Conectar ao RabbitMQ ─────────────────────────────────────────────────
    try:
        rabbitmq = RabbitMQClient()
    except Exception as e:
        console.print(f"[red]Erro ao conectar no RabbitMQ:[/red] {e}")
        console.print("[yellow]Dica: suba o RabbitMQ com 'docker compose up -d'.[/yellow]")
        sys.exit(1)

    console.print("[green]✔[/green] Conectado ao RabbitMQ\n")

    # ── Fase 1: Publicar promoções ──────────────────────────────────────────
    ids_publicados: list[str] = []
    nomes_publicados: dict[str, str] = {}  # id -> nome_produto

    with Progress(
        SpinnerColumn(style="red"),
        TextColumn("[bold white]{task.description}"),
        BarColumn(bar_width=40, complete_style="red", finished_style="green"),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_promo = progress.add_task("Publicando promoções...", total=num_promo)

        for _ in range(num_promo):
            promo = gerar_promocao()
            ids_publicados.append(promo.id_promocao)
            nomes_publicados[promo.id_promocao] = promo.nome_produto

            envelope = EventEnvelope(
                routing_key="promocao.recebida",
                payload=promo.model_dump(),
            )
            rabbitmq.publish_signed_event(envelope, gateway_private_key)

            progress.advance(task_promo)
            if delay > 0:
                time.sleep(delay)

    console.print(f"[green]✔ {num_promo} promoções publicadas com sucesso![/green]\n")

    # ── Espera: dar tempo ao MS Promoção validar ─────────────────────────────
    if num_votos > 0 and ids_publicados and wait_between > 0:
        console.print(
            f"[dim]⏳ Aguardando {wait_between:.0f}s para o MS Promoção validar as "
            f"promoções antes de enviar os votos...[/dim]"
        )
        with Progress(
            SpinnerColumn(style="cyan"),
            TextColumn("[bold white]{task.description}"),
            BarColumn(bar_width=40, complete_style="cyan", finished_style="green"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            wait_task = progress.add_task("Aguardando validação...", total=int(wait_between * 10))
            for _ in range(int(wait_between * 10)):
                time.sleep(0.1)
                progress.advance(wait_task)
        console.print()

    # ── Fase 2: Publicar votos aleatórios ────────────────────────────────────
    if num_votos > 0 and ids_publicados:
        votos_positivos = 0
        votos_negativos = 0

        with Progress(
            SpinnerColumn(style="yellow"),
            TextColumn("[bold white]{task.description}"),
            BarColumn(bar_width=40, complete_style="yellow", finished_style="green"),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task_votos = progress.add_task("Publicando votos...", total=num_votos)

            for _ in range(num_votos):
                id_alvo = random.choice(ids_publicados)
                nome_alvo = nomes_publicados.get(id_alvo, "?")
                voto = random.choice([1, 1, 1, -1])  # 75% positivo, 25% negativo

                voto_payload = VotoPayload(id_promocao=id_alvo, nome_produto=nome_alvo, voto=voto)
                envelope = EventEnvelope(
                    routing_key="promocao.voto", payload=voto_payload.model_dump()
                )
                rabbitmq.publish_signed_event(envelope, gateway_private_key)

                if voto > 0:
                    votos_positivos += 1
                else:
                    votos_negativos += 1

                progress.advance(task_votos)
                if delay > 0:
                    time.sleep(delay)

        console.print(f"[green]✔ {num_votos} votos publicados![/green]")
        console.print(
            f"  [dim]👍 Positivos: {votos_positivos}  |  👎 Negativos: {votos_negativos}[/dim]\n"
        )

    # ── Resumo final ─────────────────────────────────────────────────────────
    rabbitmq.close()

    table = Table(
        box=box.ROUNDED,
        style="green",
        header_style="bold green",
        title="[bold]📊 Resumo do Teste de Carga[/bold]",
        show_lines=True,
    )
    table.add_column("Métrica", style="white")
    table.add_column("Valor", style="bold cyan", justify="right")

    table.add_row("Promoções publicadas", str(num_promo))
    table.add_row("Votos publicados", str(num_votos))
    table.add_row(
        "Votos por promoção (média)",
        f"{num_votos / num_promo:.1f}" if num_promo > 0 else "0",
    )
    table.add_row(
        "Limite Hot Deal (MS Ranking)",
        "3 votos positivos líquidos",
    )
    table.add_row("IDs de promoção gerados", str(len(ids_publicados)))

    console.print(table)
    console.print(
        "\n[dim]Dica: acompanhe os dashboards do MS Promoção, MS Ranking e MS Notificação "
        "em terminais separados para ver o sistema processando a carga.[/dim]\n"
    )


if __name__ == "__main__":
    main()
