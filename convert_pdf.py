"""Converte `data/politicas_da_loja.pdf` em `data/politicas_da_loja.md` usando o modelo `gemini-3.5-flash-lite`."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from typing import Any

from google import genai
from google.genai import types

from src.config import DATA_DIR, GEMINI_API_KEY

PDF_CONVERSION_MODEL = "gemini-3.5-flash-lite"

PDF_TO_MD_PROMPT = (
    "Converta integralmente este documento PDF para formato Markdown (.md). "
    "Preserve fielmente todos os títulos, subtítulos, tabelas, listas, valores, "
    "telefones, e-mails, CEPs e regras de negócio sem omitir nenhuma informação "
    "e sem adicionar comentários introdutórios ou conclusivos."
)


def _strip_markdown_fences(text: str) -> str:
    """Remove cercas de código externas (```markdown ... ```) caso o modelo envolva a resposta."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:markdown|md)?\s*\n", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n```\s*$", "", cleaned)
    return cleaned.strip() + "\n"


def convert_pdf_to_markdown(
    pdf_path: Path | None = None,
    md_path: Path | None = None,
    api_key: str | None = None,
    model: str = PDF_CONVERSION_MODEL,
    client: Any | None = None,
) -> Path:
    """Envia o PDF para o Gemini (`gemini-3.5-flash-lite`) e salva o Markdown resultante."""
    source_pdf = pdf_path or (DATA_DIR / "politicas_da_loja.pdf")
    target_md = md_path or (DATA_DIR / "politicas_da_loja.md")

    if not source_pdf.exists():
        raise FileNotFoundError(
            f"Arquivo PDF não encontrado em '{source_pdf}'. "
            "Certifique-se de copiar a pasta 'data/' original do desafio para a raiz do projeto."
        )

    key = (api_key if api_key is not None else GEMINI_API_KEY).strip()
    if client is None:
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY não configurada. Preencha sua chave no arquivo .env antes de converter o PDF."
            )
        client = genai.Client(api_key=key)

    pdf_bytes = source_pdf.read_bytes()
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            PDF_TO_MD_PROMPT,
        ],
        config=types.GenerateContentConfig(temperature=0.0),
    )

    markdown_text = _strip_markdown_fences(response.text or "")
    target_md.parent.mkdir(parents=True, exist_ok=True)
    target_md.write_text(markdown_text, encoding="utf-8")
    return target_md


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Converte o manual PDF de políticas da loja em Markdown via Gemini."
    )
    parser.add_argument(
        "--pdf",
        default=str(DATA_DIR / "politicas_da_loja.pdf"),
        help="Caminho do arquivo PDF de entrada (padrão: data/politicas_da_loja.pdf)",
    )
    parser.add_argument(
        "--output",
        default=str(DATA_DIR / "politicas_da_loja.md"),
        help="Caminho do arquivo Markdown de saída (padrão: data/politicas_da_loja.md)",
    )
    parser.add_argument(
        "--model",
        default=PDF_CONVERSION_MODEL,
        help=f"Modelo Gemini para conversão (padrão: {PDF_CONVERSION_MODEL})",
    )
    args = parser.parse_args()

    try:
        out = convert_pdf_to_markdown(
            pdf_path=Path(args.pdf),
            md_path=Path(args.output),
            model=args.model,
        )
        print(f"✅ Arquivo convertido com sucesso via '{args.model}': {out}")
    except Exception as exc:
        print(f"❌ Erro ao converter PDF: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
