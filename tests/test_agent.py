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
        if self.calls == 1:
            fc = SimpleNamespace(name="tool_obter_detalhes_produto", args={"produto_id_ou_nome": "Takamine GD20"})
            return SimpleNamespace(
                function_calls=[fc],
                candidates=[SimpleNamespace(content=contents[-1])],
                text=None,
            )
        return SimpleNamespace(
            function_calls=[],
            candidates=[],
            text="O Takamine GD20 custa R$ 2.199,00 na tabela (ou R$ 2.089,05 no PIX com 5% de desconto) e temos 5 unidades em estoque!",
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

    # Verifica persistência no banco e exportação Markdown
    history = memory.get_messages("sessao_teste")
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    assert len(history[1]["tool_calls"]) == 1

    md = memory.export_session_markdown("sessao_teste", scenario_title="Teste Takamine")
    assert "# Teste Takamine" in md
    assert "tool_obter_detalhes_produto" in md
