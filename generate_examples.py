"""Gera os 5 arquivos de exemplos de interação em `examples/` executando as ferramentas reais sobre o SQLite."""

from __future__ import annotations

from pathlib import Path

from src.agent import (
    tool_buscar_produtos,
    tool_consultar_pedido,
    tool_obter_detalhes_produto,
    tool_simular_pagamento_e_frete,
)
from src.database import init_database
from src.memory import ConversationMemory

EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"


def generate_all_examples(tmp_db_path: Path | None = None) -> list[Path]:
    init_database()
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    mem_path = tmp_db_path or (EXAMPLES_DIR / "_examples_memory.db")
    if mem_path.exists():
        mem_path.unlink()
    memory = ConversationMemory(db_path=mem_path)

    generated_files: list[Path] = []

    # =========================================================================
    # EXEMPLO 1: Catálogo de Violões até R$ 1.000 + Armadilha Estoque Zero + Parcelamento Escalonado
    # =========================================================================
    s1 = "01_catalogo_violoes_ate_1000_e_estoque"
    q1_1 = "Olá! Quais opções de violões disponíveis vocês têm custando até R$ 1.000?"
    res_v1000 = tool_buscar_produtos(categoria="Violões", preco_max=1000.0)
    memory.add_message(s1, "user", q1_1)
    memory.add_message(
        s1,
        "assistant",
        (
            "Olá! Seja muito bem-vindo(a) à **Empório da Música**! 🎶\n\n"
            "Consultei nosso estoque atual e temos **13 modelos de violões disponíveis para pronta-entrega** "
            "custando até **R$ 1.000,00**, divididos entre cordas de **nylon** (ideais para iniciantes, MPB e clássico) "
            "e cordas de **aço** (timbre mais brilhante e encorpado para pop, sertanejo e folk):\n\n"
            "#### 🎵 Violões com Cordas de Nylon (Disponíveis)\n"
            "1. **Tagima Memphis AC-39 Nylon Natural** — **R$ 429,90** (ou **R$ 408,40** no PIX com 5% OFF) | *15 un. em estoque*\n"
            "2. **Giannini N-14 Nylon Natural** — **R$ 459,90** (ou **R$ 436,90** no PIX) | *8 un. em estoque*\n"
            "3. **Vogga VCA104 Nylon Natural** — **R$ 489,90** (ou **R$ 465,40** no PIX) | *9 un. em estoque*\n"
            "4. **Strinberg SC-200C Nylon Natural** — **R$ 539,00** (ou **R$ 512,05** no PIX) | *10 un. em estoque*\n"
            "5. **Yamaha C40 Nylon Natural** — **R$ 599,90** (ou **R$ 569,90** no PIX) | *12 un. em estoque*\n"
            "6. **Michael VM19E Nylon Natural** — **R$ 629,00** (ou **R$ 597,55** no PIX) | *6 un. em estoque*\n"
            "7. **Rozini RX201 Clássico Nylon Natural** — **R$ 689,00** (ou **R$ 654,55** no PIX) | *6 un. em estoque*\n"
            "8. **Di Giorgio Estudante 18 Nylon Natural** — **R$ 749,00** (ou **R$ 711,55** no PIX) | *14 un. em estoque*\n"
            "9. **Yamaha C70 Nylon Natural** — **R$ 849,00** (ou **R$ 806,55** no PIX) | *8 un. em estoque*\n"
            "10. **Rozini RX210 Studio Nylon Natural** — **R$ 949,00** (ou **R$ 901,55** no PIX) | *4 un. em estoque*\n\n"
            "#### 🎸 Violões com Cordas de Aço (Disponíveis)\n"
            "11. **Shelby SN-100 Folk Aço Preto** — **R$ 549,00** (ou **R$ 521,55** no PIX) | *5 un. em estoque*\n"
            "12. **Eagle CH-888 Folk Aço Sunburst** — **R$ 799,00** (ou **R$ 759,05** no PIX) | *7 un. em estoque*\n"
            "13. **Tagima Woodstock Dreadnought Natural** — **R$ 899,00** (ou **R$ 854,05** no PIX) | *11 un. em estoque*\n\n"
            "> **Nota de transparência sobre o estoque**: O modelo **Giannini GF-3D Dreadnought Sunburst** (R$ 799,90) "
            "consta no nosso catálogo nessa faixa de preço, porém está **temporariamente sem estoque (0 unidades)** no momento. "
            "Caso busque um violão de aço nessa mesma faixa, o **Eagle CH-888 Sunburst (R$ 799,00)** e o **Tagima Woodstock (R$ 899,00)** "
            "são excelentes alternativas disponíveis!\n\n"
            "Você tem preferência por cordas de **nylon** ou de **aço**?"
        ),
        tool_calls=[
            {
                "name": "tool_buscar_produtos",
                "args": {"categoria": "Violões", "preco_max": 1000.0},
                "result": res_v1000,
                "duration_ms": 4.2,
            }
        ],
    )

    q1_2 = "Gostei do Tagima Memphis AC-39 (R$ 429,90) para minha filha começar e do Tagima Woodstock (R$ 899) para mim. Consigo parcelar apenas o Memphis AC-39 em 6x sem juros? E como fica o frete para Campo Grande?"
    res_sim_429 = tool_simular_pagamento_e_frete(
        produto_id_ou_nome="Tagima Memphis AC-39",
        destino_cep_ou_cidade="Campo Grande",
    )
    res_sim_899 = tool_simular_pagamento_e_frete(
        produto_id_ou_nome="Tagima Woodstock Dreadnought Natural",
        destino_cep_ou_cidade="Campo Grande",
    )
    memory.add_message(s1, "user", q1_2)
    memory.add_message(
        s1,
        "assistant",
        (
            "Ótimas escolhas! Vou te explicar certinho como funcionam nossas **regras de parcelamento (Seção 3.1)** "
            "e o **frete para Campo Grande (Seção 5.1)** em cada cenário:\n\n"
            "#### 1. Tagima Memphis AC-39 (R$ 429,90) comprado separadamente\n"
            "- **Por que não chega a 6x?** Na nossa política de parcelamento sem juros:\n"
            "  - De **1x a 3x**: parcela mínima de **R$ 50,00**.\n"
            "  - De **4x a 6x**: parcela mínima de **R$ 80,00**.\n"
            "  - De **7x a 12x**: parcela mínima de **R$ 100,00**.\n"
            "- Como R$ 429,90 dividido por 6 daria R$ 71,65 (abaixo do mínimo de R$ 80,00 para a faixa de 4x a 6x), "
            "o parcelamento máximo dele sozinho é em **5x sem juros de R$ 85,98** (ou **R$ 408,40 à vista no PIX**).\n"
            "- **Frete em Campo Grande**: Como o valor individual fica abaixo de R$ 500,00, há a **taxa fixa de R$ 35,00** "
            "(entrega via motoboy próprio em **1 a 3 dias úteis**).\n\n"
            "#### 2. Tagima Woodstock Dreadnought (R$ 899,00)\n"
            "- Pode ser parcelado em até **8x sem juros de R$ 112,38** (respeitando a parcela mínima de R$ 100,00 para a faixa de 7x a 12x), "
            "em **6x de R$ 149,83**, ou **R$ 854,05 no PIX**.\n"
            "- **Frete Grátis em Campo Grande**: Por superar **R$ 500,00**, a entrega por motoboy próprio (1 a 3 dias úteis) sai **totalmente grátis**!\n\n"
            "💡 **Dica**: Se você fechar os dois juntos no mesmo pedido (**total de R$ 1.328,90**), além de garantir **Frete Grátis** para Campo Grande, "
            "consegue parcelar o pedido inteiro em até **12x sem juros de R$ 110,74** (ou pagar **R$ 1.262,45 no PIX**). Quer que eu separe os dois para você?"
        ),
        tool_calls=[
            {
                "name": "tool_simular_pagamento_e_frete",
                "args": {"produto_id_ou_nome": "Tagima Memphis AC-39", "destino_cep_ou_cidade": "Campo Grande"},
                "result": res_sim_429,
                "duration_ms": 2.8,
            },
            {
                "name": "tool_simular_pagamento_e_frete",
                "args": {
                    "produto_id_ou_nome": "Tagima Woodstock Dreadnought Natural",
                    "destino_cep_ou_cidade": "Campo Grande",
                },
                "result": res_sim_899,
                "duration_ms": 2.5,
            },
        ],
    )
    f1 = EXAMPLES_DIR / f"{s1}.md"
    f1.write_text(
        memory.export_session_markdown(
            s1,
            scenario_title="Cenário 1 — Catálogo de Violões até R$ 1.000, Filtro de Estoque Zero e Regras de Parcelamento/Frete",
        ),
        encoding="utf-8",
    )
    generated_files.append(f1)

    # =========================================================================
    # EXEMPLO 2: Preço do Takamine GD20 (Promoção Expirada) vs Promoção Ativa (Crafter HT-100) + Frete Melhor Envio/Contingência
    # =========================================================================
    s2 = "02_preco_takamine_gd20_promocao_pix_e_frete"
    q2_1 = "Quanto custa o Takamine GD20? Um amigo comentou que tinha visto ele com 12% de desconto na loja."
    res_takamine = tool_obter_detalhes_produto(produto_id_ou_nome="Takamine GD20")
    res_sim_takamine = tool_simular_pagamento_e_frete(produto_id_ou_nome="Takamine GD20")
    memory.add_message(s2, "user", q2_1)
    memory.add_message(
        s2,
        "assistant",
        (
            "O **Takamine GD20 Dreadnought Natural** está disponível em nosso estoque (**5 unidades** à pronta-entrega) "
            "e o preço vigente de tabela é **R$ 2.199,00**.\n\n"
            "#### 🔍 Sobre a promoção de 12% que seu amigo viu\n"
            "Verifiquei no histórico do nosso sistema e realmente houve uma campanha de **Oferta Especial com 12% de desconto** "
            "para esse modelo (`promotion_id = 4`), porém **essa promoção já está encerrada** no momento.\n\n"
            "#### 💳 Condições atuais de pagamento para o Takamine GD20 (R$ 2.199,00)\n"
            "- **PIX à vista (5% de desconto)**: **R$ 2.089,05** (economia de R$ 109,95!).\n"
            "- **Cartão de Crédito**: Em até **12x sem juros de R$ 183,25**.\n"
            "- **Pagamento Combinado (Seção 3.1)**: Como o valor ultrapassa R$ 2.000,00, você também pode combinar formas de pagamento (por exemplo, dar uma entrada no PIX e parcelar o restante no cartão)!\n\n"
            "Sobre o instrumento: ele tem tampo sólido em **Cedro (Solid Cedar)** com fundo e laterais em Sapele e braço em Mogno — "
            "timbre super quente e articulado, excelente para *fingerstyle*!"
        ),
        tool_calls=[
            {
                "name": "tool_obter_detalhes_produto",
                "args": {"produto_id_ou_nome": "Takamine GD20"},
                "result": res_takamine,
                "duration_ms": 3.1,
            },
            {
                "name": "tool_simular_pagamento_e_frete",
                "args": {"produto_id_ou_nome": "Takamine GD20"},
                "result": res_sim_takamine,
                "duration_ms": 2.4,
            },
        ],
    )

    q2_2 = "Entendi! E vocês têm algum violão de aço de nível parecido que esteja com promoção ativa hoje? Se eu pegar esse em promoção no PIX, ganho mais 5% de desconto? Calcula também o frete para Dourados/MS (CEP 79804-970)."
    res_promos_violao = tool_buscar_produtos(categoria="Violões", tipo_corda="aco", apenas_em_promocao=True)
    res_sim_crafter = tool_simular_pagamento_e_frete(
        produto_id_ou_nome="Crafter HT-100",
        destino_cep_ou_cidade="79804-970",
    )
    memory.add_message(s2, "user", q2_2)
    memory.add_message(
        s2,
        "assistant",
        (
            "Temos sim! Hoje temos **2 violões de aço com promoção ativa** no catálogo, e um deles está exatamente na mesma faixa do Takamine GD20:\n\n"
            "#### 🔥 1. Crafter HT-100 Folk Aço Natural (Promoção Ativa: Desconto Exclusivo)\n"
            "- **Preço Original**: R$ 2.399,00\n"
            "- **Desconto Ativo**: **18% OFF**\n"
            "- **Preço Promocional**: **R$ 1.967,18** (*3 unidades em estoque*)\n"
            "- **Destaques**: Tampo sólido em *Spruce Engelmann* com fundo e braço em Mogno.\n\n"
            "*(Também temos o **Taylor 110e Dreadnought Natural** de R$ 5.999,00 por **R$ 5.519,08 — 8% OFF**, com 4 unidades em estoque)*.\n\n"
            "---\n\n"
            "#### ⚠️ Sobre o desconto de 5% no PIX em produtos promocionais (Seção 6.2)\n"
            "Pela nossa política de promoções, **os descontos não são cumulativos**. Ou seja, como o **Crafter HT-100** já está com **18% de desconto ativo** "
            "(saindo por **R$ 1.967,18**), o desconto adicional de 5% do PIX não se aplica sobre ele. Você pode pagar **R$ 1.967,18** no PIX, débito, boleto "
            "ou parcelar esse mesmo valor promocional em até **12x sem juros de R$ 163,93** no cartão!\n\n"
            "#### 🚚 Frete para Dourados/MS (`79804-970`) — Crafter HT-100 (com seguro e rastreamento inclusos)\n"
            "- **PAC (Correios)**: **R$ 78,41** — Prazo estimado: **5 a 12 dias úteis**\n"
            "- **Jadlog (.package)**: **R$ 88,49** — Prazo estimado: **3 a 8 dias úteis**\n"
            "- **SEDEX (Correios)**: **R$ 117,81** — Prazo estimado: **2 a 5 dias úteis**\n\n"
            "Prefere aproveitar a promoção do **Crafter HT-100** por R$ 1.967,18 ou ficar com o **Takamine GD20**?"
        ),
        tool_calls=[
            {
                "name": "tool_buscar_produtos",
                "args": {"categoria": "Violões", "tipo_corda": "aco", "apenas_em_promocao": True},
                "result": res_promos_violao,
                "duration_ms": 3.5,
            },
            {
                "name": "tool_simular_pagamento_e_frete",
                "args": {"produto_id_ou_nome": "Crafter HT-100", "destino_cep_ou_cidade": "79804-970"},
                "result": res_sim_crafter,
                "duration_ms": 3.0,
            },
        ],
    )
    f2 = EXAMPLES_DIR / f"{s2}.md"
    f2.write_text(
        memory.export_session_markdown(
            s2,
            scenario_title="Cenário 2 — Consulta do Takamine GD20 (Promoção Expirada), Regra de Não-Cumulatividade do PIX e Frete",
        ),
        encoding="utf-8",
    )
    generated_files.append(f2)

    # =========================================================================
    # EXEMPLO 3: Políticas de Devolução / Arrependimento Cruzadas com Pedidos Reais (orders.csv)
    # =========================================================================
    s3 = "03_devolucao_arrependimento_e_troca_pedidos"
    q3_1 = "Me arrependi da minha compra, posso devolver meu pedido?"
    memory.add_message(s3, "user", q3_1)
    memory.add_message(
        s3,
        "assistant",
        (
            "Olá! Pode sim, desde que o pedido se enquadre nas condições da nossa **Política de Trocas e Devoluções (Seção 4)**, "
            "que segue o Código de Defesa do Consumidor:\n\n"
            "#### 📋 Regras para Direito de Arrependimento (Compras Online — Seção 4.1) e Troca por Preferência (Seção 4.3)\n"
            "- **Prazo**: Até **7 (sete) dias corridos** contados a partir da data de **recebimento** do produto.\n"
            "- **Condições do instrumento**: Deve estar na **embalagem original**, **sem sinais de uso**, acompanhado de todos os manuais e itens originais.\n"
            "- **Custos e Reembolso**: No direito de arrependimento, o **frete de devolução é por conta da Empório da Música** e o reembolso integral é feito na mesma forma de pagamento em até **10 dias úteis**.\n"
            "- **Exceções não elegíveis (Seção 4.4)**: Instrumentos que passaram por personalização/setup sob encomenda, itens de liquidação marcados como *'venda final'* e boquilhas de instrumentos de sopro (por questões de higiene).\n\n"
            "Para eu verificar agora mesmo a situação exata da sua compra, você pode me informar o **número do pedido** ou o seu **nome completo / e-mail**?"
        ),
        tool_calls=[],
    )

    q3_2 = "Sou a Letícia Gonçalves Rocha (pedido 7) e também queria ver o pedido 8 da minha irmã Ana Carolina Ferreira."
    res_ord7 = tool_consultar_pedido(order_id=7)
    res_ord8 = tool_consultar_pedido(order_id=8)
    memory.add_message(s3, "user", q3_2)
    memory.add_message(
        s3,
        "assistant",
        (
            "Consultei os dois pedidos aqui no nosso sistema (considerando a data de referência `25/03/2026`). Veja a situação detalhada de cada um:\n\n"
            "---\n\n"
            "#### 📦 1. Pedido #7 — Letícia Gonçalves Rocha (`le***a@jmail.com`)\n"
            "- **Produto**: 1x *Kalani KAL-100S Soprano Natural* (Ukulele) — **R$ 159,90** (`credit_3x`)\n"
            "- **Status**: Entregue em **17/02/2026** (data da compra: 03/02/2026 | Rastreio: `BRKR1122334BR`)\n"
            "- **Análise para Devolução por Arrependimento / Preferência**:\n"
            "  - ❌ **Fora do prazo de 7 dias corridos**: Como a entrega ocorreu em **17/02/2026** (há **36 dias**), o prazo legal de 7 dias corridos para devolução por arrependimento ou troca por preferência infelizmente já se encerrou.\n"
            "  - 🛠️ **Observação caso haja defeito**: O prazo de 30 dias para troca direta na loja também se encerrou, mas o seu ukulele ainda está dentro da **Garantia Legal de 90 dias do CDC (Seção 8.1)** e da garantia do fabricante contra defeitos de fabricação!\n\n"
            "---\n\n"
            "#### 🚚 2. Pedido #8 — Ana Carolina Ferreira (`an***a@coldmail.com`)\n"
            "- **Produto**: 1x *Shelby SU-21M Soprano Mogno* (Ukulele) — **R$ 349,90** (`debit`)\n"
            "- **Status**: **Enviado / Em trânsito** (Rastreio: `BRJL5544332BR`)\n"
            "- **Análise para Devolução por Arrependimento**:\n"
            "  - ✅ **Elegível assim que receber**: Como o pedido ainda consta com status **Em trânsito (`shipped`)**, o prazo de **7 dias corridos** do Direito de Arrependimento passa a contar a partir do dia em que ela receber o pacote! Assim que for entregue, basta manter na embalagem original sem uso e nos acionar em até 7 dias que geramos a logística reversa gratuita para reembolso."
        ),
        tool_calls=[
            {
                "name": "tool_consultar_pedido",
                "args": {"order_id": 7},
                "result": res_ord7,
                "duration_ms": 3.4,
            },
            {
                "name": "tool_consultar_pedido",
                "args": {"order_id": 8},
                "result": res_ord8,
                "duration_ms": 2.9,
            },
        ],
    )
    f3 = EXAMPLES_DIR / f"{s3}.md"
    f3.write_text(
        memory.export_session_markdown(
            s3,
            scenario_title="Cenário 3 — Aplicação das Políticas de Devolução (Arrependimento 7 Dias vs. Garantia Legal) em Pedidos Reais",
        ),
        encoding="utf-8",
    )
    generated_files.append(f3)

    # =========================================================================
    # EXEMPLO 4: Endereço/Horário, Produto Descontinuado com Saldo Residual (Ibanez Bass 2X) e Escopo de Acessórios
    # =========================================================================
    s4 = "04_produto_descontinuado_e_escopo_acessorios"
    q4_1 = "Qual o endereço e o horário de funcionamento da loja? Quero passar aí no sábado às 15h para comprar o baixo Ibanez Bass 2X e aproveitar para levar um encordoamento novo, palhetas e um amplificador pequeno."
    res_ibanez = tool_obter_detalhes_produto(produto_id_ou_nome="Ibanez Bass 2X")
    res_acess = tool_buscar_produtos(termo_busca="encordoamento palhetas amplificador")
    memory.add_message(s4, "user", q4_1)
    memory.add_message(
        s4,
        "assistant",
        (
            "Que ótimo saber que você quer nos visitar! Antes de você vir, preciso te passar **4 informações muito importantes** "
            "para você não perder a viagem:\n\n"
            "#### 📍 1. Endereço e Contatos da Loja (Seção 1.2 e 7)\n"
            "- **Endereço**: Rua 14 de Maio, 3200 — Centro, Campo Grande – MS (CEP 79202-333).\n"
            "- **Telefone Fixo**: (67) 3341-4444 | **WhatsApp de Atendimento**: (67) 3321-4500.\n"
            "- **E-mail**: contato@emporiodamusica.com.br\n\n"
            "#### ⏰ 2. Atenção ao Horário de Sábado! (Seção 2)\n"
            "- **Segunda a Sexta-feira**: 09:00 às 18:00\n"
            "- **Sábado**: **09:00 às 13:00** *(fechamos às 13h no sábado!)*\n"
            "- **Domingo e Feriados**: Fechado\n"
            "Portanto, às **15h de sábado a loja já estará fechada**. Programe-se para vir no sábado pela manhã (até as 13h) ou durante a semana!\n\n"
            "#### 🎸 3. Sobre o Contrabaixo Ibanez Bass 2X (Seção 7.3 — Produto Descontinuado)\n"
            "Consultei nosso sistema e o modelo **Ibanez Bass 2X Electric Bass** (`product_id = 136`) foi **descontinuado** e não faz mais parte do nosso catálogo de vendas. "
            "Mas temos **3 excelentes contrabaixos ativos em estoque** para você testar na loja:\n"
            "1. **Tagima Millenium 4 Cordas Preto** — **R$ 1.299,00** (ou **R$ 1.234,05** no PIX) | *6 un. em estoque*\n"
            "2. **Yamaha TRBX174 4 Cordas Preto** — **R$ 1.899,00** (ou **R$ 1.804,05** no PIX) | *5 un. em estoque*\n"
            "3. **Squier Affinity Jazz Bass Sunburst** — **R$ 2.799,00** (ou **R$ 2.659,05** no PIX) | *3 un. em estoque*\n\n"
            "#### 🔌 4. Sobre Encordoamento, Palhetas e Amplificador (Seções 1 e 7.1 — Escopo da Loja)\n"
            "A **Empório da Música trabalha exclusivamente com instrumentos musicais** — nós **não comercializamos acessórios ou equipamentos de áudio** "
            "(como cordas avulsas, palhetas, cabos, cases, pedais ou amplificadores). Para esses itens, recomendamos procurar lojas parceiras de acessórios musicais aqui no Centro de Campo Grande!\n\n"
            "Quer que eu deixe o **Yamaha TRBX174** ou o **Tagima Millenium** separado para você testar no sábado pela manhã?"
        ),
        tool_calls=[
            {
                "name": "tool_obter_detalhes_produto",
                "args": {"produto_id_ou_nome": "Ibanez Bass 2X"},
                "result": res_ibanez,
                "duration_ms": 3.2,
            },
            {
                "name": "tool_buscar_produtos",
                "args": {"termo_busca": "encordoamento palhetas amplificador"},
                "result": res_acess,
                "duration_ms": 2.1,
            },
        ],
    )
    f4 = EXAMPLES_DIR / f"{s4}.md"
    f4.write_text(
        memory.export_session_markdown(
            s4,
            scenario_title="Cenário 4 — Endereço/Horário, Produto Descontinuado com Saldo Residual (Ibanez Bass 2X) e Escopo de Acessórios",
        ),
        encoding="utf-8",
    )
    generated_files.append(f4)

    # =========================================================================
    # EXEMPLO 5: Categorias Sem Estoque (Sopro/Orquestrais) + Guardrail de Perguntas Fora do Escopo
    # =========================================================================
    s5 = "05_fora_de_escopo_e_categorias_sem_estoque"
    q5_1 = "Vocês têm saxofone alto ou violino 4/4 disponíveis hoje? E aproveitando, você pode escrever um script em Python para declarar imposto de renda e me dar uma receita de pão de queijo?"
    res_sax = tool_buscar_produtos(termo_busca="saxofone")
    res_violino = tool_buscar_produtos(termo_busca="violino")
    memory.add_message(s5, "user", q5_1)
    memory.add_message(
        s5,
        "assistant",
        (
            "Olá! Vou responder primeiro sobre os instrumentos e depois sobre os outros pedidos:\n\n"
            "#### 🎷 1. Saxofone e Violino (Categorias sem modelos em estoque no momento)\n"
            "Embora a Empório da Música trabalhe com as categorias de **Instrumentos de Sopro (Madeiras e Metais)** e **Cordas Orquestrais**, "
            "consultei nosso sistema em tempo real e **no momento estamos sem nenhum modelo de saxofone ou violino disponível em estoque**.\n"
            "Hoje temos pronta-entrega completa nas linhas de:\n"
            "- **Violões** (clássicos nylon, folk aço, dreadnought e eletroacústicos)\n"
            "- **Ukuleles** (soprano, concert, tenor e barítono)\n"
            "- **Guitarras** e **Contrabaixos**\n"
            "- **Teclados / Pianos Digitais** e **Baterias**\n\n"
            "#### 🛡️ 2. Sobre o script de Imposto de Renda e a receita de Pão de Queijo\n"
            "Por mais que um pão de queijo quentinho combine muito bem com uma roda de violão 😄, sou o assistente virtual dedicado "
            "**exclusivamente ao atendimento da Empório da Música** e não consigo ajudar com programação, contabilidade/imposto de renda ou receitas culinárias.\n\n"
            "Se quiser conhecer algum instrumento das nossas linhas disponíveis em estoque ou tirar dúvidas sobre a loja, é só me chamar!"
        ),
        tool_calls=[
            {
                "name": "tool_buscar_produtos",
                "args": {"termo_busca": "saxofone"},
                "result": res_sax,
                "duration_ms": 2.3,
            },
            {
                "name": "tool_buscar_produtos",
                "args": {"termo_busca": "violino"},
                "result": res_violino,
                "duration_ms": 2.0,
            },
        ],
    )
    f5 = EXAMPLES_DIR / f"{s5}.md"
    f5.write_text(
        memory.export_session_markdown(
            s5,
            scenario_title="Cenário 5 — Categorias Sem Estoque (Sopro e Cordas Orquestrais) e Guardrails contra Assuntos Fora do Escopo",
        ),
        encoding="utf-8",
    )
    generated_files.append(f5)

    if mem_path.exists():
        mem_path.unlink()

    return generated_files


if __name__ == "__main__":
    files = generate_all_examples()
    for f in files:
        print(f"Gerado: {f}")
