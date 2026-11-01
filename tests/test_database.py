"""Testes automatizados da camada de ingestão e higienização SQLite."""

from pathlib import Path

from src.database import get_connection, init_database, normalize_text


def test_normalize_text() -> None:
    assert normalize_text("Violão Clássico Elétrico") == "violao classico eletrico"
    assert normalize_text("  Campo   Grande - MS ") == "campo grande - ms"


def test_database_ingestion_and_anomalies(tmp_path: Path) -> None:
    db_file = tmp_path / "test_emporio.db"
    init_database(db_path=db_file, force_rebuild=True)

    conn = get_connection(db_file, readonly=True)

    # Verifica contagens exatas dos CSVs
    assert conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 9
    assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 65
    assert conn.execute("SELECT COUNT(*) FROM promotions").fetchone()[0] == 25
    assert conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 50
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 20
    assert conn.execute("SELECT COUNT(*) FROM order_items").fetchone()[0] == 22

    # Caso de borda 1: Produto 96 (Giannini GF-3D) está active mas com stock_quantity = 0
    prod_96 = conn.execute(
        "SELECT availability_label, is_available, stock_quantity FROM v_products_enriched WHERE product_id = 96"
    ).fetchone()
    assert prod_96["availability_label"] == "sem_estoque"
    assert prod_96["is_available"] == 0
    assert prod_96["stock_quantity"] == 0

    # Caso de borda 2: Produto 136 (Ibanez Bass 2X) tem stock 13 mas status = discontinued
    prod_136 = conn.execute(
        "SELECT availability_label, is_available, stock_quantity FROM v_products_enriched WHERE product_id = 136"
    ).fetchone()
    assert prod_136["availability_label"] == "descontinuado"
    assert prod_136["is_available"] == 0
    assert prod_136["stock_quantity"] == 13

    # Caso de borda 3: Produto 90 (Crafter HT-100) possui promoção ativa de 18% -> PIX não acumula
    prod_90 = conn.execute(
        "SELECT original_price_brl, active_discount_percent, final_price_brl, pix_price_brl, pix_discount_applied "
        "FROM v_products_enriched WHERE product_id = 90"
    ).fetchone()
    assert prod_90["original_price_brl"] == 2399.0
    assert prod_90["active_discount_percent"] == 18.0
    assert prod_90["final_price_brl"] == 1967.18
    assert prod_90["pix_price_brl"] == 1967.18
    assert prod_90["pix_discount_applied"] == 0

    # Caso de borda 4: Produto 95 (Takamine GD20) tem apenas promoção expirada -> PIX aplica 5%
    prod_95 = conn.execute(
        "SELECT original_price_brl, active_discount_percent, final_price_brl, pix_price_brl, pix_discount_applied "
        "FROM v_products_enriched WHERE product_id = 95"
    ).fetchone()
    assert prod_95["original_price_brl"] == 2199.0
    assert prod_95["active_discount_percent"] == 0.0
    assert prod_95["final_price_brl"] == 2199.0
    assert prod_95["pix_price_brl"] == 2089.05
    assert prod_95["pix_discount_applied"] == 1

    conn.close()
