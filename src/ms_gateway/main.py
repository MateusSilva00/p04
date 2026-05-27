import os
import threading
import uuid

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from src.core.models import EventEnvelope, PromoPayload, VotoPayload
from src.core.rabbitmq import RabbitMQClient
from src.core.security import CryptoService
from src.utils.utils import cls

console = Console()
approved_promotions: dict = {}
last_notification: dict = {}
approval_event = threading.Event()


def print_header():
    title = Text()
    title.append("🏷️", style="bold white")
    title.append("  |  ", style="dim white")
    title.append("MS Gateway", style="bold cyan")
    console.print(Panel(title, style="cyan", padding=(0, 2)))


def print_menu():
    menu = Text()
    menu.append("  [1]", style="bold yellow")
    menu.append("  Cadastrar nova promoção\n", style="white")
    menu.append("  [2]", style="bold yellow")
    menu.append("  Listar promoções e votar\n", style="white")
    menu.append("  [0]", style="bold red")
    menu.append("  Sair", style="white")
    console.print(Panel(menu, title="[bold]Menu[/bold]", style="dim white", padding=(0, 2)))


def render_menu():
    cls()
    print_header()
    print_menu()


def print_promotions_table():
    if not approved_promotions:
        console.print(
            Panel("[yellow]Nenhuma promoção aprovada no momento.[/yellow]", style="yellow")
        )
        return False

    table = Table(
        box=box.ROUNDED,
        style="cyan",
        header_style="bold cyan",
        show_lines=True,
        title="[bold]Promoções Ativas[/bold]",
    )
    table.add_column("#", style="bold yellow", justify="center", width=4)
    table.add_column("Produto", style="white")
    table.add_column("Preço", style="bold green", justify="right")
    table.add_column("Loja", style="dim white")
    table.add_column("Categoria", style="cyan", justify="center")

    for idx, pid in enumerate(approved_promotions):
        p = approved_promotions[pid]
        table.add_row(
            str(idx),
            p["nome_produto"],
            f"R$ {p['preco']:.2f}",
            p["loja"],
            p.get("categoria", "-"),
        )

    console.print(table)
    return True


def init_background_consumer(public_key_promocao):
    try:
        rabbitmq_consumer = RabbitMQClient()
    except Exception as e:
        console.print(f"[red][Aviso] Falha ao iniciar consumidor de background: {e}[/red]")
        return

    def process_published_promotions(envelope: EventEnvelope):
        payload = envelope.payload
        approved_promotions[payload["id_promocao"]] = payload
        last_notification.clear()
        last_notification.update(payload)
        approval_event.set()  # Sinaliza a thread principal

    rabbitmq_consumer.setup_consumer(
        queue_name="Fila_Gateway",
        routing_keys=["promocao.publicada"],
        public_key_pem=public_key_promocao,
        callback=process_published_promotions,
    )


