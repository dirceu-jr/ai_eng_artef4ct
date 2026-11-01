"""Ferramentas determinísticas de negócio e fallback SQL Read-Only para o agente da Empório da Música."""

from __future__ import annotations

from datetime import date
import json
import re
import sqlite3
from typing import Any

from src.config import DB_PATH, get_reference_date
from src.database import digits_only, get_connection, init_database, normalize_text
from src.schemas import (
    ExpiredPromotionInfo,
    InstallmentOption,
    OrderDetailResponse,
    OrderItemDetail,
    PaymentAndShippingSimulation,
    ProductDetailResponse,
    ProductSummary,
    ReturnEligibility,
)
from src.shipping import calculate_shipping

# Mapeamento de sinônimos e plurais para garantir recall 100% entre categorias e produtos
TERM_SYNONYMS: dict[str, list[str]] = {
    "violoes": ["violao", "violoes"],
    "violao": ["violao", "violoes"],
    "guitarras": ["guitarra", "guitarras"],
    "guitarra": ["guitarra", "guitarras"],
    "baixos": ["baixo", "baixos", "contrabaixo"],
    "baixo": ["baixo", "baixos", "contrabaixo"],
    "contrabaixo": ["baixo", "baixos", "contrabaixo"],
    "baterias": ["bateria", "baterias", "percussao"],
    "bateria": ["bateria", "baterias", "percussao"],
    "teclados": ["teclado", "teclados", "piano", "sintetizador", "arranjador"],
    "teclado": ["teclado", "teclados", "piano"],
    "pianos": ["piano", "pianos", "teclado"],
    "piano": ["piano", "pianos"],
    "ukuleles": ["ukulele", "ukuleles"],
    "ukulele": ["ukulele", "ukuleles"],
    "sopro": ["sopro", "flauta", "clarinete", "saxofone", "oboe", "trompete", "trombone", "tuba", "trompa"],
    "violino": ["violino", "viola", "violoncelo", "orquestrais"],
    "aco": ["steel", "aco"],
    "steel": ["steel", "aco"],
    "nylon": ["nylon", "classico"],
}

OUT_OF_SCOPE_ACCESSORIES: dict[str, str] = {
    "encordoamento": "cordas avulsas/encordoamentos",
    "cordas avulsas": "cordas avulsas",
    "palheta": "palhetas",
    "palhetas": "palhetas",
    "cabo": "cabos",
    "cabos": "cabos",
    "case": "cases/estojos",
    "cases": "cases/estojos",
    "bag": "bags/capas",
    "capa": "capas",
    "pedal": "pedais de efeito",
    "pedais": "pedais de efeito",
    "pedaleira": "pedaleiras",
    "amplificador": "amplificadores/cubos",
    "amplificadores": "amplificadores/cubos",
    "cubo": "amplificadores/cubos",
    "correia": "correias",
    "capotraste": "capotrastes",
    "suporte": "suportes/estantes",
}

ORDER_STATUS_PT: dict[str, str] = {
    "delivered": "Entregue",
    "shipped": "Enviado / Em trânsito",
    "confirmed": "Confirmado (aguardando postagem)",
    "pending": "Pendente (aguardando confirmação de pagamento)",
    "cancelled": "Cancelado",
}


def _row_to_product_summary(row: sqlite3.Row) -> ProductSummary:
    try:
        specs = json.loads(row["specs_json"]) if row["specs_json"] else {}
    except json.JSONDecodeError:
        specs = {}

    return ProductSummary(
        product_id=int(row["product_id"]),
        name=row["name"],
        category_id=int(row["category_id"]),
        category_name=row["category_name"],
        status=row["status"],
        availability_label=row["availability_label"],
        stock_quantity=int(row["stock_quantity"]),
        original_price_brl=float(row["original_price_brl"]),
        active_discount_percent=float(row["active_discount_percent"]),
        promotion_description=row["promotion_description"],
        final_price_brl=float(row["final_price_brl"]),
        pix_price_brl=float(row["pix_price_brl"]),
        pix_discount_applied=bool(row["pix_discount_applied"]),
        specs=specs,
        description=row["description"],
    )


