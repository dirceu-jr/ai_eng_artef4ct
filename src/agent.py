"""Orquestrador do agente de atendimento utilizando o SDK nativo `google-genai` e Function Calling."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Callable

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from src.config import GEMINI_API_KEY, GEMINI_FALLBACK_MODEL, GEMINI_MODEL, MEMORY_DB_PATH
from src.database import init_database
from src.memory import ConversationMemory
from src.prompts import build_system_prompt
from src.tools import (
    buscar_produtos,
    consultar_pedido,
    executar_sql_leitura,
    obter_detalhes_produto,
    simular_pagamento_e_frete,
)


# Wrappers com assinatura limpa para geração automática de JSON Schema pelo SDK google-genai
def tool_buscar_produtos(
    termo_busca: str = "",
    categoria: str = "",
    preco_max: float = 0.0,
    preco_min: float = 0.0,
    tipo_corda: str = "",
    apenas_eletricos: bool = False,
    apenas_em_promocao: bool = False,
) -> dict[str, Any]:
    """Busca instrumentos musicais no catálogo por termo, categoria (Violões, Guitarras, Baixos, Baterias, Teclados, Ukuleles), preço máximo/mínimo, corda (nylon ou aco) e captação elétrica."""
    return buscar_produtos(
        termo_busca=termo_busca,
        categoria=categoria,
        preco_max=preco_max,
        preco_min=preco_min,
        tipo_corda=tipo_corda,
        apenas_eletricos=apenas_eletricos,
        apenas_em_promocao=apenas_em_promocao,
    )


def tool_obter_detalhes_produto(produto_id_ou_nome: str) -> dict[str, Any]:
    """Obtém ficha técnica, preço original, promoções ativas/expiradas, valor no PIX, estoque, status (ativo, sem estoque, descontinuado, em breve) e produtos similares de um instrumento específico."""
    return obter_detalhes_produto(produto_id_ou_nome=produto_id_ou_nome)


def tool_simular_pagamento_e_frete(
    valor_brl: float = 0.0,
    produto_id_ou_nome: str = "",
    tem_promocao_ativa: bool = False,
    percentual_desconto_ativo: float = 0.0,
    destino_cep_ou_cidade: str = "",
    categoria_id: int = 5,
) -> dict[str, Any]:
    """Simula pagamento (PIX com regra de não-cumulatividade, débito, boleto e parcelas de 1x a 12x sem juros com parcelas mínimas de R$50/R$80/R$100) e calcula o frete (Motoboy em Campo Grande ou API Melhor Envio / Contingência para outras cidades)."""
    return simular_pagamento_e_frete(
        valor_brl=valor_brl,
        produto_id_ou_nome=produto_id_ou_nome,
        tem_promocao_ativa=tem_promocao_ativa,
        percentual_desconto_ativo=percentual_desconto_ativo,
        destino_cep_ou_cidade=destino_cep_ou_cidade,
        categoria_id=categoria_id,
    )


def tool_consultar_pedido(order_id: int = 0, identificador_cliente: str = "") -> dict[str, Any]:
    """Consulta pedidos pelo número (order_id de 1 a 20) ou pelo nome, e-mail, telefone ou código de rastreamento do cliente, retornando status, itens e elegibilidade para arrependimento (7 dias), troca por defeito (30 dias) e garantia legal (90 dias)."""
    return consultar_pedido(order_id=order_id, identificador_cliente=identificador_cliente)


def tool_executar_sql_leitura(sql_query: str) -> dict[str, Any]:
    """Executa uma consulta SQL SELECT somente-leitura no banco SQLite (tabelas: v_products_enriched, products, categories, promotions, orders, order_items, customers) para perguntas analíticas não cobertas pelas outras ferramentas."""
    return executar_sql_leitura(sql_query=sql_query)


AGENT_TOOLS: list[Callable[..., dict[str, Any]]] = [
    tool_buscar_produtos,
    tool_obter_detalhes_produto,
    tool_simular_pagamento_e_frete,
    tool_consultar_pedido,
    tool_executar_sql_leitura,
]

TOOL_DISPATCH_MAP: dict[str, Callable[..., dict[str, Any]]] = {
    fn.__name__: fn for fn in AGENT_TOOLS
}


@dataclass
class AgentTurnResponse:
    """Resposta estruturada de um turno de interação do agente."""

    text: str
    session_id: str
    model_used: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class EmporioMusicaAgent:
    """Agente conversacional da Empório da Música com suporte a Function Calling e memória persistente."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        memory: ConversationMemory | None = None,
        client: Any | None = None,
    ) -> None:
        init_database()
        self.api_key = (api_key if api_key is not None else GEMINI_API_KEY).strip()
        self.model_name = (model or GEMINI_MODEL).strip()
        self.fallback_model_name = GEMINI_FALLBACK_MODEL
        self.memory = memory or ConversationMemory(db_path=MEMORY_DB_PATH)
        self.system_prompt = build_system_prompt()
        self._client = client

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            if not self.api_key:
                raise RuntimeError(
                    "GEMINI_API_KEY não configurada. Defina a variável de ambiente GEMINI_API_KEY no arquivo .env."
                )
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _build_contents_from_history(self, session_id: str, new_user_message: str) -> list[types.Content]:
        past_messages = self.memory.get_messages(session_id)
        contents: list[types.Content] = []
        for msg in past_messages[-16:]:  # Mantém janela recente de 16 mensagens
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg["content"])],
                )
            )
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=new_user_message)],
            )
        )
        return contents

    def _generate_with_model_fallback(
        self,
        contents: list[types.Content],
        config: types.GenerateContentConfig,
    ) -> tuple[Any, str]:
        """Invoca `generate_content` com o modelo configurado e faz fallback transparente se o alias não existir na conta."""
        try:
            resp = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config,
            )
            return resp, self.model_name
        except genai_errors.APIError as exc:
            err_msg = str(exc).lower()
            if (
                self.fallback_model_name
                and self.fallback_model_name != self.model_name
                and ("not found" in err_msg or "404" in err_msg or "not supported" in err_msg)
            ):
                resp = self.client.models.generate_content(
                    model=self.fallback_model_name,
                    contents=contents,
                    config=config,
                )
                return resp, self.fallback_model_name
            raise

    def chat(
        self,
        user_message: str,
        session_id: str = "default",
        max_tool_iterations: int = 5,
    ) -> AgentTurnResponse:
        """Processa uma mensagem do cliente, executa ferramentas se necessário e salva no histórico."""
        contents = self._build_contents_from_history(session_id=session_id, new_user_message=user_message)
        config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            tools=AGENT_TOOLS,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0.2,
        )

        executed_tool_calls: list[dict[str, Any]] = []
        model_used = self.model_name
        final_text = ""

        for _ in range(max_tool_iterations):
            response, model_used = self._generate_with_model_fallback(contents=contents, config=config)

            function_calls = getattr(response, "function_calls", None)
            if not function_calls:
                final_text = (response.text or "").strip()
                break

            # Preserva o turno de solicitação de tool do modelo
            if response.candidates and response.candidates[0].content:
                contents.append(response.candidates[0].content)

            tool_response_parts: list[types.Part] = []
            for fc in function_calls:
                fn_name = fc.name
                fn_args = dict(fc.args) if fc.args else {}
                t0 = time.perf_counter()

                target_fn = TOOL_DISPATCH_MAP.get(fn_name)
                if target_fn is None:
                    tool_result: dict[str, Any] = {"error": f"Ferramenta '{fn_name}' não encontrada."}
                else:
                    try:
                        tool_result = target_fn(**fn_args)
                    except Exception as exc:
                        tool_result = {"error": f"Erro ao executar '{fn_name}': {exc}"}

                elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
                executed_tool_calls.append(
                    {
                        "name": fn_name,
                        "args": fn_args,
                        "result": tool_result,
                        "duration_ms": elapsed_ms,
                    }
                )
                tool_response_parts.append(
                    types.Part.from_function_response(
                        name=fn_name,
                        response={"result": tool_result},
                    )
                )

            contents.append(types.Content(role="user", parts=tool_response_parts))
        else:
            final_text = (
                "Consultei as informações no sistema, mas atingi o limite de etapas internas. "
                "Pode reformular ou especificar melhor sua dúvida?"
            )

        self.memory.add_message(session_id=session_id, role="user", content=user_message)
        self.memory.add_message(
            session_id=session_id,
            role="assistant",
            content=final_text,
            tool_calls=executed_tool_calls,
        )

        return AgentTurnResponse(
            text=final_text,
            session_id=session_id,
            model_used=model_used,
            tool_calls=executed_tool_calls,
        )
