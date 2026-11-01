"""Pipeline de ingestão, higienização dos CSVs e banco relacional SQLite da Empório da Música."""

from __future__ import annotations

import csv
import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any

from src.config import DATA_DIR, DB_PATH


def normalize_text(value: str | None) -> str:
    """Remove acentos, converte para minúsculas e normaliza espaços para busca tolerante."""
    if not value:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(value))
    no_accents = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", no_accents).strip().lower()


def digits_only(value: str | None) -> str:
    """Extrai apenas dígitos numéricos (útil para CEPs e telefones)."""
    if not value:
        return ""
    return re.sub(r"\D+", "", str(value))


def _read_csv(file_path: Path) -> list[dict[str, str]]:
    with open(file_path, mode="r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        return [
            {k.strip(): (v.strip() if isinstance(v, str) else "") for k, v in row.items() if k}
            for row in reader
        ]


def get_connection(db_path: Path = DB_PATH, readonly: bool = False) -> sqlite3.Connection:
    """Retorna conexão SQLite configurada com Row factory e função NORM()."""
    if readonly:
        uri = f"file:{db_path.resolve()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.create_function("NORM", 1, normalize_text)
    return conn


def init_database(data_dir: Path = DATA_DIR, db_path: Path = DB_PATH, force_rebuild: bool = False) -> Path:
    """Inicializa o banco SQLite a partir dos CSVs da loja, tratando tipos e colunas JSON."""
    if db_path.exists() and not force_rebuild:
        try:
            conn = get_connection(db_path)
            count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            conn.close()
            if count > 0:
                return db_path
        except sqlite3.Error:
            pass

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path, readonly=False)
    cur = conn.cursor()

    cur.executescript(
        """
        DROP VIEW IF EXISTS v_products_enriched;
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS promotions;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS categories;

        CREATE TABLE categories (
            category_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            name_norm TEXT NOT NULL,
            description TEXT NOT NULL
        );

        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            price_brl REAL NOT NULL,
            name TEXT NOT NULL,
            name_norm TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            description_norm TEXT NOT NULL,
            stock_quantity INTEGER NOT NULL,
            status TEXT NOT NULL,
            specs_json TEXT NOT NULL,
            spec_strings TEXT,
            spec_electronics TEXT,
            spec_color TEXT,
            spec_top TEXT,
            spec_back_sides TEXT,
            spec_neck TEXT,
            spec_body TEXT,
            spec_type TEXT,
            spec_keys TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories(category_id)
        );

        CREATE TABLE promotions (
            promotion_id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL,
            discount_percent REAL NOT NULL,
            description TEXT NOT NULL,
            is_active INTEGER NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );

        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            name_norm TEXT NOT NULL,
            phone TEXT NOT NULL,
            phone_digits TEXT NOT NULL,
            email TEXT NOT NULL,
            email_norm TEXT NOT NULL,
            city TEXT NOT NULL,
            city_norm TEXT NOT NULL
        );

        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT NOT NULL,
            total_brl REAL NOT NULL,
            payment_method TEXT NOT NULL,
            tracking_code TEXT,
            estimated_delivery TEXT,
            notes TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
        """
    )

    # 1. Categories
    categories_rows = _read_csv(data_dir / "desafio_tecnico_ai_eng - categories.csv")
    for r in categories_rows:
        cur.execute(
            "INSERT INTO categories (category_id, name, name_norm, description) VALUES (?, ?, ?, ?)",
            (int(r["category_id"]), r["name"], normalize_text(r["name"]), r["description"]),
        )

    # 2. Products (com extração estruturada do JSON specs)
    products_rows = _read_csv(data_dir / "desafio_tecnico_ai_eng - products.csv")
    for r in products_rows:
        raw_specs = r.get("specs", "{}") or "{}"
        try:
            specs: dict[str, Any] = json.loads(raw_specs)
        except json.JSONDecodeError:
            specs = {}

        cur.execute(
            """
            INSERT INTO products (
                product_id, price_brl, name, name_norm, category_id,
                description, description_norm, stock_quantity, status,
                specs_json, spec_strings, spec_electronics, spec_color,
                spec_top, spec_back_sides, spec_neck, spec_body,
                spec_type, spec_keys, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(r["product_id"]),
                float(r["price_brl"]),
                r["name"],
                normalize_text(r["name"]),
                int(r["category_id"]),
                r["description"],
                normalize_text(r["description"] + " " + raw_specs),
                int(r["stock_quantity"]),
                r["status"].lower(),
                json.dumps(specs, ensure_ascii=False),
                normalize_text(specs.get("strings")),
                normalize_text(specs.get("electronics")),
                normalize_text(specs.get("color")),
                normalize_text(specs.get("top")),
                normalize_text(specs.get("back_sides")),
                normalize_text(specs.get("neck")),
                normalize_text(specs.get("body")),
                normalize_text(specs.get("type")),
                str(specs.get("keys", "")).strip() or None,
                r["created_at"],
            ),
        )

    # 3. Promotions
    promotions_rows = _read_csv(data_dir / "desafio_tecnico_ai_eng - promotions.csv")
    for r in promotions_rows:
        cur.execute(
            """
            INSERT INTO promotions (promotion_id, product_id, discount_percent, description, is_active)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(r["promotion_id"]),
                int(r["product_id"]),
                float(r["discount_percent"]),
                r["description"],
                int(r["is_active"]),
            ),
        )

    # 4. Customers
    customers_rows = _read_csv(data_dir / "desafio_tecnico_ai_eng - customers.csv")
    for r in customers_rows:
        cur.execute(
            """
            INSERT INTO customers (
                customer_id, name, name_norm, phone, phone_digits,
                email, email_norm, city, city_norm
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(r["customer_id"]),
                r["name"],
                normalize_text(r["name"]),
                r["phone"],
                digits_only(r["phone"]),
                r["email"],
                normalize_text(r["email"]),
                r["city"],
                normalize_text(r["city"]),
            ),
        )

    # 5. Orders
    orders_rows = _read_csv(data_dir / "desafio_tecnico_ai_eng - orders.csv")
    for r in orders_rows:
        cur.execute(
            """
            INSERT INTO orders (
                order_id, customer_id, order_date, status, total_brl,
                payment_method, tracking_code, estimated_delivery, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(r["order_id"]),
                int(r["customer_id"]),
                r["order_date"],
                r["status"].lower(),
                float(r["total_brl"]),
                r["payment_method"],
                r["tracking_code"] or None,
                r["estimated_delivery"] or None,
                r["notes"] or None,
            ),
        )

    # 6. Order Items
    order_items_rows = _read_csv(data_dir / "desafio_tecnico_ai_eng - order_items.csv")
    for r in order_items_rows:
        cur.execute(
            "INSERT INTO order_items (order_id, quantity, product_id) VALUES (?, ?, ?)",
            (int(r["order_id"]), int(r["quantity"]), int(r["product_id"])),
        )

    # View enriquecida com regras de promoção ativa, PIX não-cumulativo (Seção 6.2) e disponibilidade (Seção 7.3)
    cur.executescript(
        """
        CREATE VIEW v_products_enriched AS
        SELECT
            p.product_id,
            p.name,
            p.name_norm,
            p.category_id,
            c.name AS category_name,
            c.name_norm AS category_name_norm,
            p.status,
            p.stock_quantity,
            CASE
                WHEN p.status = 'active' AND p.stock_quantity > 0 THEN 'disponivel'
                WHEN p.status = 'active' AND p.stock_quantity <= 0 THEN 'sem_estoque'
                WHEN p.status = 'discontinued' THEN 'descontinuado'
                WHEN p.status = 'coming_soon' THEN 'em_breve'
                ELSE 'indisponivel'
            END AS availability_label,
            CASE
                WHEN p.status = 'active' AND p.stock_quantity > 0 THEN 1
                ELSE 0
            END AS is_available,
            p.price_brl AS original_price_brl,
            COALESCE(pr.discount_percent, 0.0) AS active_discount_percent,
            pr.description AS promotion_description,
            ROUND(p.price_brl * (1.0 - COALESCE(pr.discount_percent, 0.0) / 100.0), 2) AS final_price_brl,
            CASE
                WHEN COALESCE(pr.discount_percent, 0.0) > 0 THEN
                    ROUND(p.price_brl * (1.0 - pr.discount_percent / 100.0), 2)
                ELSE
                    ROUND(p.price_brl * 0.95, 2)
            END AS pix_price_brl,
            CASE
                WHEN COALESCE(pr.discount_percent, 0.0) > 0 THEN 0
                ELSE 1
            END AS pix_discount_applied,
            p.description,
            p.description_norm,
            p.specs_json,
            p.spec_strings,
            p.spec_electronics,
            p.spec_color,
            p.spec_top,
            p.spec_back_sides,
            p.spec_neck,
            p.spec_body,
            p.spec_type,
            p.spec_keys,
            p.created_at
        FROM products p
        JOIN categories c ON c.category_id = p.category_id
        LEFT JOIN promotions pr ON pr.product_id = p.product_id AND pr.is_active = 1;
        """
    )

    conn.commit()
    conn.close()
    return db_path