def _detect_accessory_inquiry(text_norm: str) -> str | None:
    tokens = set(re.findall(r"[a-z0-9]+", text_norm))
    for key, label in OUT_OF_SCOPE_ACCESSORIES.items():
        if key in tokens or (len(key.split()) > 1 and key in text_norm):
            return (
                f"Atenção (Seção 1 e 7.1 - Escopo): A Empório da Música trabalha EXCLUSIVAMENTE com "
                f"instrumentos musicais e NÃO comercializa acessórios como {label} (cordas avulsas, "
                f"palhetas, cabos, cases, pedais ou amplificadores). Redirecione educadamente o cliente."
            )
    return None


def buscar_produtos(
    termo_busca: str = "",
    categoria: str = "",
    preco_max: float = 0.0,
    preco_min: float = 0.0,
    tipo_corda: str = "",
    apenas_eletricos: bool = False,
    apenas_em_promocao: bool = False,
    db_path: Any = DB_PATH,
) -> dict[str, Any]:
    """
    Busca instrumentos musicais no catálogo da Empório da Música com filtros de categoria, faixa de preço,
    tipo de corda (nylon ou aço/steel), captação elétrica e promoções ativas.
    Separa automaticamente os produtos disponíveis em estoque dos produtos sem estoque ou descontinuados.

    Args:
        termo_busca: Termo livre para buscar no nome, marca, modelo ou descrição (ex: 'Yamaha', 'dreadnought', 'iniciante').
        categoria: Nome da categoria (ex: 'Violões', 'Guitarras', 'Baixos', 'Baterias', 'Teclados', 'Ukuleles').
        preco_max: Preço máximo em R$ (considera o preço final com promoção ativa, se houver). Use 0 para sem limite.
        preco_min: Preço mínimo em R$. Use 0 para sem limite.
        tipo_corda: Filtro opcional por encordoamento do instrumento ('nylon' ou 'aco'/'steel').
        apenas_eletricos: Se True, filtra apenas instrumentos eletroacústicos ou elétricos.
        apenas_em_promocao: Se True, retorna apenas produtos com promoção ativa no momento.
    """
    init_database(db_path=db_path)
    conn = get_connection(db_path=db_path, readonly=True)

    combined_query_norm = normalize_text(f"{termo_busca} {categoria}")
    accessory_alert = _detect_accessory_inquiry(combined_query_norm)

    rows = conn.execute("SELECT * FROM v_products_enriched ORDER BY final_price_brl ASC").fetchall()
    conn.close()

    cat_norm = normalize_text(categoria)
    cat_variants = TERM_SYNONYMS.get(cat_norm, [cat_norm]) if cat_norm else []

    raw_tokens = [
        t
        for t in re.findall(r"[a-z0-9-]+", normalize_text(termo_busca))
        if t not in ("de", "da", "do", "para", "com", "ate", "em", "um", "uma", "o", "a", "os", "as")
    ]

    corda_norm = normalize_text(tipo_corda)
    if corda_norm in ("aco", "steel"):
        corda_target = "steel"
    elif corda_norm == "nylon":
        corda_target = "nylon"
    else:
        corda_target = ""

    matched: list[ProductSummary] = []
    for row in rows:
        haystack = f"{row['name_norm']} {row['category_name_norm']} {row['description_norm']}"

        # Filtro de categoria
        if cat_variants:
            if not any(v in row["category_name_norm"] or v in row["name_norm"] for v in cat_variants):
                continue

        # Filtro de tokens de busca livre (com expansão de sinônimos singular/plural)
        if raw_tokens:
            token_ok = True
            for tok in raw_tokens:
                variants = TERM_SYNONYMS.get(tok, [tok])
                if not any(v in haystack for v in variants):
                    token_ok = False
                    break
            if not token_ok:
                continue

        # Filtro de corda (nylon vs steel/aço)
        if corda_target:
            if row["spec_strings"] != corda_target and corda_target not in haystack:
                continue

        # Filtro de instrumento elétrico / eletroacústico
        if apenas_eletricos:
            is_elec = (
                row["spec_electronics"] == "yes"
                or row["category_id"] in (1, 2, 4)
                or "eletrico" in haystack
                or "eletroacustico" in haystack
                or "eletronica" in haystack
            )
            if not is_elec:
                continue

        # Filtro de promoção ativa
        if apenas_em_promocao and float(row["active_discount_percent"]) <= 0:
            continue

        # Filtro de preço (considera final_price_brl e também original_price_brl)
        final_p = float(row["final_price_brl"])
        if preco_max > 0 and final_p > preco_max:
            continue
        if preco_min > 0 and final_p < preco_min:
            continue

        matched.append(_row_to_product_summary(row))

    disponiveis = [p for p in matched if p.availability_label == "disponivel"]
    indisponiveis = [p for p in matched if p.availability_label != "disponivel"]

    empty_category_note = None
    if not matched and any(
        w in combined_query_norm
        for w in ("sopro", "flauta", "sax", "saxofone", "clarinete", "trompete", "trombone", "violino", "violoncelo", "orquestr")
    ):
        empty_category_note = (
            "As categorias de Instrumentos de Sopro (Madeiras/Metais) e Cordas Orquestrais existem no cadastro "
            "da loja, mas estão sem modelos disponíveis em estoque no momento."
        )

    return {
        "total_disponiveis": len(disponiveis),
        "total_indisponiveis_ou_descontinuados": len(indisponiveis),
        "alerta_acessorio_fora_escopo": accessory_alert,
        "alerta_categoria_sem_estoque": empty_category_note,
        "orientacao_politica_7_3": (
            "Apresente como opções disponíveis APENAS os itens em `produtos_disponiveis`. "
            "Os itens em `produtos_indisponiveis_ou_descontinuados` NÃO devem ser ofertados para venda imediata "
            "(informe o status caso o cliente pergunte por eles)."
        ),
        "produtos_disponiveis": [p.model_dump() for p in disponiveis],
        "produtos_indisponiveis_ou_descontinuados": [p.model_dump() for p in indisponiveis],
    }


