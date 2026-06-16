"""初始化 PostgreSQL 数据库与表结构。

用法:
    python scripts/init_postgres.py
    python scripts/init_postgres.py --create-db

环境变量 DATABASE_URL 示例:
    postgresql://postgres:密码@localhost:5432/durian_agent
"""

from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def create_database_if_needed(url: str) -> None:
    parsed = urlparse(url)
    db_name = parsed.path.lstrip("/")
    if not db_name:
        print("DATABASE_URL 缺少数据库名")
        sys.exit(1)

    import psycopg

    # 连到默认 postgres 库建库
    admin_path = f"/postgres"
    admin_url = url.replace(f"/{db_name}", admin_path, 1)

    try:
        with psycopg.connect(admin_url, autocommit=True, connect_timeout=10) as conn:
            exists = conn.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (db_name,)
            ).fetchone()
            if exists:
                print(f"数据库已存在: {db_name}")
                return
            conn.execute(f'CREATE DATABASE "{db_name}"')
            print(f"已创建数据库: {db_name}")
    except Exception as exc:
        print(f"创建数据库失败: {exc}")
        print("若库已存在可忽略，继续初始化表...")
        if "already exists" not in str(exc).lower():
            raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--create-db", action="store_true", help="若库不存在则自动创建")
    args = parser.parse_args()

    url = os.getenv("DATABASE_URL", "")
    if not url.startswith("postgresql") and not url.startswith("postgres"):
        print("请先在 .env 设置 PostgreSQL 连接，例如:")
        print("DATABASE_URL=postgresql://postgres:密码@localhost:5432/durian_agent")
        print("")
        print("或运行: .\\scripts\\setup_postgres.ps1 -Password \"你的密码\"")
        sys.exit(1)

    if args.create_db:
        create_database_if_needed(url)

    from src.storage.db import init_db
    from src.storage.connection import database_label

    init_db()
    print(f"表结构与演示数据初始化完成（{database_label()}）")


if __name__ == "__main__":
    main()
