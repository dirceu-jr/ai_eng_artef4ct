"""Configurações centralizadas do projeto carregadas via variáveis de ambiente."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))
DB_PATH = Path(os.getenv("DB_PATH", str(PROJECT_ROOT / "emporio_da_musica.db")))
MEMORY_DB_PATH = Path(os.getenv("MEMORY_DB_PATH", str(PROJECT_ROOT / "chat_memory.db")))

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
AVAILABLE_GEMINI_MODELS: tuple[str, ...] = ("gemini-3.8-flash", "gemini-3.5-flash-lite")
MAX_TOOL_ITERATIONS: int = int(os.getenv("MAX_TOOL_ITERATIONS", "10").strip() or "10")

# Tabela de preços de referência por 1 milhão (1M) de tokens em USD
MODEL_PRICING_USD_PER_1M: dict[str, dict[str, float]] = {
    "gemini-3.8-flash": {"input": 0.75, "output": 3.75, "cached_input": 0.075},
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50, "cached_input": 0.03},
}
USD_TO_BRL_RATE: float = float(os.getenv("USD_TO_BRL_RATE", "5.80").strip() or "5.80")

# Data de referência para avaliar prazos de 7 dias (arrependimento) e 30 dias (defeito)
# Os pedidos em orders.csv vão de 2025-10-15 até 2026-03-22.
REFERENCE_DATE_STR: str = os.getenv("REFERENCE_DATE", "2026-03-25").strip()

# Configurações da API do Melhor Envio
MELHOR_ENVIO_TOKEN: str = os.getenv("MELHOR_ENVIO_TOKEN", "").strip()
MELHOR_ENVIO_SANDBOX: bool = os.getenv("MELHOR_ENVIO_SANDBOX", "true").lower() in ("1", "true", "yes")
MELHOR_ENVIO_USER_AGENT: str = os.getenv(
    "MELHOR_ENVIO_USER_AGENT",
    "EmporioDaMusicaAI (contato@emporiodamusica.com.br)",
).strip()
# Nota técnica: O manual cita CEP 79202-333 (fictício / faixa de Aquidauana-MS).
# Na API postal real, usamos um CEP válido do Centro de Campo Grande-MS (79002-070).
STORE_ORIGIN_CEP: str = os.getenv("STORE_ORIGIN_CEP", "79002070").strip()


def get_reference_date() -> date:
    """Retorna a data de referência configurada para cálculo de elegibilidade de trocas."""
    try:
        return date.fromisoformat(REFERENCE_DATE_STR)
    except ValueError:
        return date(2026, 3, 25)


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