def obter_detalhes_produto(
    produto_id_ou_nome: str,
    db_path: Any = DB_PATH,
) -> dict[str, Any]:
    """
    Obtém a ficha completa de um instrumento específico pelo ID ou pelo nome/modelo (ex: 'Takamine GD20', '95', 'Giannini GF-3D').
    Retorna preço de tabela, promoções ativas, histórico de promoções expiradas (Seção 7.3), valor no PIX,
    status de estoque e até 3 produtos similares disponíveis caso o item esteja sem estoque ou descontinuado.

    Args:
        produto_id_ou_nome: ID numérico do produto ou nome/modelo do instrumento.
    """
    init_database(db_path=db_path)
    conn = get_connection(db_path=db_path, readonly=True)

    query_clean = produto_id_ou_nome.strip()
    target_row: sqlite3.Row | None = None

    if query_clean.isdigit():
        target_row = conn.execute(
            "SELECT * FROM v_products_enriched WHERE product_id = ?",
            (int(query_clean),),
        ).fetchone()

    if target_row is None:
        q_norm = normalize_text(query_clean)
        all_rows = conn.execute("SELECT * FROM v_products_enriched").fetchall()
        # 1. Substring exata no nome normalizado
        for r in all_rows:
            if q_norm and q_norm in r["name_norm"]:
                target_row = r
                break
        # 2. Match por todos os tokens
        if target_row is None and q_norm:
            tokens = [t for t in re.findall(r"[a-z0-9-]+", q_norm) if len(t) > 1]
            best_row = None
            best_score = 0
            for r in all_rows:
                score = sum(1 for t in tokens if t in r["name_norm"] or t in r["description_norm"])
                if score > best_score:
                    best_score = score
                    best_row = r
            if best_row is not None and best_score > 0:
                target_row = best_row

    if target_row is None:
        conn.close()
        accessory_msg = _detect_accessory_inquiry(normalize_text(query_clean))
        return ProductDetailResponse(
            found=False,
            message=(
                accessory_msg
                or f"Nenhum instrumento encontrado para '{produto_id_ou_nome}' no catálogo da Empório da Música."
            ),
            policy_alert=accessory_msg,
        ).model_dump()

    product = _row_to_product_summary(target_row)

    # Busca promoções expiradas (is_active = 0) para transparência (Seção 7.3)
    expired_rows = conn.execute(
        "SELECT promotion_id, discount_percent, description FROM promotions WHERE product_id = ? AND is_active = 0",
        (product.product_id,),
    ).fetchall()
    expired_promos = [
        ExpiredPromotionInfo(
            promotion_id=int(er["promotion_id"]),
            discount_percent=float(er["discount_percent"]),
            description=er["description"],
        )
        for er in expired_rows
    ]

    # Busca similares disponíveis na mesma categoria
    similar_rows = conn.execute(
        """
        SELECT * FROM v_products_enriched
        WHERE category_id = ?
          AND product_id != ?
          AND status = 'active'
          AND stock_quantity > 0
        ORDER BY ABS(final_price_brl - ?) ASC
        LIMIT 3
        """,
        (product.category_id, product.product_id, product.final_price_brl),
    ).fetchall()
    conn.close()

    similares = [_row_to_product_summary(sr) for sr in similar_rows]

    policy_alert: str | None = None
    if product.availability_label == "sem_estoque":
        policy_alert = (
            "ALERTA POLÍTICA 7.3 (Produto fora de estoque): Este produto está ativo no catálogo, mas com "
            "estoque ZERO no momento. Informe que está temporariamente indisponível e sugira os modelos "
            "disponíveis listados em `similar_available_products`."
        )
    elif product.availability_label == "descontinuado":
        policy_alert = (
            "ALERTA POLÍTICA 7.3 (Produto descontinuado): Este produto foi DESCONTINUADO e não faz mais "
            "parte do catálogo comercializável (mesmo que conste saldo residual no banco). Informe ao cliente "
            "que saiu de linha e ofereça os modelos equivalentes em `similar_available_products`."
        )
    elif product.availability_label == "em_breve":
        policy_alert = (
            "ALERTA (Em breve / Pré-lançamento): Este produto está com status 'coming_soon' e ainda não está "
            "liberado para pronta-entrega. Informe o cliente e ofereça alternativas disponíveis."
        )
    elif product.active_discount_percent > 0:
        policy_alert = (
            f"POLÍTICA 6.2 (Promoção Ativa - {product.promotion_description}): Sempre apresente o preço "
            f"original (R$ {product.original_price_brl:.2f}), o percentual de desconto ({product.active_discount_percent:.0f}%) "
            f"e o preço promocional (R$ {product.final_price_brl:.2f}). Lembre-se: o desconto de 5% do PIX "
            "NÃO é cumulativo com promoções ativas."
        )
    elif expired_promos:
        promo_names = ", ".join(f"{ep.description} ({ep.discount_percent:.0f}%)" for ep in expired_promos)
        policy_alert = (
            f"POLÍTICA 7.3 (Promoção expirada): Este produto possui histórico de promoção encerrada ({promo_names}). "
            f"Não há promoção ativa hoje: o preço vigente de tabela é R$ {product.original_price_brl:.2f} "
            f"(ou R$ {product.pix_price_brl:.2f} com 5% de desconto à vista no PIX)."
        )

    return ProductDetailResponse(
        found=True,
        message=f"Detalhes do produto '{product.name}' carregados com sucesso.",
        product=product,
        expired_promotions=expired_promos,
        policy_alert=policy_alert,
        similar_available_products=similares,
    ).model_dump()


