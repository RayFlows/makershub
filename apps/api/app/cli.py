from __future__ import annotations

import argparse
import asyncio
import getpass
import os

from app.core.database.session import AsyncSessionLocal, close_database_engine
from app.modules.identity.service import bootstrap_super_admin


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="makershub-api")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = subparsers.add_parser("bootstrap-super-admin")
    bootstrap_parser.add_argument("--email", required=True)
    bootstrap_parser.add_argument("--display-name", default="系统超级管理员")
    bootstrap_parser.add_argument("--password-env", default="INITIAL_SUPER_ADMIN_PASSWORD")

    return parser


async def run_bootstrap_super_admin(args: argparse.Namespace) -> None:
    password = os.environ.get(args.password_env)
    if not password:
        password = getpass.getpass("Initial super admin password: ")

    async with AsyncSessionLocal() as session:
        result = await bootstrap_super_admin(
            session,
            email=args.email,
            password=password,
            display_name=args.display_name,
        )
        await session.commit()

    print(f"created={result.created} user_id={result.user.id} email={result.local_account.email}")


async def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "bootstrap-super-admin":
            await run_bootstrap_super_admin(args)
    finally:
        await close_database_engine()


if __name__ == "__main__":
    asyncio.run(main())
