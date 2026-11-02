"""Testes unitários do orquestrador do agente, memória SQLite e ciclo de Function Calling."""

from pathlib import Path
from types import SimpleNamespace

from src.agent import EmporioMusicaAgent
from src.memory import ConversationMemory


class FakeModelsAPI:
    """Simula o cliente `google-genai` em 2 etapas: 1) solicita tool call; 2) responde ao usuário."""

    def __init__(self) -> None:
        self.calls = 0

    def generate_content(self, model: str, contents: list, config: object) -> object:
        self.calls += 1
        fake_usage = SimpleNamespace(
            prompt_token_count=1200,
            candidates_token_count=150,
            thoughts_token_count=50,
            cached_content_token_count=0,
            total_token_count=1400,
        )
        if self.calls == 1:
            fc = SimpleNamespace(name="tool_obter_detalhes_produto", args={"produto_id_ou_nome": "Takamine GD20"})
            return SimpleNamespace(
                function_calls=[fc],
                candidates=[SimpleNamespace(content=contents[-1])],
                text=None,
                usage_metadata=fake_usage,
            )
        return SimpleNamespace(
            function_calls=[],
            candidates=[],
            text="O Takamine GD20 custa R$ 2.199,00 na tabela (ou R$ 2.089,05 no PIX com 5% de desconto) e temos 5 unidades em estoque!",
            usage_metadata=fake_usage,
        )


def test_agent_tool_calling_loop_and_memory_persistence(tmp_path: Path) -> None:
    mem_db = tmp_path / "test_memory.db"
    memory = ConversationMemory(db_path=mem_db)
    fake_client = SimpleNamespace(models=FakeModelsAPI())

    agent = EmporioMusicaAgent(
        api_key="fake-key",
        model="gemini-3.8-flash",
        memory=memory,
        client=fake_client,
    )

    turn = agent.chat("Quanto custa o Takamine GD20?", session_id="sessao_teste")
    assert "2.199,00" in turn.text
    assert turn.model_used == "gemini-3.8-flash"
    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0]["name"] == "tool_obter_detalhes_produto"
    assert turn.tool_calls[0]["result"]["product"]["product_id"] == 95
    assert turn.usage["llm_calls"] == 2
    assert turn.usage["prompt_tokens"] == 2400
    assert turn.usage["output_tokens"] == 300
    assert turn.usage["thoughts_tokens"] == 100
    assert turn.usage["total_tokens"] == 2800
    assert turn.usage["estimated_cost_usd"] > 0
    assert turn.usage["estimated_cost_brl"] > 0

    # Verifica persistência no banco e exportação Markdown
    history = memory.get_messages("sessao_teste")
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    assert len(history[1]["tool_calls"]) == 1

    md = memory.export_session_markdown("sessao_teste", scenario_title="Teste Takamine")
    assert "# Teste Takamine" in md
    assert "tool_obter_detalhes_produto" in md


def test_escape_streamlit_markdown_currency() -> None:
    from app import escape_streamlit_markdown

    raw = "De R$ 2.399,00 por R$ 1.967,18 (já escapado: R\\$ 100,00)."
    escaped = escape_streamlit_markdown(raw)
    assert escaped == "De R\\$ 2.399,00 por R\\$ 1.967,18 (já escapado: R\\$ 100,00)."


def test_convert_pdf_to_markdown_with_fake_client(tmp_path: Path) -> None:
    from convert_pdf import convert_pdf_to_markdown

    # Simula o nome original com acento ('políticas_da_loja.pdf') para testar a renomeação automática
    accented_pdf = tmp_path / "políticas_da_loja.pdf"
    accented_pdf.write_bytes(b"%PDF-1.4 fake pdf bytes")
    target_md = tmp_path / "politicas_da_loja.md"

    class FakePdfClient:
        class models:
            @staticmethod
            def generate_content(model: str, contents: list, config: object) -> object:
                assert model == "gemini-3.5-flash-lite"
                return SimpleNamespace(text="```markdown\n## EMPÓRIO DA MÚSICA\nHorário: 09:00 às 18:00\n```")

    out_path = convert_pdf_to_markdown(
        pdf_path=tmp_path / "politicas_da_loja.pdf",
        md_path=target_md,
        client=FakePdfClient(),
    )
    assert out_path == target_md
    assert (tmp_path / "politicas_da_loja.pdf").exists()
    assert not accented_pdf.exists()
    content = target_md.read_text(encoding="utf-8")
    assert content.startswith("## EMPÓRIO DA MÚSICA")
    assert "```" not in content



