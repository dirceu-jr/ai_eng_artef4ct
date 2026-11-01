"""Testes unitários das ferramentas determinísticas de negócio e guardrails SQL."""

from datetime import date

from src.tools import (
    buscar_produtos,
    consultar_pedido,
    executar_sql_leitura,
    obter_detalhes_produto,
    simular_pagamento_e_frete,
)


def test_buscar_violoes_ate_1000_separa_giannini_sem_estoque() -> None:
    res = buscar_produtos(categoria="Violões", preco_max=1000.0)
    assert res["total_disponiveis"] > 0

    disp_ids = {p["product_id"] for p in res["produtos_disponiveis"]}
    indisp_ids = {p["product_id"] for p in res["produtos_indisponiveis_ou_descontinuados"]}

    # Giannini GF-3D (id=96, R$ 799,90) tem stock=0 -> deve ficar fora dos disponíveis!
    assert 96 not in disp_ids
    assert 96 in indisp_ids
    # Todos os disponíveis devem ter stock > 0 e final_price_brl <= 1000
    for p in res["produtos_disponiveis"]:
        assert p["stock_quantity"] > 0
        assert p["status"] == "active"
        assert p["final_price_brl"] <= 1000.0


def test_buscar_acessorios_dispara_alerta_fora_de_escopo() -> None:
    res = buscar_produtos(termo_busca="encordoamento e palhetas")
    assert res["alerta_acessorio_fora_escopo"] is not None
    assert "EXCLUSIVAMENTE com instrumentos musicais" in res["alerta_acessorio_fora_escopo"]


def test_obter_detalhes_takamine_gd20_mostra_promocao_expirada() -> None:
    res = obter_detalhes_produto("Takamine GD20")
    assert res["found"] is True
    prod = res["product"]
    assert prod["product_id"] == 95
    assert prod["original_price_brl"] == 2199.0
    assert prod["active_discount_percent"] == 0.0
    assert prod["pix_price_brl"] == 2089.05
    assert len(res["expired_promotions"]) == 1
    assert res["expired_promotions"][0]["discount_percent"] == 12.0
    assert "Promoção expirada" in res["policy_alert"]


def test_obter_detalhes_produto_descontinuado_com_estoque_sugere_similares() -> None:
    # Ibanez Bass 2X (id=136) tem stock=13 mas status='discontinued'
    res = obter_detalhes_produto("136")
    assert res["found"] is True
    assert res["product"]["availability_label"] == "descontinuado"
    assert "DESCONTINUADO" in res["policy_alert"]
    assert len(res["similar_available_products"]) > 0
    for sim in res["similar_available_products"]:
        assert sim["availability_label"] == "disponivel"


def test_simular_pagamento_pix_nao_cumulativo_e_parcelamento_escalonado() -> None:
    # Crafter HT-100 (id=90) tem promoção ativa de 18% (de R$ 2399 por R$ 1967,18)
    sim_promo = simular_pagamento_e_frete(produto_id_ou_nome="Crafter HT-100", destino_cep_ou_cidade="Campo Grande")
    assert sim_promo["has_active_promotion"] is True
    assert sim_promo["effective_amount_brl"] == 1967.18
    assert sim_promo["pix_discount_applied"] is False
    assert sim_promo["pix_amount_brl"] == 1967.18
    assert sim_promo["shipping"]["is_local_campo_grande"] is True
    assert sim_promo["shipping"]["options"][0]["price_brl"] == 0.0  # > R$ 500 -> Frete Grátis em CG

    # Teste de parcelamento escalonado para um item de R$ 450,00 sem promoção:
    # - 1x a 3x (mín R$ 50): 3x de R$ 150,00 (OK)
    # - 4x a 6x (mín R$ 80): 4x de R$ 112,50 (OK), 5x de R$ 90,00 (OK), 6x de R$ 75,00 (< 80 -> bloqueado!)
    # - 7x a 12x (mín R$ 100): todos < 100 -> bloqueados!
    sim_450 = simular_pagamento_e_frete(valor_brl=450.0)
    assert sim_450["max_installments"] == 5
    assert sim_450["allows_combined_payment"] is False


def test_consultar_pedido_prazos_arrependimento_e_defeito() -> None:
    # Pedido 7: entregue em 2026-02-17. Na data de referência 2026-02-22 (5 dias depois), é elegível aos 7 dias!
    res_within_7d = consultar_pedido(order_id=7, reference_date=date(2026, 2, 22))
    assert res_within_7d["found"] is True
    elig_7d = res_within_7d["orders"][0]["return_eligibility"]
    assert elig_7d["repentance_7d_eligible"] is True

    # Na data de referência padrão (2026-03-25), já se passaram 36 dias da entrega de 2026-02-17:
    # fora dos 7 dias (arrependimento) e dos 30 dias (troca na loja), mas dentro dos 90 dias da Garantia Legal!
    res_after_30d = consultar_pedido(order_id=7, reference_date=date(2026, 3, 25))
    elig_30d = res_after_30d["orders"][0]["return_eligibility"]
    assert elig_30d["repentance_7d_eligible"] is False
    assert elig_30d["defect_store_exchange_30d_eligible"] is False
    assert elig_30d["legal_warranty_90d_active"] is True


def test_executar_sql_leitura_bloqueia_escrita() -> None:
    ok_res = executar_sql_leitura("SELECT COUNT(*) AS total FROM products WHERE status = 'active'")
    assert ok_res["success"] is True
    assert ok_res["rows"][0]["total"] == 62

    blocked_res = executar_sql_leitura("DROP TABLE products")
    assert blocked_res["success"] is False
