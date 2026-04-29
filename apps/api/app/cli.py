# app/cli.py
"""
MakersHub API 运维命令入口

该文件用于放置只能由部署或运维执行的命令，不能作为普通业务接口暴露。
目前包含唯一 999 超级管理员初始化命令。

使用示例:
    uv run python -m app.cli bootstrap-super-admin --email admin@example.com
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os

from app.core.database.session import AsyncSessionLocal, close_database_engine
from app.modules.identity.service import bootstrap_super_admin


def build_parser() -> argparse.ArgumentParser:
    """
    构建命令行参数解析器。

    Returns:
        已注册子命令的 argparse.ArgumentParser。
    """

    parser = argparse.ArgumentParser(prog="makershub-api")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- 初始化唯一 999 超级管理员 ---
    bootstrap_parser = subparsers.add_parser("bootstrap-super-admin")
    bootstrap_parser.add_argument("--email", required=True)
    bootstrap_parser.add_argument("--display-name", default="系统超级管理员")
    bootstrap_parser.add_argument("--password-env", default="INITIAL_SUPER_ADMIN_PASSWORD")

    return parser


async def run_bootstrap_super_admin(args: argparse.Namespace) -> None:
    """
    执行唯一 999 初始化。

    Args:
        args: argparse 解析后的命令参数。

    注意:
        密码优先从环境变量读取，便于 Docker/CI/部署平台通过 secret 注入。
        如果没有环境变量，则交互式输入，避免密码出现在 shell 历史中。
    """

    password = os.environ.get(args.password_env)
    if not password:
        password = getpass.getpass("Initial super admin password: ")

    async with AsyncSessionLocal() as session:
        # bootstrap_super_admin 内部会检查系统中是否已经存在有效 999。
        result = await bootstrap_super_admin(
            session,
            email=args.email,
            password=password,
            display_name=args.display_name,
        )
        await session.commit()

    print(f"created={result.created} user_id={result.user.id} email={result.local_account.email}")


async def main() -> None:
    """CLI 异步主函数。"""

    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "bootstrap-super-admin":
            await run_bootstrap_super_admin(args)
    finally:
        # CLI 进程结束前主动释放连接池，避免异步 engine 残留告警。
        await close_database_engine()


if __name__ == "__main__":
    asyncio.run(main())
