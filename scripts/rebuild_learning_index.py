"""Rebuild Chroma learning vectors from SQLite."""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from life_copilot import storage  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=PROJECT_ROOT / "life_copilot.db")
    parser.add_argument("--chroma", type=Path, default=PROJECT_ROOT / "chroma_data")
    parser.add_argument("--backup-dir", type=Path, default=PROJECT_ROOT / "backups")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required because the current learning collection will be replaced.",
    )
    args = parser.parse_args()
    if not args.confirm:
        parser.error("Pass --confirm to rebuild the learning index.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = args.backup_dir / f"before_vector_rebuild_{timestamp}"
    backup.mkdir(parents=True, exist_ok=False)
    if args.chroma.exists():
        shutil.copytree(args.chroma, backup / args.chroma.name)

    count = storage.rebuild_learning_vectors(args.database, args.chroma)
    print(f"Backup: {backup}")
    print(f"Rebuilt learning vectors: {count}")


if __name__ == "__main__":
    main()