def main():
    cls()
    print_header()
    console.print("[dim]Iniciando MS Gateway...[/dim]\n")

    private_key, _ = CryptoService.load_or_generate_keys("ms_gateway")

    keys_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../keys"))
    promocao_pub_path = os.path.join(keys_dir, "ms_promocao_public.pem")

    if not os.path.exists(promocao_pub_path):
        console.print(
            Panel(
                "[red]Chave pública do MS Promoção não encontrada em:[/red]\n"
                f"[dim]{promocao_pub_path}[/dim]\n\n"
                "[yellow]Rode o MS Promoção pelo menos uma vez para gerar suas chaves.[/yellow]",
                title="[red]❌ Erro de Configuração[/red]",
                style="red",
            )
        )
        return

    with open(promocao_pub_path, "rb") as f:
        promocao_public_key = f.read()

    try:
        rabbitmq_publisher = RabbitMQClient()
    except Exception as e:
        console.print(f"[red]Erro ao conectar no RabbitMQ: {e}[/red]")
        return

    thread_consumidor = threading.Thread(
        target=init_background_consumer, args=(promocao_public_key,), daemon=True
    )
    thread_consumidor.start()
    console.print("[dim]✔ Consumidor de aprovações iniciado em background.[/dim]")

    input("\nPressione Enter para abrir o menu...")
    render_menu()

    while True:
        opcao = Prompt.ask(
            "[bold yellow]Escolha uma opção[/bold yellow]",
            choices=["0", "1", "2"],
            show_choices=False,
        )

        if opcao == "0":
            cls()
            console.print("[dim]Encerrando Gateway. Até logo![/dim]")
            break

        elif opcao == "1":
            cls()
            print_header()
            console.print(Panel("[bold]Cadastro de Nova Promoção[/bold]", style="cyan"))

            nome = Prompt.ask("  [cyan]Nome do produto[/cyan]")
            categoria = Prompt.ask("  [cyan]Categoria[/cyan]")
            preco_str = Prompt.ask("  [cyan]Preço[/cyan]")
            try:
                preco = float(preco_str.replace(",", "."))
            except ValueError:
                console.print("[red]Preço inválido. Operação cancelada.[/red]")
                input("\nPressione Enter para voltar ao menu...")
                render_menu()
                continue
            loja = Prompt.ask("  [cyan]Loja[/cyan]")

            payload = PromoPayload(
                id_promocao=str(uuid.uuid4()),
                nome_produto=nome,
                categoria=categoria,
                preco=preco,
                loja=loja,
            )

            envelope = EventEnvelope(
                routing_key="promocao.recebida",
                payload=payload.model_dump(),
                signature=None,
            )

            approval_event.clear()
            rabbitmq_publisher.publish_signed_event(envelope, private_key)

            console.print("\n[dim]⏳ Aguardando confirmação do MS Promoção (timeout: 15s)...[/dim]")
            aprovado = approval_event.wait(timeout=15)

            if aprovado and last_notification:
                p = last_notification
                console.print(
                    Panel(
                        f"[bold white]Produto:[/bold white]   {p.get('nome_produto')}\n"
                        f"[bold white]Preço:[/bold white]     R$ {float(p.get('preco', 0)):.2f}\n"
                        f"[bold white]Loja:[/bold white]      {p.get('loja')}\n"
                        f"[bold white]Categoria:[/bold white] {p.get('categoria')}",
                        title="[bold green]✅ Promoção Aprovada e Publicada![/bold green]",
                        style="green",
                    )
                )
            else:
                console.print(
                    Panel(
                        "[yellow]MS Promoção não respondeu a tempo.\n"
                        "Verifique se o serviço está rodando.[/yellow]",
                        title="[yellow]⚠ Timeout[/yellow]",
                        style="yellow",
                    )
                )

            input("\nPressione Enter para voltar ao menu...")
            render_menu()

        elif opcao == "2":
            cls()
            print_header()
            has_promos = print_promotions_table()

            if not has_promos:
                input("\nPressione Enter para voltar...")
                render_menu()
                continue

            lista_ids = list(approved_promotions.keys())
            escolha = Prompt.ask(
                "\n  [yellow]Número da promoção para votar[/yellow] ([red]v[/red] para voltar)"
            )

            if escolha.lower() == "v":
                render_menu()
                continue

            if escolha.isdigit() and int(escolha) < len(lista_ids):
                id_escolhido = lista_ids[int(escolha)]
                nome_escolhido = approved_promotions[id_escolhido]["nome_produto"]
                console.print(f"\n  Votando em: [bold white]{nome_escolhido}[/bold white]")

                voto_str = Prompt.ask(
                    "  [cyan]Voto[/cyan]",
                    choices=["1", "-1"],
                    show_choices=True,
                )
                voto_payload = VotoPayload(
                    id_promocao=id_escolhido,
                    nome_produto=nome_escolhido,
                    voto=int(voto_str),
                )

                envelope_voto = EventEnvelope(
                    routing_key="promocao.voto",
                    payload=voto_payload.model_dump(),
                    signature=None,
                )
                rabbitmq_publisher.publish_signed_event(envelope_voto, private_key)

                icone = "👍" if int(voto_str) == 1 else "👎"
                console.print(f"\n[bold green]{icone} Voto registrado e enviado![/bold green]")
            else:
                console.print("[red]Opção inválida.[/red]")

            input("\nPressione Enter para voltar ao menu...")
            render_menu()

    rabbitmq_publisher.close()


if __name__ == "__main__":
    main()