def simular_pagamento_e_frete(
    valor_brl: float = 0.0,
    produto_id_ou_nome: str = "",
    tem_promocao_ativa: bool = False,
    percentual_desconto_ativo: float = 0.0,
    destino_cep_ou_cidade: str = "",
    categoria_id: int = 5,
    db_path: Any = DB_PATH,
) -> dict[str, Any]:
    """
    Simula todas as formas de pagamento (PIX com verificação de não-cumulatividade, débito, boleto e
    parcelamento sem juros de 1x a 12x conforme as parcelas mínimas da Seção 3.1) e calcula o frete
    (Motoboy em Campo Grande ou API do Melhor Envio / Contingência para outras cidades).

    Args:
        valor_brl: Valor do produto ou pedido em R$ (opcional se `produto_id_ou_nome` for informado).
        produto_id_ou_nome: Nome ou ID do produto para carregar automaticamente preço, promoção ativa e categoria.
        tem_promocao_ativa: Indica se o valor já possui promoção ativa (bloqueia os 5% adicionais do PIX).
        percentual_desconto_ativo: Percentual de desconto ativo (0 a 100), caso queira aplicar sobre `valor_brl`.
        destino_cep_ou_cidade: CEP (ex: '79002-070', '01310-100') ou nome da cidade (ex: 'Campo Grande', 'Dourados', 'São Paulo') para cotar frete.
        categoria_id: ID da categoria do instrumento (1 a 9) para estimativa de cubagem no frete.
    """
    original_amount = float(valor_brl)
    has_promo = bool(tem_promocao_ativa)
    discount_pct = float(percentual_desconto_ativo)
    cat_id = int(categoria_id) if categoria_id else 5

    if produto_id_ou_nome.strip():
        detail = obter_detalhes_produto(produto_id_ou_nome, db_path=db_path)
        if detail.get("found") and detail.get("product"):
            prod = detail["product"]
            original_amount = float(prod["original_price_brl"])
            discount_pct = float(prod["active_discount_percent"])
            has_promo = discount_pct > 0
            cat_id = int(prod["category_id"])

    if has_promo and discount_pct > 0:
        effective_amount = round(original_amount * (1.0 - discount_pct / 100.0), 2)
    else:
        effective_amount = round(original_amount, 2)

    # Regra Seção 6.2: O desconto de PIX (5%) não se aplica sobre preços já promocionais
    if has_promo:
        pix_amount = effective_amount
        pix_applied = False
        pix_explanation = (
            "Conforme a Seção 6.2 da política da loja, promoções não são cumulativas: "
            "o desconto de 5% do PIX não se aplica sobre preços que já estão em promoção."
        )
    else:
        pix_amount = round(effective_amount * 0.95, 2)
        pix_applied = True
        pix_explanation = "Desconto de 5% aplicado para pagamento à vista via PIX sobre o preço de tabela (Seção 3)."

    # Regras de parcelamento escalonado (Seção 3.1):
    # - Até 3x: sem juros, parcela mínima de R$ 50,00 (1x sempre permitido)
    # - De 4x a 6x: sem juros, parcela mínima de R$ 80,00
    # - De 7x a 12x: sem juros, parcela mínima de R$ 100,00
    installments_list: list[InstallmentOption] = []
    for n in range(1, 13):
        inst_val = round(effective_amount / n, 2)
        if n == 1:
            min_rule = 0.0
        elif n <= 3:
            min_rule = 50.0
        elif n <= 6:
            min_rule = 80.0
        else:
            min_rule = 100.0

        if inst_val >= min_rule:
            installments_list.append(
                InstallmentOption(
                    installments=n,
                    installment_value_brl=inst_val,
                    total_brl=effective_amount,
                    min_installment_rule_brl=min_rule,
                )
            )

    max_inst = installments_list[-1].installments if installments_list else 1
    allows_combined = effective_amount > 2000.0

    shipping_result = None
    if destino_cep_ou_cidade.strip():
        shipping_result = calculate_shipping(
            destination=destino_cep_ou_cidade.strip(),
            order_value_brl=effective_amount,
            category_id=cat_id,
        )

    return PaymentAndShippingSimulation(
        original_amount_brl=original_amount,
        has_active_promotion=has_promo,
        discount_percent=discount_pct,
        effective_amount_brl=effective_amount,
        pix_amount_brl=pix_amount,
        pix_discount_applied=pix_applied,
        pix_rule_explanation=pix_explanation,
        debit_amount_brl=effective_amount,
        boleto_amount_brl=effective_amount,
        max_installments=max_inst,
        installment_options=installments_list,
        allows_combined_payment=allows_combined,
        combined_payment_rule=(
            "Permitida combinação de formas de pagamento (ex.: PIX + cartão) por ser compra acima de R$ 2.000,00 (Seção 3.1)."
            if allows_combined
            else "Combinação de formas de pagamento (ex.: PIX + cartão) é permitida apenas para compras acima de R$ 2.000,00 (Seção 3.1)."
        ),
        shipping=shipping_result,
    ).model_dump()


