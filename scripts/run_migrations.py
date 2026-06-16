
"""Helper script to run Alembic migrations."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env", override=False)

    alembic_cfg = Config(str(project_root / "alembic.ini"))

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(alembic_cfg, "head")


if __name__ == "__main__":
    try:
        main()
        print("✅ Alembic migrations applied (upgrade head)")
    except Exception as exc:  # noqa: BLE001
        print(f"❌ Migration failed: {exc}")
        sys.exit(1)

