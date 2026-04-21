"""
軽量な自動マイグレーションヘルパー。

本格的な Alembic は導入済だが、既存 SQLite DB (aimotion_experimental.db) に対する
「カラム追加のみ」は起動時に自動適用することで、ローカル開発の煩雑さを下げる。

- 既存カラムは PRAGMA table_info で検査
- 既に存在するカラムは ALTER しない (idempotent)
- 失敗しても例外を上まで飛ばさない（ログ警告にとどめる）

このヘルパーは Base.metadata.create_all の後に呼ぶ前提。
"""

from __future__ import annotations

import logging
from typing import Iterable, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


# (table_name, column_name, column_ddl)
ADDITIVE_COLUMNS: Tuple[Tuple[str, str, str], ...] = (
    ("analysis_results", "events", "JSON"),
    ("analysis_results", "events_version", "VARCHAR(64)"),
)


def apply_additive_migrations(engine: Engine) -> None:
    """既存テーブルに欠けているカラムを追加する"""
    try:
        with engine.connect() as conn:
            for table, column, ddl in ADDITIVE_COLUMNS:
                existing = _existing_columns(conn, table)
                if existing is None:
                    logger.debug("[MIGRATE] Table '%s' does not exist yet, skip", table)
                    continue
                if column in existing:
                    continue
                sql = f'ALTER TABLE "{table}" ADD COLUMN "{column}" {ddl}'
                logger.info("[MIGRATE] %s", sql)
                conn.execute(text(sql))
                conn.commit()
    except Exception as exc:  # pragma: no cover - fail-soft
        logger.warning("[MIGRATE] additive migration failed: %s", exc)


def _existing_columns(conn, table: str) -> Iterable[str] | None:
    rows = conn.execute(text(f'PRAGMA table_info("{table}")')).fetchall()
    if not rows:
        return None
    return {row[1] for row in rows}  # row[1] = column name
