"""Run the self-contained semantic learning-retrieval evaluation."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from life_copilot import storage  # noqa: E402
from life_copilot.retrieval.evaluation import (  # noqa: E402
    evaluate_learning_retrieval,
    load_learning_evaluation,
)
from life_copilot.retrieval.learning import search_learning_records  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "tests" / "fixtures" / "learning_retrieval_cases.json",
    )
    parser.add_argument("--min-hit-rate", type=float, default=0.75)
    args = parser.parse_args()
    if not 0 <= args.min_hit_rate <= 1:
        parser.error("--min-hit-rate must be between 0 and 1.")

    evaluation = load_learning_evaluation(args.dataset)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        db_path = root / "evaluation.db"
        chroma_path = root / "chroma"
        storage.init_sqlite_db(db_path)
        collection = storage.init_chroma_db(chroma_path)
        try:
            for record in evaluation["records"]:
                record_id = storage.insert_learning_log(
                    record["entry_date"],
                    record["topic"],
                    record.get("duration_minutes"),
                    record.get("url_reference"),
                    summary_text=record["summary_text"],
                    source="evaluation",
                    db_path=db_path,
                )
                storage.add_learning_vector(
                    collection,
                    record_id,
                    record["entry_date"],
                    record["topic"],
                    record["summary_text"],
                    record.get("url_reference"),
                )

            report = evaluate_learning_retrieval(
                evaluation["cases"],
                lambda request: search_learning_records(
                    request,
                    db_path=db_path,
                    chroma_path=chroma_path,
                    collection=collection,
                ),
            )
        finally:
            client = getattr(collection, "_client", None)
            system = getattr(client, "_system", None)
            if system is not None:
                system.stop()

    for item in report["cases"]:
        outcome = "PASS" if item["passed"] else "FAIL"
        rank = item["rank"] if item["rank"] is not None else "-"
        print(f"{outcome} {item['name']}: rank={rank}, mode={item['mode']}")
    print(
        f"Top-k hit rate: {report['passed']}/{report['total']} "
        f"({report['top_k_hit_rate']:.0%})"
    )
    if report["top_k_hit_rate"] < args.min_hit_rate:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
