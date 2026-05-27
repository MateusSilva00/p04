import os
import time

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from src.core.models import EventEnvelope
from src.core.rabbitmq import RabbitMQClient
from src.core.security import CryptoService
from src.utils.utils import cls

console = Console()

processed: list = []  # Histórico de promoções processadas


def render():
    """Limpa o terminal e re-renderiza o dashboard completo."""
    cls()

    title = Text()
    title.append("📋", style="bold white")
    title.append("  |  ", style="dim white")
    title.append("MS Promoção", style="bold magenta")
    console.print(Panel(title, style="magenta", padding=(0, 2)))

    if processed:
        table = Table(
            box=box.ROUNDED,
            style="magenta",
            header_style="bold magenta",
            title=f"[bold]Promoções Processadas ({len(processed)})[/bold]",
            show_lines=True,
        )
        table.add_column("#", style="dim white", justify="center", width=4)
        table.add_column("Produto", style="white")
        table.add_column("Preço", style="bold green", justify="right")
        table.add_column("Loja", style="dim white")
        table.add_column("Categoria", style="cyan", justify="center")
        table.add_column("Status", justify="center")

        for i, p in enumerate(processed):
            table.add_row(
                str(i + 1),
                p["nome_produto"],
                f"R$ {p['preco']:.2f}",
                p["loja"],
                p.get("categoria", "-"),
                "[bold green]✅ Publicada[/bold green]",
            )

        console.print(table)
    else:
        console.print("[dim]Aguardando promoções para validar...[/dim]\n")


def main():
    render()

    promocao_private_key, _ = CryptoService.load_or_generate_keys("ms_promocao")

    keys_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../keys"))
    gateway_pub_path = os.path.join(keys_dir, "ms_gateway_public.pem")

    if not os.path.exists(gateway_pub_path):
        console.print(
            Panel(
                "[red]Chave pública do Gateway não encontrada em:[/red]\n"
                f"[dim]{gateway_pub_path}[/dim]\n\n"
                "[yellow]Rode o MS Gateway pelo menos uma vez para gerar suas chaves.[/yellow]",
                title="[red]❌ Erro de Configuração[/red]",
                style="red",
            )
        )
        return

    with open(gateway_pub_path, "rb") as f:
        gateway_public_key = f.read()

    try:
        rabbitmq = RabbitMQClient()
    except Exception as e:
        console.print(Panel(f"[red]Erro ao conectar no RabbitMQ:[/red] {e}", style="red"))
        return

    def processar_promocao_recebida(envelope: EventEnvelope):
        payload = envelope.payload

        console.print(
            Rule(
                "[dim magenta]Validando nova promoção...[/dim magenta]",
                style="dim magenta",
            )
        )
        time.sleep(1)

        novo_envelope = EventEnvelope(
            routing_key="promocao.publicada", payload=payload, signature=None
        )
        rabbitmq.publish_signed_event(novo_envelope, promocao_private_key)

        processed.append(payload)
        render()

    rabbitmq.setup_consumer(
        queue_name="Fila_Promocao",
        routing_keys=["promocao.recebida"],
        public_key_pem=gateway_public_key,
        callback=processar_promocao_recebida,
    )


if __name__ == "__main__":
    main()
