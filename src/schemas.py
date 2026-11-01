"""Schemas Pydantic para entradas e saídas estruturadas das ferramentas do agente."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class ProductSummary(BaseModel):
    """Resumo enriquecido de um produto do catálogo."""

    product_id: int
    name: str
    category_id: int
    category_name: str
    status: Literal["active", "discontinued", "coming_soon"]
    availability_label: Literal["disponivel", "sem_estoque", "descontinuado", "em_breve"]
    stock_quantity: int
    original_price_brl: float
    active_discount_percent: float = 0.0
    promotion_description: str | None = None
    final_price_brl: float
    pix_price_brl: float
    pix_discount_applied: bool
    specs: dict[str, Any] = Field(default_factory=dict)
    description: str


class ExpiredPromotionInfo(BaseModel):
    """Informação sobre promoção encerrada para transparência com o cliente (Seção 7.3)."""

    promotion_id: int
    discount_percent: float
    description: str


class ProductDetailResponse(BaseModel):
    """Resposta detalhada de um produto específico, com alternativas se indisponível."""

    found: bool
    message: str
    product: ProductSummary | None = None
    expired_promotions: list[ExpiredPromotionInfo] = Field(default_factory=list)
    policy_alert: str | None = None
    similar_available_products: list[ProductSummary] = Field(default_factory=list)


class InstallmentOption(BaseModel):
    """Opção de parcelamento sem juros no cartão de crédito (Seção 3.1)."""

    installments: int
    installment_value_brl: float
    total_brl: float
    min_installment_rule_brl: float


class ShippingQuoteOption(BaseModel):
    """Modalidade individual de frete calculada."""

    service_name: str
    carrier: str
    price_brl: float
    delivery_days_min: int
    delivery_days_max: int
    includes_insurance: bool = True
    includes_tracking: bool = True
    notes: str | None = None


class ShippingCalculationResult(BaseModel):
    """Resultado do cálculo de frete (Motoboy CG, API Melhor Envio ou Contingência Local)."""

    destination: str
    postal_code_clean: str | None = None
    is_local_campo_grande: bool
    source: Literal["regra_local_motoboy", "melhor_envio_api", "tabela_contingencia_loja"]
    large_item_warning: str | None = None
    options: list[ShippingQuoteOption] = Field(default_factory=list)


class PaymentAndShippingSimulation(BaseModel):
    """Resultado completo da simulação financeira e logística."""

    original_amount_brl: float
    has_active_promotion: bool
    discount_percent: float
    effective_amount_brl: float
    pix_amount_brl: float
    pix_discount_applied: bool
    pix_rule_explanation: str
    debit_amount_brl: float
    boleto_amount_brl: float
    max_installments: int
    installment_options: list[InstallmentOption]
    allows_combined_payment: bool
    combined_payment_rule: str
    shipping: ShippingCalculationResult | None = None


class OrderItemDetail(BaseModel):
    """Item pertencente a um pedido de cliente."""

    product_id: int
    product_name: str
    category_name: str
    quantity: int
    unit_price_catalog_brl: float


class ReturnEligibility(BaseModel):
    """Análise determinística de elegibilidade de troca/devolução (Seções 4 e 8)."""

    reference_date: str
    days_since_order: int
    days_since_delivery_or_estimate: int | None
    can_cancel_immediately: bool
    repentance_7d_eligible: bool
    repentance_explanation: str
    preference_exchange_7d_eligible: bool
    defect_store_exchange_30d_eligible: bool
    defect_explanation: str
    legal_warranty_90d_active: bool
    non_eligible_exceptions_warning: str


class OrderDetailResponse(BaseModel):
    """Detalhes completos de um pedido e sua análise perante as políticas de troca."""

    order_id: int
    customer_id: int
    customer_name: str
    customer_city: str
    customer_email_masked: str
    order_date: str
    status: str
    status_pt_br: str
    total_brl: float
    payment_method: str
    tracking_code: str | None = None
    estimated_delivery: str | None = None
    notes: str | None = None
    items: list[OrderItemDetail] = Field(default_factory=list)
    return_eligibility: ReturnEligibility

