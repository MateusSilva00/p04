from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from src.core.models import EventEnvelope
from src.core.rabbitmq import RabbitMQClient
from src.utils.utils import cls

console = Console()

notification_history: list = []


def render(nome_cliente: str, interesses: list[str]):
    """Limpa o terminal e re-renderiza o dashboard completo."""
    cls()

    title = Text()
    title.append("👤", style="bold white")
    title.append("  |  ", style="dim white")
    title.append(f"Cliente: {nome_cliente}", style="bold green")
    categorias_str = "  ".join(f"[cyan]{i}[/cyan]" for i in interesses)
    console.print(
        Panel(
            f"{title}\n[dim]Categorias:[/dim] {categorias_str}",
            style="green",
            padding=(0, 2),
        )
    )

    if notification_history:
        table = Table(
            box=box.ROUNDED,
            style="green",
            header_style="bold green",
            title=f"[bold]Notificações Recebidas ({len(notification_history)})[/bold]",
            show_lines=True,
        )
        table.add_column("Tipo", justify="center", width=12)
        table.add_column("Produto", style="white")
        table.add_column("Preço", style="bold green", justify="right")
        table.add_column("Loja", style="dim white")
        table.add_column("Canal", style="cyan", justify="center")

        for n in notification_history:
            table.add_row(
                n["tipo"],
                n["produto"],
                n["preco"],
                n["loja"],
                n["canal"],
            )

        console.print(table)
    else:
        console.print("[dim]Aguardando notificações...[/dim]\n")


def main():
    console.clear()

    title = Text()
    title.append("👤", style="bold white")
    title.append("  |  ", style="dim white")
    title.append("Terminal do Cliente", style="bold green")
    console.print(Panel(title, style="green", padding=(0, 2)))

    nome_cliente = Prompt.ask("[bold green]Nome do cliente[/bold green]").strip().replace(" ", "_")
    if not nome_cliente:
        nome_cliente = "Cliente"

    console.print(
        "\n[dim]Sugestões:[/dim] [cyan]livro[/cyan]  "
        "[cyan]jogo[/cyan]  [cyan]eletronico[/cyan]  "
        "[cyan]destaque[/cyan]"
    )
    interesses_input = Prompt.ask(
        "[bold green]Categorias de interesse[/bold green] (separadas por vírgula)"
    )
    interesses = [i.strip().lower() for i in interesses_input.split(",") if i.strip()]

    if not interesses:
        console.print(
            Panel(
                "[yellow]Nenhum interesse fornecido. Encerrando.[/yellow]",
                style="yellow",
            )
        )
        return

    routing_keys = [f"promocao.{interesse}" for interesse in interesses]

    try:
        rabbitmq = RabbitMQClient()
    except Exception as e:
        console.print(Panel(f"[red]Erro ao conectar no RabbitMQ:[/red] {e}", style="red"))
        return

    render(nome_cliente, interesses)

    def processar_notificacao(envelope: EventEnvelope):
        payload = envelope.payload
        categoria_rk = envelope.routing_key

        if "score" in payload and "nome_produto" not in payload:
            notification_history.append(
                {
                    "tipo": "[bold yellow]🔥 Destaque[/bold yellow]",
                    "produto": f"ID: {payload['id_promocao'][:8]}...",
                    "preco": f"Score: {payload['score']}",
                    "loja": "-",
                    "canal": categoria_rk,
                }
            )
        elif payload.get("aviso") == "hot deal":
            notification_history.append(
                {
                    "tipo": "[bold yellow]🔥 Hot Deal[/bold yellow]",
                    "produto": payload["nome_produto"],
                    "preco": f"R$ {payload['preco']:.2f}",
                    "loja": payload["loja"],
                    "canal": categoria_rk,
                }
            )
        else:
            notification_history.append(
                {
                    "tipo": "[green]🏷️ Promoção[/green]",
                    "produto": payload["nome_produto"],
                    "preco": f"R$ {payload['preco']:.2f}",
                    "loja": payload["loja"],
                    "canal": categoria_rk,
                }
            )

        render(nome_cliente, interesses)

    nome_fila = f"Fila_{nome_cliente}"
    rabbitmq.setup_unsigned_consumer(
        queue_name=nome_fila, routing_keys=routing_keys, callback=processar_notificacao
    )


if __name__ == "__main__":
    main()
