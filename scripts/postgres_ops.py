from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine import make_url


@dataclass(frozen=True)
class PostgresTarget:
    host: str
    port: int
    database: str
    username: str
    password: str
    sslmode: str | None


def parse_postgres_target(database_url: str) -> PostgresTarget:
    url = make_url(database_url)
    if url.drivername != "postgresql+psycopg":
        raise ValueError("DATABASE_URL 必须使用 postgresql+psycopg 驱动")
    if not url.host or not url.database or not url.username:
        raise ValueError("DATABASE_URL 缺少主机、数据库名或用户名")
    return PostgresTarget(
        host=url.host,
        port=url.port or 5432,
        database=url.database,
        username=url.username,
        password=url.password or "",
        sslmode=url.query.get("sslmode"),
    )


def postgres_environment(target: PostgresTarget) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if key != "DATABASE_URL"}
    environment.update(
        {
            "PGHOST": target.host,
            "PGPORT": str(target.port),
            "PGDATABASE": target.database,
            "PGUSER": target.username,
            "PGPASSWORD": target.password,
        }
    )
    if target.sslmode:
        environment["PGSSLMODE"] = target.sslmode
    return environment


def backup_command(target_file: Path) -> list[str]:
    return [
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--file",
        str(target_file),
    ]


def restore_command(source_file: Path, database: str) -> list[str]:
    return [
        "pg_restore",
        "--clean",
        "--if-exists",
        "--exit-on-error",
        "--no-owner",
        "--no-privileges",
        "--dbname",
        database,
        str(source_file),
    ]


def validate_restore_confirmation(target: PostgresTarget, confirmation: str) -> None:
    if confirmation != target.database:
        raise ValueError("恢复确认值必须与目标数据库名完全一致")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="YunSync PostgreSQL/RDS 备份与受控恢复工具。"
    )
    subparsers = parser.add_subparsers(dest="operation", required=True)
    backup = subparsers.add_parser("backup")
    backup.add_argument("--target", type=Path, required=True)
    backup.add_argument("--dry-run", action="store_true")
    restore = subparsers.add_parser("restore")
    restore.add_argument("--source", type=Path, required=True)
    restore.add_argument("--confirm-database", required=True)
    restore.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        parser.error("必须通过环境变量注入 DATABASE_URL")
    target = parse_postgres_target(database_url)
    environment = postgres_environment(target)

    if args.operation == "backup":
        path = args.target.resolve()
        if path.suffix != ".dump":
            parser.error("备份文件必须使用 .dump 扩展名")
        command = backup_command(path)
        if args.dry_run:
            print(_safe_plan("backup", target, command))
            return 0
        _require_program("pg_dump")
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(command, env=environment, check=True)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_suffix(path.suffix + ".sha256").write_text(
            f"{digest}  {path.name}\n", encoding="utf-8"
        )
        print(json.dumps({"operation": "backup", "database": target.database, "completed": True}))
        return 0

    path = args.source.resolve()
    validate_restore_confirmation(target, args.confirm_database)
    command = restore_command(path, target.database)
    if args.dry_run:
        print(_safe_plan("restore", target, command))
        return 0
    if not path.is_file():
        parser.error("恢复源文件不存在")
    _require_program("pg_restore")
    subprocess.run(command, env=environment, check=True)
    print(json.dumps({"operation": "restore", "database": target.database, "completed": True}))
    return 0


def _safe_plan(operation: str, target: PostgresTarget, command: list[str]) -> str:
    return json.dumps(
        {
            "operation": operation,
            "database": target.database,
            "host_configured": bool(target.host),
            "sslmode": target.sslmode,
            "command": command,
            "credentials_in_command": False,
        },
        ensure_ascii=False,
    )


def _require_program(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"未找到 {name}，请先安装 PostgreSQL 客户端工具")


if __name__ == "__main__":
    raise SystemExit(main())
