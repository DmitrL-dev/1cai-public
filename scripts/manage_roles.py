
"""CLI tool to grant/revoke user roles and permissions."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage user roles and permissions")

    subparsers = parser.add_subparsers(dest="command", required=True)

    grant_role = subparsers.add_parser("grant-role", help="Grant role to user")
    grant_role.add_argument("user_id", help="User identifier")
    grant_role.add_argument("role", help="Role name (e.g. admin, moderator)")
    grant_role.add_argument("--assigned-by", dest="assigned_by")
    grant_role.add_argument("--reason")
    grant_role.add_argument("--metadata", help="JSON string with metadata")

    revoke_role = subparsers.add_parser("revoke-role", help="Revoke role from user")
    revoke_role.add_argument("user_id")
    revoke_role.add_argument("role")
    revoke_role.add_argument("--revoked-by", dest="revoked_by")
    revoke_role.add_argument("--reason")
    revoke_role.add_argument("--metadata", help="JSON string with metadata")

    grant_perm = subparsers.add_parser("grant-permission", help="Grant permission to user")
    grant_perm.add_argument("user_id")
    grant_perm.add_argument("permission")
    grant_perm.add_argument("--assigned-by", dest="assigned_by")

    revoke_perm = subparsers.add_parser("revoke-permission", help="Revoke permission from user")
    revoke_perm.add_argument("user_id")
    revoke_perm.add_argument("permission")

    return parser.parse_args()


async def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env", override=False)

    args = parse_args()

    from src.database import create_pool
    from src.security.roles import (grant_permission, grant_role,
                                    revoke_permission, revoke_role)

    await create_pool()

    metadata = None
    if getattr(args, "metadata", None):
        metadata = json.loads(args.metadata)

    if args.command == "grant-role":
        await grant_role(args.user_id, args.role, args.assigned_by, args.reason, metadata)
        print(f"Role '{args.role}' granted to {args.user_id}")
    elif args.command == "revoke-role":
        await revoke_role(args.user_id, args.role, args.revoked_by, args.reason, metadata)
        print(f"Role '{args.role}' revoked from {args.user_id}")
    elif args.command == "grant-permission":
        await grant_permission(args.user_id, args.permission, args.assigned_by)
        print(f"Permission '{args.permission}' granted to {args.user_id}")
    elif args.command == "revoke-permission":
        await revoke_permission(args.user_id, args.permission)
        print(f"Permission '{args.permission}' revoked from {args.user_id}")


if __name__ == "__main__":
    asyncio.run(main())

