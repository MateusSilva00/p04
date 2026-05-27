import os
import threading

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from src.core.models import EventEnvelope
from src.core.rabbitmq import RabbitMQClient
from src.utils.utils import cls

console = Console()

known_promotions: dict = {}
event_log: list = []
render_lock = threading.Lock()


def render():
    """Limpa o terminal e re-renderiza o dashboard completo."""
    with render_lock:
        cls()

        title = Text()
        title.append("🔔", style="bold white")
        title.append("  |  ", style="dim white")
        title.append("MS Notificação", style="bold blue")
        console.print(Panel(title, style="blue", padding=(0, 2)))

        # Tabela de promoções conhecidas
        if known_promotions:
            table = Table(
                box=box.ROUNDED,
                style="blue",
                header_style="bold blue",
                title=f"[bold]Catálogo Conhecido ({len(known_promotions)} promoções)[/bold]",
                show_lines=True,
            )
            table.add_column("Produto", style="white")
            table.add_column("Categoria", style="cyan", justify="center")
            table.add_column("Preço", style="bold green", justify="right")

            for _, p in known_promotions.items():
                table.add_row(
                    p.get("nome_produto", "?"),
                    p.get("categoria", "?"),
                    f"R$ {p.get('preco', 0):.2f}",
                )
            console.print(table)
        else:
            console.print("[dim]Aguardando promoções publicadas...[/dim]\n")

        # Log de roteamentos
        if event_log:
            console.print(Rule("[dim]Log de Roteamentos[/dim]", style="dim blue"))
            for entrada in event_log[-10:]:
                console.print(entrada)


def init_consumers(public_key_promotion, public_key_ranking):
    try:
        rabbitmq = RabbitMQClient()
    except Exception as e:
        console.print(Panel(f"[red]Erro RabbitMQ:[/red] {e}", style="red"))
        return

    def process_published(envelope: EventEnvelope):
        payload = envelope.payload
        id_promotion = payload["id_promocao"]
        category = payload["categoria"].lower()
        nome = payload.get("nome_produto", "?")

        known_promotions[id_promotion] = payload

        new_envelope = EventEnvelope(
            routing_key=f"promocao.{category}", payload=payload, signature=b""
        )
        rabbitmq.publish_unsigned_event(new_envelope)

        event_log.append(
            f"  [blue]📢[/blue] [white]{nome}[/white] → [cyan]promocao.{category}[/cyan]"
        )
        render()

    def processar_destaque(envelope: EventEnvelope):
        payload = envelope.payload
        id_promotion = payload["id_promocao"]
        score = payload.get("score", "?")

        if id_promotion in known_promotions:
            dados_originais = known_promotions[id_promotion]
            category = dados_originais["categoria"].lower()
            nome = dados_originais.get("nome_produto", "?")

            payload_destaque = dados_originais.copy()
            payload_destaque["aviso"] = "hot deal"

            new_envelope = EventEnvelope(
                routing_key=f"promocao.{category}",
                payload=payload_destaque,
                signature=b"",
            )
            rabbitmq.publish_unsigned_event(new_envelope)

            event_log.append(
                f"  [yellow]🔥 HOT DEAL:[/yellow] [white]{nome}[/white] (score {score}) "
                f"→ [cyan]promocao.{category}[/cyan]"
            )
        else:
            event_log.append(
                "  [yellow]⚠[/yellow] Hot Deal para promoção desconhecida: "
                f"[dim]{id_promotion[:10]}...[/dim]"
            )

        render()

    rabbitmq.setup_multi_consumer(
        queue_name="Fila_Notificacao",
        handlers={
            "promocao.publicada": (public_key_promotion, process_published),
            "promocao.destaque": (public_key_ranking, processar_destaque),
        },
    )


def main():
    render()

    keys_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../keys"))
    promocao_pub_path = os.path.join(keys_dir, "ms_promocao_public.pem")
    ranking_pub_path = os.path.join(keys_dir, "ms_ranking_public.pem")

    if not os.path.exists(promocao_pub_path) or not os.path.exists(ranking_pub_path):
        console.print(
            Panel(
                "[red]Chaves públicas de Promoção ou Ranking não encontradas.[/red]\n"
                "[yellow]Rode todos os serviços pelo menos uma vez.[/yellow]",
                title="[red]❌ Erro de Configuração[/red]",
                style="red",
            )
        )
        return

    with open(promocao_pub_path, "rb") as f:
        promocao_public_key = f.read()

    with open(ranking_pub_path, "rb") as f:
        ranking_public_key = f.read()

    thread = threading.Thread(
        target=init_consumers,
        args=(promocao_public_key, ranking_public_key),
        daemon=True,
    )
    thread.start()

    try:
        while thread.is_alive():
            thread.join(timeout=0.5)
    except KeyboardInterrupt:
        console.print("\n[dim]Encerrando MS Notificação...[/dim]")


if __name__ == "__main__":
    main()
