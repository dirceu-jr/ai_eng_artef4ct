# ARTEF4CT

# Preâmbulo

Testei usar os comandos `pdftotext` e `pdf-to-markdown` mas não gostei do resultado.

Teste com `pip install markitdown`.

# Prompts

Antigravity com Gemini 4 Argon.

1 - Estou participando de um processo seletivo e preciso fazer um desafio técnico. Leia o arquivo `desafio_tecnico_ai_eng_artef4ct.md` e siga as instruções. Antes de escrever código, monte um plano de ação com algumas opções de decisões técnicas.

2 - Parece legal. Salve o plano de implementação na raiz do projeto.
No "Modelo / Provedor" podemos utilizar o Google Gemini mais atualizado: "gemini-3.8-flash".
Para o cálculo do frete, faça a avaliação de utilizar a API do "Melhor Envio".

# Perguntas 

- Qual abordagem arquitetural você prefere para o agente e o acesso aos dados/políticas?

    - Híbrida: Tools de negócio sobre SQLite + Políticas completas no contexto + Fallback SQL read-only

- Qual framework de orquestração em Python você prefere utilizar?

    - SDK Nativo / Leve + Pydantic (sem LangChain/LangGraph, código puro e direto)

- Qual provedor de LLM você tem chave disponível (ou prefere usar como principal)?

    - Apenas Google Gemini (ex.: gemini-2.5-flash via Google AI Studio)

- Qual interface de interação você prefere entregar?

    - (Recommended) CLI Interativa (Rich) + Web UI (Streamlit com inspetor de Tool Calls) + Persistência SQLite/JSON

