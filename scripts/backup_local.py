from __future__ import annotations

import argparse
from pathlib import Path

from angel_market.storage.sqlite import Database


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria uma copia consistente do SQLite local.")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--db", type=Path, default=ROOT / "data/private/angel_market.db")
    args = parser.parse_args()
    if not args.db.exists():
        raise SystemExit(f"banco de origem nao encontrado: {args.db}")
    database = Database(args.db)
    try:
        destination = database.backup(args.destination)
    finally:
        database.close()
    print(f"backup_ok destination={destination}")


if __name__ == "__main__":
    main()

