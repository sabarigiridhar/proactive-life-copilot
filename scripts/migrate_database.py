"""Back up and migrate the Life Copilot data stores."""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import db_utils  # noqa: E402


def create_backup(db_path: Path, chroma_path: Path, backup_root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = backup_root / f"before_schema_update_{timestamp}"
    destination.mkdir(parents=True, exist_ok=False)
    if db_path.exists():
        shutil.copy2(db_path, destination / db_path.name)
    if chroma_path.exists():
        shutil.copytree(chroma_path, destination / chroma_path.name)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Back up data, apply SQLite migrations, and preserve learning summaries."
    )
    parser.add_argument("--database", type=Path, default=PROJECT_ROOT / "life_copilot.db")
    parser.add_argument("--chroma", type=Path, default=PROJECT_ROOT / "chroma_data")
    parser.add_argument("--backup-dir", type=Path, default=PROJECT_ROOT / "backups")
    parser.add_argument(
        "--rebuild-vectors",
        action="store_true",
        help="Rebuild Chroma with stable SQLite-based document IDs after migration.",
    )
    args = parser.parse_args()

    backup = create_backup(args.database, args.chroma, args.backup_dir)
    applied = db_utils.init_sqlite_db(args.database)
    recovered = db_utils.backfill_learning_summaries_from_chroma(
        args.database, args.chroma
    )
    rebuilt = None
    if args.rebuild_vectors:
        rebuilt = db_utils.rebuild_learning_vectors(args.database, args.chroma)

    print(f"Backup: {backup}")
    print(f"Applied migrations: {applied or 'none'}")
    print(f"Recovered legacy learning summaries: {recovered}")
    if rebuilt is not None:
        print(f"Rebuilt learning vectors: {rebuilt}")


if __name__ == "__main__":
    main()
