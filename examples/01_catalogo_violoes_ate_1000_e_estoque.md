# Cenário 1 — Catálogo de Violões até R$ 1.000, Filtro de Estoque Zero e Regras de Parcelamento/Frete

### 👤 Cliente

Olá! Quais opções de violões disponíveis vocês têm custando até R$ 1.000?

---

<details>
<summary>🔧 <b>Ferramentas consultadas pelo Agente (1)</b></summary>

- **`tool_buscar_produtos`** — Argumentos: `{"categoria": "Violões", "preco_max": 1000.0}`

</details>

### 🎸 Assistente Empório da Música

Olá! Seja muito bem-vindo(a) à **Empório da Música**! 🎶

Consultei nosso estoque atual e temos **13 modelos de violões disponíveis para pronta-entrega** custando até **R$ 1.000,00**, divididos entre cordas de **nylon** (ideais para iniciantes, MPB e clássico) e cordas de **aço** (timbre mais brilhante e encorpado para pop, sertanejo e folk):

#### 🎵 Violões com Cordas de Nylon (Disponíveis)
1. **Tagima Memphis AC-39 Nylon Natural** — **R$ 429,90** (ou **R$ 408,40** no PIX com 5% OFF) | *15 un. em estoque*
2. **Giannini N-14 Nylon Natural** — **R$ 459,90** (ou **R$ 436,90** no PIX) | *8 un. em estoque*
3. **Vogga VCA104 Nylon Natural** — **R$ 489,90** (ou **R$ 465,40** no PIX) | *9 un. em estoque*
4. **Strinberg SC-200C Nylon Natural** — **R$ 539,00** (ou **R$ 512,05** no PIX) | *10 un. em estoque*
5. **Yamaha C40 Nylon Natural** — **R$ 599,90** (ou **R$ 569,90** no PIX) | *12 un. em estoque*
6. **Michael VM19E Nylon Natural** — **R$ 629,00** (ou **R$ 597,55** no PIX) | *6 un. em estoque*
7. **Rozini RX201 Clássico Nylon Natural** — **R$ 689,00** (ou **R$ 654,55** no PIX) | *6 un. em estoque*
8. **Di Giorgio Estudante 18 Nylon Natural** — **R$ 749,00** (ou **R$ 711,55** no PIX) | *14 un. em estoque*
9. **Yamaha C70 Nylon Natural** — **R$ 849,00** (ou **R$ 806,55** no PIX) | *8 un. em estoque*
10. **Rozini RX210 Studio Nylon Natural** — **R$ 949,00** (ou **R$ 901,55** no PIX) | *4 un. em estoque*

#### 🎸 Violões com Cordas de Aço (Disponíveis)
11. **Shelby SN-100 Folk Aço Preto** — **R$ 549,00** (ou **R$ 521,55** no PIX) | *5 un. em estoque*
12. **Eagle CH-888 Folk Aço Sunburst** — **R$ 799,00** (ou **R$ 759,05** no PIX) | *7 un. em estoque*
13. **Tagima Woodstock Dreadnought Natural** — **R$ 899,00** (ou **R$ 854,05** no PIX) | *11 un. em estoque*

> **Nota de transparência sobre o estoque**: O modelo **Giannini GF-3D Dreadnought Sunburst** (R$ 799,90) consta no nosso catálogo nessa faixa de preço, porém está **temporariamente sem estoque (0 unidades)** no momento. Caso busque um violão de aço nessa mesma faixa, o **Eagle CH-888 Sunburst (R$ 799,00)** e o **Tagima Woodstock (R$ 899,00)** são excelentes alternativas disponíveis!

Você tem preferência por cordas de **nylon** ou de **aço**?

---

### 👤 Cliente

Gostei do Tagima Memphis AC-39 (R$ 429,90) para minha filha começar e do Tagima Woodstock (R$ 899) para mim. Consigo parcelar apenas o Memphis AC-39 em 6x sem juros? E como fica o frete para Campo Grande?

---

<details>
<summary>🔧 <b>Ferramentas consultadas pelo Agente (2)</b></summary>

- **`tool_simular_pagamento_e_frete`** — Argumentos: `{"produto_id_ou_nome": "Tagima Memphis AC-39", "destino_cep_ou_cidade": "Campo Grande"}`
- **`tool_simular_pagamento_e_frete`** — Argumentos: `{"produto_id_ou_nome": "Tagima Woodstock Dreadnought Natural", "destino_cep_ou_cidade": "Campo Grande"}`

</details>

### 🎸 Assistente Empório da Música

Ótimas escolhas! Vou te explicar certinho como funcionam nossas **regras de parcelamento (Seção 3.1)** e o **frete para Campo Grande (Seção 5.1)** em cada cenário:

#### 1. Tagima Memphis AC-39 (R$ 429,90) comprado separadamente
- **Por que não chega a 6x?** Na nossa política de parcelamento sem juros:
  - De **1x a 3x**: parcela mínima de **R$ 50,00**.
  - De **4x a 6x**: parcela mínima de **R$ 80,00**.
  - De **7x a 12x**: parcela mínima de **R$ 100,00**.
- Como R$ 429,90 dividido por 6 daria R$ 71,65 (abaixo do mínimo de R$ 80,00 para a faixa de 4x a 6x), o parcelamento máximo dele sozinho é em **5x sem juros de R$ 85,98** (ou **R$ 408,40 à vista no PIX**).
- **Frete em Campo Grande**: Como o valor individual fica abaixo de R$ 500,00, há a **taxa fixa de R$ 35,00** (entrega via motoboy próprio em **1 a 3 dias úteis**).

#### 2. Tagima Woodstock Dreadnought (R$ 899,00)
- Pode ser parcelado em até **8x sem juros de R$ 112,38** (respeitando a parcela mínima de R$ 100,00 para a faixa de 7x a 12x), em **6x de R$ 149,83**, ou **R$ 854,05 no PIX**.
- **Frete Grátis em Campo Grande**: Por superar **R$ 500,00**, a entrega por motoboy próprio (1 a 3 dias úteis) sai **totalmente grátis**!

💡 **Dica**: Se você fechar os dois juntos no mesmo pedido (**total de R$ 1.328,90**), além de garantir **Frete Grátis** para Campo Grande, consegue parcelar o pedido inteiro em até **12x sem juros de R$ 110,74** (ou pagar **R$ 1.262,45 no PIX**). Quer que eu separe os dois para você?

---
