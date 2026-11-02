"""Interface Web em Streamlit com Chat e Inspetor de Tool Calls para a Empório da Música."""

from __future__ import annotations

import re
import streamlit as st

from src.agent import EmporioMusicaAgent
from src.config import AVAILABLE_GEMINI_MODELS, GEMINI_API_KEY, GEMINI_MODEL
from src.memory import ConversationMemory


def escape_streamlit_markdown(text: str) -> str:
    """Escapa o símbolo '$' (ex.: 'R$') para evitar que o KaTeX do Streamlit interprete preços como fórmulas LaTeX."""
    if not text:
        return ""
    return re.sub(r"(?<!\\)\$", r"\$", text)

st.set_page_config(
    page_title="Empório da Música — Assistente Virtual",
    page_icon="🎸",
    layout="wide",
)

QUICK_PROMPTS = [
    "Quais opções de violões disponíveis custando até R$1000?",
    "Quanto custa o Takamine GD20? Ainda tem alguma promoção nele e quanto fica o frete para Dourados (79804-970)?",
    "Me arrependi da minha compra, posso devolver meu pedido? Sou a Fernanda (pedido 13) e também quero saber do pedido 7.",
    "Qual o endereço, telefone e horário de funcionamento da loja? Vocês vendem encordoamento e amplificador?",
]


def main() -> None:
    memory = ConversationMemory()

    if "session_id" not in st.session_state:
        st.session_state.session_id = "streamlit_default"

    with st.sidebar:
        st.title("🎸 Empório da Música")
        st.caption("*Sua música começa aqui.* — Campo Grande/MS")
        st.divider()

        api_key_input = st.text_input(
            "🔑 Google Gemini API Key",
            value=GEMINI_API_KEY,
            type="password",
            help="Carregada automaticamente do arquivo .env se presente.",
        )
        model_options = list(AVAILABLE_GEMINI_MODELS)
        default_idx = model_options.index(GEMINI_MODEL) if GEMINI_MODEL in model_options else 0
        model_choice = st.selectbox(
            "🤖 Modelo Gemini",
            options=model_options,
            index=default_idx,
        )
        session_id = st.text_input("🗂️ ID da Sessão", value=st.session_state.session_id)
        st.session_state.session_id = session_id

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Limpar Chat", use_container_width=True):
                memory.clear_session(session_id)
                st.rerun()
        with col2:
            md_export = memory.export_session_markdown(session_id)
            st.download_button(
                "📥 Exportar .md",
                data=md_export,
                file_name=f"atendimento_{session_id}.md",
                mime="text/markdown",
                use_container_width=True,
            )

        st.divider()
        st.subheader("⚡ Cenários Rápidos")
        selected_quick_prompt: str | None = None
        for idx, qp in enumerate(QUICK_PROMPTS):
            if st.button(qp, key=f"qp_{idx}", use_container_width=True):
                selected_quick_prompt = qp

    st.header("🎸 Atendimento Virtual — Empório da Música")
    st.markdown(
        "Tire dúvidas sobre nosso **catálogo de instrumentos**, **preços e promoções**, "
        "**simulação de PIX/parcelamento e frete** ou consulte o **status e trocas do seu pedido**."
    )

    messages = memory.get_messages(session_id)
    if not messages:
        with st.chat_message("assistant", avatar="🎸"):
            st.markdown(
                "Olá! Bem-vindo(a) à **Empório da Música**! 🎶\n\n"
                "Sou o assistente virtual da loja. Posso ajudar você a encontrar o instrumento ideal, "
                "consultar preços, promoções, opções de parcelamento/frete ou verificar seus pedidos. "
                "Como posso te ajudar hoje?"
            )

    for msg in messages:
        avatar = "👤" if msg["role"] == "user" else "🎸"
        with st.chat_message(msg["role"], avatar=avatar):
            if msg["role"] == "assistant" and msg.get("tool_calls"):
                with st.expander(f"🔧 Ferramentas consultadas ({len(msg['tool_calls'])})", expanded=False):
                    for tc in msg["tool_calls"]:
                        st.markdown(f"**`{tc['name']}`** ({tc.get('duration_ms', 0)} ms)")
                        st.json({"args": tc.get("args"), "result": tc.get("result")})
            st.markdown(escape_streamlit_markdown(msg["content"]))

    user_prompt = st.chat_input("Digite sua mensagem sobre instrumentos, preços, políticas ou pedidos...")
    active_prompt = selected_quick_prompt or user_prompt

    if active_prompt:
        with st.chat_message("user", avatar="👤"):
            st.markdown(escape_streamlit_markdown(active_prompt))

        with st.chat_message("assistant", avatar="🎸"):
            with st.spinner("Consultando catálogo e políticas da Empório da Música..."):
                try:
                    agent = EmporioMusicaAgent(
                        api_key=api_key_input,
                        model=model_choice,
                        memory=memory,
                    )
                    turn = agent.chat(active_prompt, session_id=session_id)
                    if turn.tool_calls:
                        with st.expander(f"🔧 Ferramentas consultadas ({len(turn.tool_calls)})", expanded=False):
                            for tc in turn.tool_calls:
                                st.markdown(f"**`{tc['name']}`** ({tc.get('duration_ms', 0)} ms)")
                                st.json({"args": tc.get("args"), "result": tc.get("result")})
                    st.markdown(escape_streamlit_markdown(turn.text))
                except Exception as exc:
                    st.error(f"Erro ao processar mensagem: {exc}")


if __name__ == "__main__":
    main()