def _mask_email(email: str) -> str:
    if "@" not in email:
        return email
    user, domain = email.split("@", 1)
    if len(user) <= 2:
        return f"{user[0]}***@{domain}"
    return f"{user[:2]}***{user[-1]}@{domain}"


def _evaluate_return_eligibility(
    order_status: str,
    order_date_str: str,
    estimated_delivery_str: str | None,
    ref_date: date,
) -> ReturnEligibility:
    order_dt = date.fromisoformat(order_date_str)
    days_since_order = (ref_date - order_dt).days

    delivery_dt = date.fromisoformat(estimated_delivery_str) if estimated_delivery_str else None
    days_since_delivery = (ref_date - delivery_dt).days if delivery_dt else None

    if order_status == "cancelled":
        return ReturnEligibility(
            reference_date=ref_date.isoformat(),
            days_since_order=days_since_order,
            days_since_delivery_or_estimate=days_since_delivery,
            can_cancel_immediately=False,
            repentance_7d_eligible=False,
            repentance_explanation="O pedido já se encontra cancelado no sistema.",
            preference_exchange_7d_eligible=False,
            defect_store_exchange_30d_eligible=False,
            defect_explanation="Pedido cancelado.",
            legal_warranty_90d_active=False,
            non_eligible_exceptions_warning="Não aplicável (pedido cancelado).",
        )

    if order_status in ("pending", "confirmed"):
        return ReturnEligibility(
            reference_date=ref_date.isoformat(),
            days_since_order=days_since_order,
            days_since_delivery_or_estimate=None,
            can_cancel_immediately=True,
            repentance_7d_eligible=True,
            repentance_explanation=(
                "O pedido ainda não foi despachado (status: "
                f"{ORDER_STATUS_PT.get(order_status, order_status)}). O cliente pode solicitar o cancelamento "
                "imediato sem custos ou exercer o Direito de Arrependimento em até 7 dias corridos após o recebimento (Seção 4.1)."
            ),
            preference_exchange_7d_eligible=True,
            defect_store_exchange_30d_eligible=True,
            defect_explanation="Caso apresente defeito após a entrega, terá 30 dias corridos para troca direta na loja (Seção 4.2).",
            legal_warranty_90d_active=True,
            non_eligible_exceptions_warning=(
                "Exceções (Seção 4.4): Não são elegíveis para troca instrumentos com personalização/setup sob encomenda, "
                "itens de liquidação 'venda final' e boquilhas de sopro por higiene."
            ),
        )

    if order_status == "shipped":
        return ReturnEligibility(
            reference_date=ref_date.isoformat(),
            days_since_order=days_since_order,
            days_since_delivery_or_estimate=days_since_delivery,
            can_cancel_immediately=False,
            repentance_7d_eligible=True,
            repentance_explanation=(
                "O pedido está em trânsito. O prazo de 7 dias corridos do Direito de Arrependimento (Seção 4.1) "
                "passa a contar a partir da data efetiva de recebimento do produto, com frete de devolução por conta da loja."
            ),
            preference_exchange_7d_eligible=True,
            defect_store_exchange_30d_eligible=True,
            defect_explanation="Troca por defeito na loja disponível em até 30 dias corridos após a compra/recebimento (Seção 4.2).",
            legal_warranty_90d_active=True,
            non_eligible_exceptions_warning=(
                "O produto deve estar na embalagem original, sem sinais de uso, com todos os acessórios e manuais (Seção 4.1)."
            ),
        )

    # Status == delivered
    effective_days_delivered = days_since_delivery if days_since_delivery is not None else days_since_order
    repentance_ok = 0 <= effective_days_delivered <= 7
    defect_30d_ok = 0 <= days_since_order <= 30 or (days_since_delivery is not None and 0 <= days_since_delivery <= 30)
    warranty_90d_ok = 0 <= effective_days_delivered <= 90

    if repentance_ok:
        rep_msg = (
            f"ELEGÍVEL para Direito de Arrependimento (Seção 4.1) e Troca por Preferência (Seção 4.3): "
            f"foram decorridos {effective_days_delivered} dias desde a entrega ({estimated_delivery_str}), dentro "
            "do limite de 7 dias corridos. Frete de devolução por conta da loja e reembolso em até 10 dias úteis."
        )
    else:
        rep_msg = (
            f"FORA DO PRAZO de 7 dias corridos para Direito de Arrependimento (Seção 4.1) e Troca por Preferência (Seção 4.3): "
            f"o pedido foi entregue em {estimated_delivery_str} ({effective_days_delivered} dias atrás em relação à data de referência {ref_date.isoformat()})."
        )

    if defect_30d_ok:
        def_msg = (
            f"ELEGÍVEL para Troca por Defeito diretamente na loja (Seção 4.2), pois está dentro do prazo de 30 dias corridos "
            f"(compra em {order_date_str}, entrega em {estimated_delivery_str})."
        )
    elif warranty_90d_ok:
        def_msg = (
            f"Prazo de 30 dias para troca direta na loja por defeito já expirou ({days_since_order} dias desde a compra), "
            f"PORÉM o produto ainda está coberto pela Garantia Legal de 90 dias do CDC (Seção 8.1 — {effective_days_delivered} dias desde o recebimento) "
            "e pela Garantia do Fabricante (6 meses a 2 anos, Seção 8.2). A Empório da Música pode intermediar o acionamento junto ao fabricante (Seção 4.2)."
        )
    else:
        def_msg = (
            f"Os prazos de 30 dias na loja (Seção 4.2) e de 90 dias da Garantia Legal (Seção 8.1) já expiraram "
            f"({effective_days_delivered} dias desde a entrega). Verificar se a Garantia do Fabricante (6 meses a 2 anos, Seção 8.2) "
            "ainda está vigente no certificado do produto; a loja pode intermediar o contato."
        )

    return ReturnEligibility(
        reference_date=ref_date.isoformat(),
        days_since_order=days_since_order,
        days_since_delivery_or_estimate=days_since_delivery,
        can_cancel_immediately=False,
        repentance_7d_eligible=repentance_ok,
        repentance_explanation=rep_msg,
        preference_exchange_7d_eligible=repentance_ok,
        defect_store_exchange_30d_eligible=defect_30d_ok,
        defect_explanation=def_msg,
        legal_warranty_90d_active=warranty_90d_ok,
        non_eligible_exceptions_warning=(
            "Condições (Seções 4.1 a 4.4): Embalagem original, sem sinais de mau uso/quedas/umidade. "
            "Não são elegíveis itens personalizados/setup sob encomenda, liquidação 'venda final' ou boquilhas de sopro."
        ),
    )


