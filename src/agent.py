"""Orquestrador do agente de atendimento utilizando o SDK nativo `google-genai` e Function Calling."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Callable

from google import genai
from google.genai import types

from src.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    MAX_TOOL_ITERATIONS,
    MEMORY_DB_PATH,
    MODEL_PRICING_USD_PER_1M,
    USD_TO_BRL_RATE,
)
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


def estimate_usage_cost(
    model: str,
    prompt_tokens: int,
    output_tokens: int,
    thoughts_tokens: int = 0,
    cached_tokens: int = 0,
    llm_calls: int = 1,
) -> dict[str, float | int | str]:
    """Calcula o custo estimado em USD e BRL a partir dos contadores do `usage_metadata` do Gemini."""
    rates = MODEL_PRICING_USD_PER_1M.get(model, MODEL_PRICING_USD_PER_1M["gemini-3.8-flash"])
    non_cached_input = max(prompt_tokens - cached_tokens, 0)
    billable_output = output_tokens + thoughts_tokens

    cost_usd = (
        (non_cached_input / 1_000_000) * rates["input"]
        + (cached_tokens / 1_000_000) * rates["cached_input"]
        + (billable_output / 1_000_000) * rates["output"]
    )
    cost_brl = cost_usd * USD_TO_BRL_RATE
    total_tokens = prompt_tokens + output_tokens + thoughts_tokens

    return {
        "model": model,
        "llm_calls": llm_calls,
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "thoughts_tokens": thoughts_tokens,
        "cached_tokens": cached_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(cost_usd, 6),
        "estimated_cost_brl": round(cost_brl, 6),
    }



@dataclass
class AgentTurnResponse:
    """Resposta estruturada de um turno de interação do agente."""

    text: str
    session_id: str
    model_used: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)


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

    def chat(
        self,
        user_message: str,
        session_id: str = "default",
        max_tool_iterations: int = MAX_TOOL_ITERATIONS,
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

        prompt_tokens_sum = 0
        output_tokens_sum = 0
        thoughts_tokens_sum = 0
        cached_tokens_sum = 0
        llm_calls_count = 0

        for _ in range(max_tool_iterations):
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config,
            )
            llm_calls_count += 1
            um = getattr(response, "usage_metadata", None)
            if um is not None:
                prompt_tokens_sum += int(getattr(um, "prompt_token_count", 0) or 0)
                output_tokens_sum += int(getattr(um, "candidates_token_count", 0) or 0)
                thoughts_tokens_sum += int(getattr(um, "thoughts_token_count", 0) or 0)
                cached_tokens_sum += int(getattr(um, "cached_content_token_count", 0) or 0)

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

        usage_summary = estimate_usage_cost(
            model=model_used,
            prompt_tokens=prompt_tokens_sum,
            output_tokens=output_tokens_sum,
            thoughts_tokens=thoughts_tokens_sum,
            cached_tokens=cached_tokens_sum,
            llm_calls=llm_calls_count,
        )

        self.memory.add_message(session_id=session_id, role="user", content=user_message)
        self.memory.add_message(
            session_id=session_id,
            role="assistant",
            content=final_text,
            tool_calls=executed_tool_calls,
            usage=usage_summary,
        )

        return AgentTurnResponse(
            text=final_text,
            session_id=session_id,
            model_used=model_used,
            tool_calls=executed_tool_calls,
            usage=usage_summary,
        )

