"""Módulo de cálculo de frete: Regra local (Campo Grande), API v2 do Melhor Envio e Fallback Determinístico."""

from __future__ import annotations

from dataclasses import dataclass
import httpx

from src.config import (
    MELHOR_ENVIO_SANDBOX,
    MELHOR_ENVIO_TOKEN,
    MELHOR_ENVIO_USER_AGENT,
    STORE_ORIGIN_CEP,
)
from src.database import digits_only, normalize_text
from src.schemas import ShippingCalculationResult, ShippingQuoteOption


@dataclass(frozen=True)
class ShippingProfile:
    """Perfil físico estimado por categoria de instrumento para cálculo de cubagem."""

    width_cm: int
    height_cm: int
    length_cm: int
    weight_kg: float
    is_large_item: bool
    label: str


CATEGORY_SHIPPING_PROFILES: dict[int, ShippingProfile] = {
    1: ShippingProfile(width_cm=40, height_cm=12, length_cm=100, weight_kg=4.5, is_large_item=False, label="Guitarra"),
    2: ShippingProfile(width_cm=42, height_cm=12, length_cm=118, weight_kg=5.2, is_large_item=True, label="Contrabaixo"),
    3: ShippingProfile(width_cm=60, height_cm=60, length_cm=80, weight_kg=28.0, is_large_item=True, label="Bateria / Percussão"),
    4: ShippingProfile(width_cm=42, height_cm=22, length_cm=115, weight_kg=12.0, is_large_item=True, label="Teclado / Piano Digital"),
    5: ShippingProfile(width_cm=45, height_cm=16, length_cm=100, weight_kg=3.2, is_large_item=False, label="Violão"),
    6: ShippingProfile(width_cm=30, height_cm=18, length_cm=65, weight_kg=2.5, is_large_item=False, label="Sopro (Madeiras)"),
    7: ShippingProfile(width_cm=32, height_cm=22, length_cm=60, weight_kg=3.0, is_large_item=False, label="Sopro (Metais)"),
    8: ShippingProfile(width_cm=35, height_cm=18, length_cm=85, weight_kg=3.0, is_large_item=False, label="Cordas Orquestrais"),
    9: ShippingProfile(width_cm=25, height_cm=12, length_cm=65, weight_kg=1.2, is_large_item=False, label="Ukulele"),
}

DEFAULT_PROFILE = CATEGORY_SHIPPING_PROFILES[5]


def is_campo_grande_destination(destination: str) -> tuple[bool, str | None]:
    """Identifica se o destino informado (CEP ou nome de cidade) pertence à Região Metropolitana de Campo Grande."""
    clean_cep = digits_only(destination)
    norm_dest = normalize_text(destination)

    if len(clean_cep) == 8:
        # CEPs de Campo Grande/MS vão de 79000-000 a 79129-999.
        # Também aceitamos 79202-333 caso o usuário digite o CEP fictício citado no manual da loja.
        prefix3 = int(clean_cep[:3])
        if 790 <= prefix3 <= 791 or clean_cep == "79202333":
            return True, clean_cep
        return False, clean_cep

    if "campo grande" in norm_dest or norm_dest in ("cg", "campo grande ms", "campo grande - ms"):
        return True, None

    return False, (clean_cep if len(clean_cep) == 8 else None)


def _call_melhor_envio_api(
    dest_cep: str,
    order_value_brl: float,
    profile: ShippingProfile,
    token: str,
    sandbox: bool = True,
) -> list[ShippingQuoteOption] | None:
    """Consulta o endpoint oficial POST /api/v2/me/shipment/calculate do Melhor Envio."""
    base_url = "https://sandbox.melhorenvio.com.br" if sandbox else "https://melhorenvio.com.br"
    url = f"{base_url}/api/v2/me/shipment/calculate"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": MELHOR_ENVIO_USER_AGENT,
    }

    payload = {
        "from": {"postal_code": digits_only(STORE_ORIGIN_CEP) or "79002070"},
        "to": {"postal_code": dest_cep},
        "products": [
            {
                "id": "instrumento_musical",
                "width": profile.width_cm,
                "height": profile.height_cm,
                "length": profile.length_cm,
                "weight": profile.weight_kg,
                "insurance_value": round(max(order_value_brl, 50.0), 2),
                "quantity": 1,
            }
        ],
        "options": {"receipt": False, "own_hand": False},
        "services": "1,2,3",  # 1: PAC (Correios), 2: SEDEX (Correios), 3: Jadlog (.Package)
    }

    try:
        with httpx.Client(timeout=6.0) as client:
            response = client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                return None
            data = response.json()
    except Exception:
        return None

    if not isinstance(data, list):
        return None

    options: list[ShippingQuoteOption] = []
    for item in data:
        if not isinstance(item, dict) or item.get("error"):
            continue
        price_raw = item.get("custom_price") or item.get("price")
        if price_raw is None:
            continue
        try:
            price = round(float(price_raw), 2)
        except (TypeError, ValueError):
            continue

        delivery_range = item.get("custom_delivery_range") or item.get("delivery_range") or {}
        d_min = int(delivery_range.get("min") or item.get("delivery_time") or 3)
        d_max = int(delivery_range.get("max") or item.get("delivery_time") or 8)
        company_name = (item.get("company") or {}).get("name", "Transportadora")
        service_name = item.get("name", " Padrão")

        options.append(
            ShippingQuoteOption(
                service_name=f"{service_name} ({company_name})",
                carrier=company_name,
                price_brl=price,
                delivery_days_min=d_min,
                delivery_days_max=d_max,
                includes_insurance=True,
                includes_tracking=True,
                notes="Cotação em tempo real via API Melhor Envio (seguro incluso).",
            )
        )

    return options if options else None


