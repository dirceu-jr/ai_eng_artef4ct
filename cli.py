"""Interface de Linha de Comando (CLI) interativa com Rich para o agente da Empório da Música."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from src.agent import EmporioMusicaAgent
from src.config import GEMINI_MODEL

console = Console()


def _print_banner(session_id: str, model_name: str) -> None:
    banner_md = (
        "**EMPÓRIO DA MÚSICA** — *Sua música começa aqui.*\n\n"
        f"- **Sessão ativa**: `{session_id}` | **Modelo**: `{model_name}`\n"
        "- Comandos: `/ajuda`, `/limpar`, `/exportar [arquivo.md]`, `/sair`"
    )
    console.print(Panel(Markdown(banner_md), title="🎸 Atendimento Virtual", border_style="cyan"))


def _print_help() -> None:
    table = Table(title="Comandos e Sugestões de Teste", border_style="blue")
    table.add_column("Comando / Pergunta", style="cyan", no_wrap=False)
    table.add_column("Descrição", style="white")
    table.add_row("/ajuda", "Exibe esta tabela de ajuda")
    table.add_row("/limpar", "Limpa o histórico da sessão atual")
    table.add_row("/exportar [caminho.md]", "Exporta a conversa atual em formato Markdown")
    table.add_row("/sair", "Encerra o atendimento")
    table.add_row(
        "Quais opções de violões disponíveis custando até R$1000?",
        "Consulta catálogo filtrando o Giannini GF-3D sem estoque",
    )
    table.add_row(
        "Quanto custa o Takamine GD20? Ainda tem promoção?",
        "Verifica preço, promoção expirada (12%) e desconto no PIX",
    )
    table.add_row(
        "Me arrependi da compra do pedido 8 (ou pedido 7), posso devolver?",
        "Cruza orders.csv com regras de 7 dias / 30 dias",
    )
    table.add_row(
        "Vocês vendem encordoamento de aço e amplificador?",
        "Testa guardrail de escopo (apenas instrumentos musicais)",
    )
    console.print(table)


def _render_turn(turn_text: str, tool_calls: list[dict]) -> None:
    if tool_calls:
        tc_lines = []
        for tc in tool_calls:
            args_str = json.dumps(tc.get("args", {}), ensure_ascii=False)
            tc_lines.append(f"• `{tc['name']}({args_str})` ({tc.get('duration_ms', 0)} ms)")
        console.print(
            Panel(
                "\n".join(tc_lines),
                title=f"🔧 Tools Acionadas ({len(tool_calls)})",
                border_style="dim yellow",
            )
        )
    console.print(
        Panel(
            Markdown(turn_text),
            title="🎸 Assistente Empório da Música",
            border_style="green",
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI de Atendimento — Empório da Música")
    parser.add_argument("--session", default="cli_default", help="ID da sessão de conversa")
    parser.add_argument("--model", default=GEMINI_MODEL, help="Modelo Gemini a utilizar")
    parser.add_argument("--message", "-m", help="Envia uma única mensagem e encerra")
    parser.add_argument("--export", help="Caminho para exportar a sessão em Markdown")
    args = parser.parse_args()

    agent = EmporioMusicaAgent(model=args.model)

    if args.message:
        try:
            turn = agent.chat(args.message, session_id=args.session)
            _render_turn(turn.text, turn.tool_calls)
            if args.export:
                Path(args.export).write_text(
                    agent.memory.export_session_markdown(args.session),
                    encoding="utf-8",
                )
        except Exception as exc:
            console.print(f"[bold red]Erro:[/bold red] {exc}")
            sys.exit(1)
        return

    _print_banner(session_id=args.session, model_name=args.model)

    while True:
        try:
            user_input = console.input("\n[bold cyan]👤 Você:[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Encerrando atendimento. Até logo![/yellow]")
            break

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in ("/sair", "sair", "exit", "quit"):
            console.print("[yellow]Obrigado por visitar a Empório da Música! Até a próxima![/yellow]")
            break
        if cmd == "/ajuda":
            _print_help()
            continue
        if cmd == "/limpar":
            agent.memory.clear_session(args.session)
            console.print("[green]Histórico da sessão limpo com sucesso![/green]")
            continue
        if cmd.startswith("/exportar"):
            parts = user_input.split(maxsplit=1)
            out_path = Path(parts[1]) if len(parts) > 1 else Path(f"conversa_{args.session}.md")
            md_content = agent.memory.export_session_markdown(args.session)
            out_path.write_text(md_content, encoding="utf-8")
            console.print(f"[green]Conversa exportada para:[/green] `{out_path}`")
            continue

        try:
            with console.status("[bold green]Consultando sistema da Empório da Música...[/bold green]"):
                turn = agent.chat(user_input, session_id=args.session)
            _render_turn(turn.text, turn.tool_calls)
        except Exception as exc:
            console.print(Panel(str(exc), title="Erro na execução", border_style="red"))


if __name__ == "__main__":
    main()