def consultar_pedido(
    order_id: int = 0,
    identificador_cliente: str = "",
    db_path: Any = DB_PATH,
    reference_date: date | None = None,
) -> dict[str, Any]:
    """
    Consulta status, código de rastreamento, itens comprados e elegibilidade completa para troca,
    devolução por arrependimento (7 dias) ou defeito (30 dias / garantia legal de 90 dias) de um pedido.
    Pode buscar pelo número do pedido (`order_id`) ou por nome, e-mail, telefone ou código de rastreio do cliente.

    Args:
        order_id: Número identificador do pedido (ex: 1 a 20). Use 0 se quiser buscar por `identificador_cliente`.
        identificador_cliente: Nome do cliente, e-mail, telefone ou código de rastreio (ex: 'BRAB1234567BR').
    """
    init_database(db_path=db_path)
    conn = get_connection(db_path=db_path, readonly=True)
    ref_dt = reference_date or get_reference_date()

    order_rows: list[sqlite3.Row] = []
    if order_id and int(order_id) > 0:
        row = conn.execute(
            """
            SELECT o.*, c.name AS customer_name, c.email AS customer_email, c.city AS customer_city, c.phone AS customer_phone
            FROM orders o
            JOIN customers c ON c.customer_id = o.customer_id
            WHERE o.order_id = ?
            """,
            (int(order_id),),
        ).fetchall()
        order_rows.extend(row)

    if not order_rows and identificador_cliente.strip():
        ident_clean = identificador_cliente.strip()
        ident_norm = normalize_text(ident_clean)
        ident_digits = digits_only(ident_clean)

        if ident_digits and len(ident_digits) <= 3 and ident_clean.isdigit():
            # Caso o modelo tenha passado o order_id dentro de identificador_cliente
            order_rows = conn.execute(
                """
                SELECT o.*, c.name AS customer_name, c.email AS customer_email, c.city AS customer_city, c.phone AS customer_phone
                FROM orders o
                JOIN customers c ON c.customer_id = o.customer_id
                WHERE o.order_id = ?
                """,
                (int(ident_digits),),
            ).fetchall()

        if not order_rows:
            all_orders = conn.execute(
                """
                SELECT o.*, c.name AS customer_name, c.name_norm, c.email AS customer_email, c.email_norm,
                       c.city AS customer_city, c.phone AS customer_phone, c.phone_digits
                FROM orders o
                JOIN customers c ON c.customer_id = o.customer_id
                ORDER BY o.order_date DESC
                """
            ).fetchall()
            for r in all_orders:
                tracking = (r["tracking_code"] or "").lower()
                if (
                    (ident_norm and ident_norm in r["name_norm"])
                    or (ident_norm and ident_norm == r["email_norm"])
                    or (ident_norm and tracking and ident_norm == tracking)
                    or (len(ident_digits) >= 8 and ident_digits in r["phone_digits"])
                ):
                    order_rows.append(r)

    if not order_rows:
        conn.close()
        return {
            "found": False,
            "message": (
                "Nenhum pedido encontrado para os dados informados. Solicite ao cliente o número do pedido "
                "(order_id), o nome completo ou o e-mail/telefone cadastrado."
            ),
            "orders": [],
        }

    results: list[dict[str, Any]] = []
    for orow in order_rows:
        oid = int(orow["order_id"])
        item_rows = conn.execute(
            """
            SELECT oi.quantity, p.product_id, p.name AS product_name, p.price_brl, c.name AS category_name
            FROM order_items oi
            JOIN products p ON p.product_id = oi.product_id
            JOIN categories c ON c.category_id = p.category_id
            WHERE oi.order_id = ?
            """,
            (oid,),
        ).fetchall()

        items = [
            OrderItemDetail(
                product_id=int(ir["product_id"]),
                product_name=ir["product_name"],
                category_name=ir["category_name"],
                quantity=int(ir["quantity"]),
                unit_price_catalog_brl=float(ir["price_brl"]),
            )
            for ir in item_rows
        ]

        eligibility = _evaluate_return_eligibility(
            order_status=orow["status"],
            order_date_str=orow["order_date"],
            estimated_delivery_str=orow["estimated_delivery"],
            ref_date=ref_dt,
        )

        detail = OrderDetailResponse(
            order_id=oid,
            customer_id=int(orow["customer_id"]),
            customer_name=orow["customer_name"],
            customer_city=orow["customer_city"],
            customer_email_masked=_mask_email(orow["customer_email"]),
            order_date=orow["order_date"],
            status=orow["status"],
            status_pt_br=ORDER_STATUS_PT.get(orow["status"], orow["status"]),
            total_brl=float(orow["total_brl"]),
            payment_method=orow["payment_method"],
            tracking_code=orow["tracking_code"],
            estimated_delivery=orow["estimated_delivery"],
            notes=orow["notes"],
            items=items,
            return_eligibility=eligibility,
        )
        results.append(detail.model_dump())

    conn.close()
    return {
        "found": True,
        "total_orders_found": len(results),
        "reference_date_used": ref_dt.isoformat(),
        "lgpd_notice": (
            "Política Seção 9 (LGPD): Confirme que está falando com o titular antes de expor dados sensíveis "
            "e utilize apenas as informações necessárias para o atendimento."
        ),
        "orders": results,
    }


FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|ATTACH|DETACH|PRAGMA|VACUUM)\b",
    re.IGNORECASE,
)


def executar_sql_leitura(
    sql_query: str,
    db_path: Any = DB_PATH,
) -> dict[str, Any]:
    """
    Executa uma consulta SQL somente-leitura (SELECT) no banco SQLite da Empório da Música.
    Use como fallback apenas para perguntas analíticas ou cruzamentos que as ferramentas principais não cobrirem.
    Tabelas disponíveis: `v_products_enriched`, `products`, `categories`, `promotions`, `orders`, `order_items`, `customers`.

    Args:
        sql_query: Consulta SQL iniciada obrigatoriamente por SELECT.
    """
    cleaned = sql_query.strip().rstrip(";")
    if not cleaned.upper().startswith(("SELECT", "WITH")):
        return {
            "success": False,
            "error": "Apenas consultas iniciadas por SELECT ou WITH são permitidas.",
            "rows": [],
        }

    if FORBIDDEN_SQL_PATTERN.search(cleaned):
        return {
            "success": False,
            "error": "Comando SQL bloqueado por conter palavras-chave de modificação ou administração.",
            "rows": [],
        }

    if ";" in cleaned:
        return {
            "success": False,
            "error": "Múltiplas instruções SQL não são permitidas.",
            "rows": [],
        }

    init_database(db_path=db_path)
    conn = get_connection(db_path=db_path, readonly=True)
    try:
        cursor = conn.execute(cleaned)
        rows = [dict(r) for r in cursor.fetchmany(50)]
        conn.close()
        return {
            "success": True,
            "row_count": len(rows),
            "rows": rows,
        }
    except sqlite3.Error as exc:
        conn.close()
        return {
            "success": False,
            "error": f"Erro ao executar SQL: {exc}",
            "rows": [],
        }
