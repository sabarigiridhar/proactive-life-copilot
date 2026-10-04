"""Parameterized record listing and dashboard aggregation queries."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from backend.models.records import RecordDomain, RecordListQuery
from life_copilot import storage
from life_copilot.storage.base import DOMAIN_SELECTS, DOMAIN_TABLES, _database


DOMAIN_FILTERS = {
    RecordDomain.WEALTH: {
        "transaction_type": "LOWER(transaction_type) = LOWER(?)",
        "currency": "LOWER(currency) = LOWER(?)",
        "category": "LOWER(category) = LOWER(?)",
        "merchant": "LOWER(COALESCE(merchant, '')) LIKE LOWER(?)",
    },
    RecordDomain.HEALTH: {
        "workout_type": "LOWER(COALESCE(workout_type, '')) LIKE LOWER(?)",
    },
    RecordDomain.LEARNING: {
        "topic": "LOWER(topic) = LOWER(?)",
    },
}
SEARCH_COLUMNS = {
    RecordDomain.WEALTH: ("category", "merchant", "notes"),
    RecordDomain.HEALTH: ("workout_type", "notes"),
    RecordDomain.LEARNING: ("topic", "summary_text", "url_reference"),
}


def list_records(
    domain: RecordDomain,
    query: RecordListQuery,
    *,
    db_path: Path,
) -> tuple[list[dict], int]:
    storage.init_sqlite_db(db_path)
    clauses = []
    params: list = []
    if query.start_date:
        clauses.append("entry_date >= ?")
        params.append(query.start_date.isoformat())
    if query.end_date:
        clauses.append("entry_date <= ?")
        params.append(query.end_date.isoformat())
    if query.source:
        clauses.append("LOWER(source) = LOWER(?)")
        params.append(query.source)

    for field, clause in DOMAIN_FILTERS[domain].items():
        value = getattr(query, field)
        if value is None:
            continue
        clauses.append(clause)
        params.append(f"%{value}%" if "LIKE" in clause else value)

    if query.search:
        search_clauses = [
            f"LOWER(COALESCE({column}, '')) LIKE LOWER(?)"
            for column in SEARCH_COLUMNS[domain]
        ]
        clauses.append(f"({' OR '.join(search_clauses)})")
        params.extend([f"%{query.search}%"] * len(search_clauses))

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    table = DOMAIN_TABLES[domain.value]
    columns = DOMAIN_SELECTS[domain.value]
    offset = (query.page - 1) * query.page_size
    with _database(db_path) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM {table} {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT {columns}
            FROM {table}
            {where}
            ORDER BY entry_date DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, query.page_size, offset],
        ).fetchall()
    return [dict(row) for row in rows], total


def load_dashboard_rows(
    start_date: date,
    end_date: date,
    *,
    db_path: Path,
) -> dict[str, list[dict]]:
    storage.init_sqlite_db(db_path)
    bounds = (start_date.isoformat(), end_date.isoformat())
    with _database(db_path) as conn:
        wealth_totals = conn.execute(
            """
            SELECT transaction_type, UPPER(currency) AS currency,
                   ROUND(SUM(amount), 2) AS total, COUNT(*) AS records
            FROM wealth_logs
            WHERE entry_date BETWEEN ? AND ?
            GROUP BY LOWER(transaction_type), UPPER(currency)
            ORDER BY currency, transaction_type
            """,
            bounds,
        ).fetchall()
        wealth_categories = conn.execute(
            """
            SELECT category, UPPER(currency) AS currency,
                   ROUND(SUM(amount), 2) AS total, COUNT(*) AS records
            FROM wealth_logs
            WHERE entry_date BETWEEN ? AND ?
              AND LOWER(transaction_type) = 'expense'
            GROUP BY category, UPPER(currency)
            ORDER BY total DESC, category, currency
            """,
            bounds,
        ).fetchall()
        wealth_daily = conn.execute(
            """
            SELECT entry_date, UPPER(currency) AS currency,
                   ROUND(SUM(CASE WHEN LOWER(transaction_type) = 'income'
                                  THEN amount ELSE 0 END), 2) AS income,
                   ROUND(SUM(CASE WHEN LOWER(transaction_type) = 'expense'
                                  THEN amount ELSE 0 END), 2) AS expense
            FROM wealth_logs
            WHERE entry_date BETWEEN ? AND ?
            GROUP BY entry_date, UPPER(currency)
            ORDER BY entry_date, currency
            """,
            bounds,
        ).fetchall()
        health_daily = conn.execute(
            """
            SELECT entry_date, sleep_hours, calories_consumed, workout_type
            FROM health_logs
            WHERE entry_date BETWEEN ? AND ?
            ORDER BY entry_date
            """,
            bounds,
        ).fetchall()
        learning_daily = conn.execute(
            """
            SELECT entry_date, COALESCE(SUM(duration_minutes), 0) AS minutes,
                   COUNT(*) AS sessions
            FROM learning_logs
            WHERE entry_date BETWEEN ? AND ?
            GROUP BY entry_date
            ORDER BY entry_date
            """,
            bounds,
        ).fetchall()
        learning_topics = conn.execute(
            """
            SELECT topic, COALESCE(SUM(duration_minutes), 0) AS minutes,
                   COUNT(*) AS sessions
            FROM learning_logs
            WHERE entry_date BETWEEN ? AND ?
            GROUP BY topic
            ORDER BY minutes DESC, sessions DESC, topic
            """,
            bounds,
        ).fetchall()
    return {
        "wealth_totals": [dict(row) for row in wealth_totals],
        "wealth_categories": [dict(row) for row in wealth_categories],
        "wealth_daily": [dict(row) for row in wealth_daily],
        "health_daily": [dict(row) for row in health_daily],
        "learning_daily": [dict(row) for row in learning_daily],
        "learning_topics": [dict(row) for row in learning_topics],
    }