def _calculate_contingency_shipping(
    destination: str,
    clean_cep: str | None,
    order_value_brl: float,
    profile: ShippingProfile,
) -> list[ShippingQuoteOption]:
    """Cálculo determinístico local alinhado à Seção 5.2 do manual quando sem token ou offline."""
    norm_dest = normalize_text(destination)
    # Fator regional (1.0 = MS interior, 1.25 = Centro-Oeste/Sudeste/Sul, 1.55 = Norte/Nordeste)
    region_factor = 1.25
    if clean_cep:
        prefix2 = int(clean_cep[:2])
        if prefix2 == 79:
            region_factor = 1.0
        elif 70 <= prefix2 <= 78 or 1 <= prefix2 <= 39 or 80 <= prefix2 <= 99:
            region_factor = 1.25
        else:
            region_factor = 1.55
    elif any(city in norm_dest for city in ("dourados", "tres lagoas", "corumba", "ponta pora", " ms")):
        region_factor = 1.0

    insurance_fee = round(order_value_brl * 0.012, 2)  # 1,2% de seguro de transporte (Seção 5.2)
    weight_base = profile.weight_kg * 6.5

    pac_price = round((34.0 + weight_base) * region_factor + insurance_fee, 2)
    jadlog_price = round((42.0 + weight_base * 1.1) * region_factor + insurance_fee, 2)
    sedex_price = round((64.0 + weight_base * 1.45) * region_factor + insurance_fee, 2)

    return [
        ShippingQuoteOption(
            service_name="PAC (Correios)",
            carrier="Correios",
            price_brl=pac_price,
            delivery_days_min=5,
            delivery_days_max=12,
            includes_insurance=True,
            includes_tracking=True,
            notes="Modalidade econômica com seguro e rastreamento (Seção 5.2).",
        ),
        ShippingQuoteOption(
            service_name="Jadlog (.package)",
            carrier="Jadlog",
            price_brl=jadlog_price,
            delivery_days_min=3,
            delivery_days_max=8,
            includes_insurance=True,
            includes_tracking=True,
            notes="Transportadora recomendada para instrumentos musicais, seguro incluso (Seção 5.2).",
        ),
        ShippingQuoteOption(
            service_name="SEDEX (Correios)",
            carrier="Correios",
            price_brl=sedex_price,
            delivery_days_min=2,
            delivery_days_max=5,
            includes_insurance=True,
            includes_tracking=True,
            notes="Entrega expressa com seguro e rastreamento (Seção 5.2).",
        ),
    ]


def calculate_shipping(
    destination: str,
    order_value_brl: float,
    category_id: int | None = None,
    token_override: str | None = None,
) -> ShippingCalculationResult:
    """
    Calcula opções de frete e prazo conforme a Seção 5 do manual da loja:
    - Região Metropolitana de Campo Grande: Motoboy próprio (Grátis > R$ 500,00 ou R$ 35,00 até R$ 500,00; 1 a 3 dias úteis).
    - Outras cidades: API v2 do Melhor Envio (se MELHOR_ENVIO_TOKEN configurado) com fallback determinístico local.
    """
    is_cg, clean_cep = is_campo_grande_destination(destination)
    profile = CATEGORY_SHIPPING_PROFILES.get(category_id or 5, DEFAULT_PROFILE)

    large_warning = None
    if profile.is_large_item:
        large_warning = (
            f"Atenção (Seção 5.2): Instrumentos de grande porte ({profile.label}) "
            "podem exigir frete especial com cotação individual."
        )

    if is_cg:
        is_free = order_value_brl > 500.0
        motoboy_price = 0.0 if is_free else 35.0
        note = (
            "Frete grátis para pedidos acima de R$ 500,00 na Região Metropolitana de Campo Grande. "
            "Entrega por motoboy próprio com contato telefônico prévio (Seção 5.1)."
            if is_free
            else "Taxa fixa de R$ 35,00 para pedidos de até R$ 500,00 em Campo Grande. "
            "Entrega por motoboy próprio com contato telefônico prévio (Seção 5.1)."
        )
        return ShippingCalculationResult(
            destination=destination,
            postal_code_clean=clean_cep,
            is_local_campo_grande=True,
            source="regra_local_motoboy",
            large_item_warning=large_warning,
            options=[
                ShippingQuoteOption(
                    service_name="Motoboy Próprio (Campo Grande)",
                    carrier="Empório da Música",
                    price_brl=motoboy_price,
                    delivery_days_min=1,
                    delivery_days_max=3,
                    includes_insurance=True,
                    includes_tracking=True,
                    notes=note,
                )
            ],
        )

    token = token_override if token_override is not None else MELHOR_ENVIO_TOKEN
    if token and clean_cep and len(clean_cep) == 8:
        api_options = _call_melhor_envio_api(
            dest_cep=clean_cep,
            order_value_brl=order_value_brl,
            profile=profile,
            token=token,
            sandbox=MELHOR_ENVIO_SANDBOX,
        )
        if api_options:
            return ShippingCalculationResult(
                destination=destination,
                postal_code_clean=clean_cep,
                is_local_campo_grande=False,
                source="melhor_envio_api",
                large_item_warning=large_warning,
                options=api_options,
            )

    fallback_options = _calculate_contingency_shipping(
        destination=destination,
        clean_cep=clean_cep,
        order_value_brl=order_value_brl,
        profile=profile,
    )
    return ShippingCalculationResult(
        destination=destination,
        postal_code_clean=clean_cep,
        is_local_campo_grande=False,
        source="tabela_contingencia_loja",
        large_item_warning=large_warning,
        options=fallback_options,
    )
