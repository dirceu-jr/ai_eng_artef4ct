"""Testes unitários para o módulo de frete (Motoboy CG, API Melhor Envio e Fallback)."""

from unittest.mock import patch

from src.shipping import calculate_shipping


def test_campo_grande_free_shipping_above_500() -> None:
    res = calculate_shipping(destination="Campo Grande", order_value_brl=849.0, category_id=5)
    assert res.is_local_campo_grande is True
    assert res.source == "regra_local_motoboy"
    assert len(res.options) == 1
    assert res.options[0].price_brl == 0.0
    assert res.options[0].delivery_days_min == 1
    assert res.options[0].delivery_days_max == 3


def test_campo_grande_fixed_fee_under_500_by_cep() -> None:
    res = calculate_shipping(destination="79002-070", order_value_brl=429.9, category_id=5)
    assert res.is_local_campo_grande is True
    assert res.source == "regra_local_motoboy"
    assert res.options[0].price_brl == 35.0


def test_other_city_contingency_fallback_and_large_item_warning() -> None:
    res = calculate_shipping(destination="01310-100", order_value_brl=4500.0, category_id=3, token_override="")
    assert res.is_local_campo_grande is False
    assert res.source == "tabela_contingencia_loja"
    assert res.large_item_warning is not None
    assert "grande porte" in res.large_item_warning
    carriers = {opt.service_name for opt in res.options}
    assert "PAC (Correios)" in carriers
    assert "SEDEX (Correios)" in carriers
    assert "Jadlog (.package)" in carriers


def test_melhor_envio_api_integration_mocked() -> None:
    fake_api_response = [
        {
            "id": 1,
            "name": "PAC",
            "price": "68.50",
            "custom_price": "68.50",
            "delivery_range": {"min": 6, "max": 10},
            "company": {"name": "Correios"},
        },
        {
            "id": 3,
            "name": ".Package",
            "price": "74.90",
            "custom_price": "74.90",
            "delivery_range": {"min": 4, "max": 7},
            "company": {"name": "Jadlog"},
        },
    ]

    with patch("src.shipping.httpx.Client") as mock_client_cls:
        mock_instance = mock_client_cls.return_value.__enter__.return_value
        mock_instance.post.return_value.status_code = 200
        mock_instance.post.return_value.json.return_value = fake_api_response

        res = calculate_shipping(
            destination="79804-970",  # Dourados-MS
            order_value_brl=2199.0,
            category_id=5,
            token_override="fake-oauth-token",
        )

        assert res.source == "melhor_envio_api"
        assert len(res.options) == 2
        assert res.options[0].price_brl == 68.50
        assert res.options[1].carrier == "Jadlog"

