import os

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

LIMIT_HOT_DEAL = 3
local_score: dict[str, dict] = {}
vote_log: list = []


def render():
    """Limpa o terminal e re-renderiza o dashboard completo."""
    cls()

    # Cabeçalho
    title = Text()
    title.append("🏆", style="bold white")
    title.append("  |  ", style="dim white")
    title.append("MS Ranking", style="bold yellow")
    title.append(f"  |  Limite Hot Deal: {LIMIT_HOT_DEAL} votos", style="dim yellow")
    console.print(Panel(title, style="yellow", padding=(0, 2)))

    # Placar atual
    if local_score:
        table = Table(
            box=box.ROUNDED,
            style="yellow",
            header_style="bold yellow",
            title="[bold]Placar de Promoções[/bold]",
            show_lines=True,
        )
        table.add_column("Nome", style="dim white", width=12)
        table.add_column("Progresso", min_width=20)
        table.add_column("Score", justify="center", width=8)
        table.add_column("Status", justify="center")

        for pid, info in local_score.items():
            nome = info["nome"]
            score = info["score"]

            if score >= LIMIT_HOT_DEAL:
                progresso = f"[green]{'█' * LIMIT_HOT_DEAL}[/green]"
                score_str = f"[green]{LIMIT_HOT_DEAL}+[/green]"
                status = "[bold green]🔥 HOT DEAL[/bold green]"
            elif score > 0:
                cheios = min(score, LIMIT_HOT_DEAL)
                vazios = max(0, LIMIT_HOT_DEAL - cheios)
                progresso = f"[yellow]{'█' * cheios}[/yellow][dim]{'░' * vazios}[/dim]"
                score_str = f"[yellow]{score}[/yellow]"
                status = "[yellow]⏳ Em votação[/yellow]"
            else:
                progresso = (
                    f"[red]{'█' * abs(min(score, 0))}[/red][dim]{'░' * LIMIT_HOT_DEAL}[/dim]"
                    if score < 0
                    else f"[dim]{'░' * LIMIT_HOT_DEAL}[/dim]"
                )
                score_str = f"[red]{score}[/red]"
                status = "[red]👎 Negativo[/red]"

            table.add_row(nome, progresso, score_str, status)

        console.print(table)
    else:
        console.print("[dim]Nenhum voto recebido ainda.[/dim]\n")

    # Log dos últimos votos
    if vote_log:
        console.print(Rule("[dim]Log de Votos[/dim]", style="dim yellow"))
        for entrada in vote_log[-10:]:
            console.print(entrada)


def main():
    render()

    ranking_private_key, _ = CryptoService.load_or_generate_keys("ms_ranking")

    keys_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../keys"))
    gateway_pub_path = os.path.join(keys_dir, "ms_gateway_public.pem")

    if not os.path.exists(gateway_pub_path):
        console.print(
            Panel(
                f"[red]Chave pública do Gateway não encontrada em:[/red]\n[dim]{gateway_pub_path}[/dim]",
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
        console.print(
            Panel(f"[red]Erro ao conectar no RabbitMQ:[/red] {e}", style="red")
        )
        return

    def process_vote(envelope: EventEnvelope):
        payload = envelope.payload
        id_promotion = payload["id_promocao"]
        voto = payload["voto"]
        nome = payload.get("nome_produto", "?")

        entry = local_score.get(id_promotion, {"nome": nome, "score": 0})
        # Atualiza o nome caso ainda não tenha sido preenchido
        if entry["nome"] == "?":
            entry["nome"] = nome

        pontuacao_atual = entry["score"]
        if pontuacao_atual >= LIMIT_HOT_DEAL:
            vote_log.append(f"  [dim]↩ Voto ignorado: {nome}... já é Hot Deal.[/dim]")
            render()
            return

        new_score = pontuacao_atual + voto
        entry["score"] = new_score
        local_score[id_promotion] = entry

        icone = "👍" if voto > 0 else "👎"
        cor = "green" if voto > 0 else "red"
        vote_log.append(
            f"  {icone} [{cor}]Voto {'+1' if voto > 0 else '-1'}[/{cor}] em "
            f"[white]{nome}[/white] → Score: [bold]{new_score}[/bold]"
        )

        if new_score >= LIMIT_HOT_DEAL:
            vote_log.append(
                f"  [bold yellow]🔥 HOT DEAL:[/bold yellow] [white]{nome}[/white] "
                f"atingiu [bold green]{new_score}[/bold green] votos! Publicando destaque..."
            )
            novo_envelope = EventEnvelope(
                routing_key="promocao.destaque",
                payload={"id_promocao": id_promotion, "score": new_score},
                signature=b"",
            )
            rabbitmq.publish_signed_event(novo_envelope, ranking_private_key)

        render()

    rabbitmq.setup_consumer(
        queue_name="Fila_Ranking",
        routing_keys=["promocao.voto"],
        public_key_pem=gateway_public_key,
        callback=process_vote,
    )


if __name__ == "__main__":
    main()
